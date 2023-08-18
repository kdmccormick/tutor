from __future__ import annotations

import os
from collections import defaultdict

import click
import yaml

from tutor import bindmount
from tutor import config as tutor_config
from tutor import exceptions, fmt, hooks
from tutor.commands.config import save as config_save
from tutor.commands.context import Context
from tutor.commands.images import (
    find_images_to_build,
    find_remote_image_tags,
    ImageNotFoundError,
)
from tutor.commands.params import ConfigLoaderParam
from tutor.utils import execute as execute_shell


class MountParamType(ConfigLoaderParam):
    name = "mount"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[click.shell_completion.CompletionItem]:
        mounts = bindmount.get_mounts(self.config)
        return [
            click.shell_completion.CompletionItem(mount)
            for mount in mounts
            if mount.startswith(incomplete)
        ]


@click.group(name="mounts")
def mounts_command() -> None:
    """
    Manage host bind-mounts

    Bind-mounted folders are used both in image building, development (`dev` commands)
    and `local` deployments.
    """


@click.command(name="list")
@click.pass_obj
def mounts_list(context: Context) -> None:
    """
    List bind-mounted folders

    Entries will be fetched from the `MOUNTS` project setting.
    """
    config = tutor_config.load(context.root)
    mounts = []
    for mount_name in bindmount.get_mounts(config):
        build_mounts = [
            {"image": image_name, "context": stage_name}
            for image_name, stage_name in hooks.Filters.IMAGES_BUILD_MOUNTS.iterate(
                mount_name
            )
        ]
        compose_mounts = [
            {
                "service": service,
                "container_path": container_path,
            }
            for service, _host_path, container_path in bindmount.parse_mount(mount_name)
        ]
        mounts.append(
            {
                "name": mount_name,
                "build_mounts": build_mounts,
                "compose_mounts": compose_mounts,
            }
        )
    fmt.echo(yaml.dump(mounts, default_flow_style=False, sort_keys=False))


@click.command(name="add")
@click.argument("mounts", metavar="mount", type=click.Path(), nargs=-1)
@click.option("-p", "--populate", is_flag=True, help="Populate mount after adding it")
@click.pass_context
def mounts_add(context: click.Context, mounts: list[str], populate: bool) -> None:
    """
    Add a bind-mounted folder

    The bind-mounted folder will be added to the project configuration, in the ``MOUNTS``
    setting.

    Values passed to this command can take one of two forms. The first is explicit::

        tutor mounts add myservice:/host/path:/container/path

    The second is implicit::

        tutor mounts add /host/path

    With the explicit form, the value means "bind-mount the host folder /host/path to
    /container/path in the "myservice" container at run time".

    With the implicit form, plugins are in charge of automatically detecting in which
    containers and locations the /host/path folder should be bind-mounted. In this case,
    folders can be bind-mounted at build-time -- which cannot be achieved with the
    explicit form.
    """
    new_mounts = []
    implicit_mounts = []

    for mount in mounts:
        if not bindmount.parse_explicit_mount(mount):
            # Path is implicit: check that this path is valid
            # (we don't try to validate explicit mounts)
            mount = os.path.abspath(os.path.expanduser(mount))
            if not os.path.exists(mount):
                raise exceptions.TutorError(f"Path {mount} does not exist on the host")
            implicit_mounts.append(mount)
        new_mounts.append(mount)
        fmt.echo_info(f"Adding bind-mount: {mount}")

    context.invoke(config_save, append_vars=[("MOUNTS", mount) for mount in new_mounts])

    if populate:
        context.invoke(mounts_populate, mounts=implicit_mounts)


@click.command(name="remove")
@click.argument("mounts", metavar="mount", type=MountParamType(), nargs=-1)
@click.pass_context
def mounts_remove(context: click.Context, mounts: list[str]) -> None:
    """
    Remove a bind-mounted folder

    The bind-mounted folder will be removed from the ``MOUNTS`` project setting.
    """
    removed_mounts = []
    for mount in mounts:
        if not bindmount.parse_explicit_mount(mount):
            # Path is implicit: expand it
            mount = os.path.abspath(os.path.expanduser(mount))
        removed_mounts.append(mount)
        fmt.echo_info(f"Removing bind-mount: {mount}")

    context.invoke(
        config_save, remove_vars=[("MOUNTS", mount) for mount in removed_mounts]
    )


@click.command(name="populate", help="TODO document command")
@click.argument("mounts", metavar="mount", type=str, nargs=-1)
@click.pass_obj
def mounts_populate(context, mounts: str) -> None:
    """
    TODO document command
    """
    container_name = "tutor_mounts_populate_temp"  # TODO: improve name?
    config = tutor_config.load(context.root)
    paths_to_copy_by_image: dict[str, tuple[str, str]] = defaultdict(list)

    if not mounts:
        mounts = bindmount.get_mounts(config)

    for mount in mounts:
        mount_items: list[tuple[str, str, str]] = bindmount.parse_mount(mount)
        if not mount_items:
            raise exceptions.TutorError(f"No mount for {mount}")
        _service, mount_host_path, _container_path = mount_items[
            0
        ]  # [0] is arbitrary, as all host_paths should be equal
        mount_expanded = os.path.abspath(os.path.expanduser(mount))
        mount_name = os.path.basename(mount_expanded)
        for (
            image,
            path_on_image,
            path_in_host_mount,
        ) in hooks.Filters.COMPOSE_MOUNT_POPULATORS.iterate(mount_name):
            paths_to_copy_by_image[image].append(
                (path_on_image, f"{mount_expanded}/{path_in_host_mount}")
            )
    for image_name, paths_to_copy in paths_to_copy_by_image.items():
        image_tag = _get_image_tag(config, image_name)
        execute_shell("docker", "rm", "-f", container_name)
        execute_shell("docker", "create", "--name", container_name, image_tag)
        for path_on_image, path_on_host in paths_to_copy:
            fmt.echo_info(f"Populating {path_on_host} from {image_name}")
            execute_shell("rm", "-rf", path_on_host)
            execute_shell(
                "docker", "cp", f"{container_name}:{path_on_image}", path_on_host
            )
        execute_shell("docker", "rm", "-f", container_name)


def _get_image_tag(config: Config, image_name: str) -> str:
    """
    Translate from a Tutor/plugin-defined image name to a specific Docker image tag.

    Searches for image_name in IMAGES_PULL then IMAGES_BUILD.
    Raises ImageNotFoundError if no match.
    """
    try:
        return next(
            find_remote_image_tags(config, hooks.Filters.IMAGES_PULL, image_name)
        )
    except ImageNotFoundError:
        _name, _path, tag, _args = next(find_images_to_build(config, image_name))
        return tag


@hooks.Filters.COMPOSE_MOUNT_POPULATORS.add()
def _populate_edx_platform_generated_dirs(
    populators: list[tuple[str, str, str]], mount_name: str
) -> list[str]:
    """
    TODO write docstring
    """
    if mount_name == "edx-platform":
        populators += [
            ("openedx-dev", f"/openedx/edx-platform/{generated_dir}", generated_dir)
            for generated_dir in [
                "Open_edX.egg-info",
                "node_modules",
                "lms/static/css",
                "lms/static/certificates/css",
                "cms/static/css",
                "common/static/bundles",
                "common/static/common/js/vendor",
                "common/static/common/css/vendor",
            ]
        ]
    return populators


mounts_command.add_command(mounts_list)
mounts_command.add_command(mounts_add)
mounts_command.add_command(mounts_remove)
mounts_command.add_command(mounts_populate)
