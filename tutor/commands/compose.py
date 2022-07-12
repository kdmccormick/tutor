import os
import re
import typing as t

import click

from tutor import bindmounts
from tutor import config as tutor_config
from tutor import env as tutor_env
from tutor import fmt, hooks, jobs, serialize, utils
from tutor.commands.context import BaseJobContext
from tutor.exceptions import TutorError
from tutor.types import Config


class ComposeJobRunner(jobs.BaseComposeJobRunner):
    def __init__(self, root: str, config: Config):
        super().__init__(root, config)
        self.project_name = ""
        self.docker_compose_files: t.List[str] = []
        self.docker_compose_job_files: t.List[str] = []
        self.docker_compose_tmp_path = ""
        self.docker_compose_jobs_tmp_path = ""

    def docker_compose(self, *command: str) -> int:
        """
        Run docker-compose with the right yml files.
        """
        if "start" in command or "up" in command or "restart" in command:
            # Note that we don't trigger the action on "run". That's because we
            # don't want to trigger the action for every initialization script.
            hooks.Actions.COMPOSE_PROJECT_STARTED.do(
                self.root, self.config, self.project_name
            )
        self.__update_docker_compose_tmp()
        args = []
        for docker_compose_path in self.docker_compose_files:
            if os.path.exists(docker_compose_path):
                args += ["-f", docker_compose_path]
        return utils.docker_compose(
            *args, "--project-name", self.project_name, *command
        )

    def __update_docker_compose_tmp(self) -> None:
        """
        Update the contents of the docker-compose.tmp.yml file, which is generated at runtime.
        """
        docker_compose_tmp = {
            "version": "{{ DOCKER_COMPOSE_VERSION }}",
            "services": {},
        }
        docker_compose_jobs_tmp = {
            "version": "{{ DOCKER_COMPOSE_VERSION }}",
            "services": {},
        }
        docker_compose_tmp = hooks.Filters.COMPOSE_LOCAL_TMP.apply(docker_compose_tmp)
        docker_compose_jobs_tmp = hooks.Filters.COMPOSE_LOCAL_JOBS_TMP.apply(
            docker_compose_jobs_tmp
        )
        docker_compose_tmp = tutor_env.render_unknown(self.config, docker_compose_tmp)
        docker_compose_jobs_tmp = tutor_env.render_unknown(
            self.config, docker_compose_jobs_tmp
        )
        tutor_env.write_to(
            serialize.dumps(docker_compose_tmp),
            self.docker_compose_tmp_path,
        )
        tutor_env.write_to(
            serialize.dumps(docker_compose_jobs_tmp),
            self.docker_compose_jobs_tmp_path,
        )

    def run_job(self, service: str, command: str) -> int:
        """
        Run the "{{ service }}-job" service from local/docker-compose.jobs.yml with the
        specified command.
        """
        run_command = []
        for docker_compose_path in self.docker_compose_job_files:
            path = tutor_env.pathjoin(self.root, docker_compose_path)
            if os.path.exists(path):
                run_command += ["-f", path]
        run_command += ["run", "--rm"]
        if not utils.is_a_tty():
            run_command += ["-T"]
        job_service_name = f"{service}-job"
        return self.docker_compose(
            *run_command,
            job_service_name,
            "sh",
            "-e",
            "-c",
            command,
        )


class BaseComposeContext(BaseJobContext):
    def job_runner(self, config: Config) -> ComposeJobRunner:
        raise NotImplementedError


class MountParam(click.ParamType):
    """
    Parser for --mount arguments of the form "service1[,service2,...]:/host/path:/container/path".
    """

    name = "mount"
    MountType = t.Tuple[str, str, str]
    # Note that this syntax does not allow us to include colon ':' characters in paths
    PARAM_REGEXP = (
        r"(?P<services>[a-zA-Z0-9-_, ]+):(?P<host_path>[^:]+):(?P<container_path>[^:]+)"
    )

    def convert(
        self,
        value: str,
        param: t.Optional["click.Parameter"],
        ctx: t.Optional[click.Context],
    ) -> t.List["MountType"]:
        mounts: t.List["MountParam.MountType"] = []
        match = re.match(self.PARAM_REGEXP, value)
        if match:
            # Argument is of the form "containers:/host/path:/container/path"
            services: t.List[str] = [
                service.strip() for service in match["services"].split(",")
            ]
            host_path = os.path.abspath(os.path.expanduser(match["host_path"]))
            host_path = host_path.replace(os.path.sep, "/")
            container_path = match["container_path"]
            for service in services:
                if not service:
                    self.fail(
                        f"incorrect services syntax: '{match['services']}'", param, ctx
                    )
                mounts.append((service, host_path, container_path))
        else:
            # Argument is of the form "/host/path"
            host_path = os.path.abspath(os.path.expanduser(value))
            volumes: t.Iterator[
                t.Tuple[str, str]
            ] = hooks.Filters.COMPOSE_MOUNTS.iterate(os.path.basename(host_path))
            for service, container_path in volumes:
                mounts.append((service, host_path, container_path))
        if not mounts:
            raise self.fail(f"no mount found for {value}", param, ctx)
        return mounts


mount_option = click.option(
    "-m",
    "--mount",
    "mounts",
    help="""Bind-mount a folder from the host in the right containers. This option can take two different forms. The first one is explicit: 'service1[,service2...]:/host/path:/container/path'. The other is implicit: '/host/path'. Arguments passed in the implicit form will be parsed by plugins to define the right folders to bind-mount from the host.""",
    type=MountParam(),
    multiple=True,
)


@click.command(
    short_help="Run all or a selection of services.",
    help="Run all or a selection of services. Docker images will be rebuilt where necessary.",
)
@click.option("--skip-build", is_flag=True, help="Skip image building")
@click.option("-d", "--detach", is_flag=True, help="Start in daemon mode")
@mount_option
@click.argument("services", metavar="service", nargs=-1)
@click.pass_obj
def start(
    context: BaseComposeContext,
    skip_build: bool,
    detach: bool,
    mounts: t.Tuple[t.List[MountParam.MountType]],
    services: t.List[str],
) -> None:
    command = ["up", "--remove-orphans"]
    if not skip_build:
        command.append("--build")
    if detach:
        command.append("-d")

    process_mount_arguments(mounts)

    # Start services
    config = tutor_config.load(context.root)
    context.job_runner(config).docker_compose(*command, *services)


@click.command(help="Stop a running platform")
@click.argument("services", metavar="service", nargs=-1)
@click.pass_obj
def stop(context: BaseComposeContext, services: t.List[str]) -> None:
    config = tutor_config.load(context.root)
    context.job_runner(config).docker_compose("stop", *services)


@click.command(
    short_help="Reboot an existing platform",
    help="This is more than just a restart: with reboot, the platform is fully stopped before being restarted again",
)
@click.option("-d", "--detach", is_flag=True, help="Start in daemon mode")
@click.argument("services", metavar="service", nargs=-1)
@click.pass_context
def reboot(context: click.Context, detach: bool, services: t.List[str]) -> None:
    context.invoke(stop, services=services)
    context.invoke(start, detach=detach, services=services)


@click.command(
    short_help="Restart some components from a running platform.",
    help="""Specify 'openedx' to restart the lms, cms and workers, or 'all' to
restart all services. Note that this performs a 'docker-compose restart', so new images
may not be taken into account. It is useful for reloading settings, for instance. To
fully stop the platform, use the 'reboot' command.""",
)
@click.argument("services", metavar="service", nargs=-1)
@click.pass_obj
def restart(context: BaseComposeContext, services: t.List[str]) -> None:
    config = tutor_config.load(context.root)
    command = ["restart"]
    if "all" in services:
        pass
    else:
        for service in services:
            if service == "openedx":
                if config["RUN_LMS"]:
                    command += ["lms", "lms-worker"]
                if config["RUN_CMS"]:
                    command += ["cms", "cms-worker"]
            else:
                command.append(service)
    context.job_runner(config).docker_compose(*command)


@click.command(help="Initialise all applications")
@click.option("-l", "--limit", help="Limit initialisation to this service or plugin")
@mount_option
@click.pass_obj
def init(
    context: BaseComposeContext,
    limit: str,
    mounts: t.Tuple[t.List[MountParam.MountType]],
) -> None:
    process_mount_arguments(mounts)
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    jobs.initialise(runner, limit_to=limit)


@click.command(help="Create an Open edX user and interactively set their password")
@click.option("--superuser", is_flag=True, help="Make superuser")
@click.option("--staff", is_flag=True, help="Make staff user")
@click.option(
    "-p",
    "--password",
    help="Specify password from the command line. If undefined, you will be prompted to input a password",
)
@click.argument("name")
@click.argument("email")
@click.pass_obj
def createuser(
    context: BaseComposeContext,
    superuser: str,
    staff: bool,
    password: str,
    name: str,
    email: str,
) -> None:
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    command = jobs.create_user_command(superuser, staff, name, email, password=password)
    runner.run_job("lms", command)


@click.command(
    help="Assign a theme to the LMS and the CMS. To reset to the default theme , use 'default' as the theme name."
)
@click.option(
    "-d",
    "--domain",
    "domains",
    multiple=True,
    help=(
        "Limit the theme to these domain names. By default, the theme is "
        "applied to the LMS and the CMS, both in development and production mode"
    ),
)
@click.argument("theme_name")
@click.pass_obj
def settheme(
    context: BaseComposeContext, domains: t.List[str], theme_name: str
) -> None:
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    domains = domains or jobs.get_all_openedx_domains(config)
    jobs.set_theme(theme_name, domains, runner)


@click.command(help="Import the demo course")
@click.pass_obj
def importdemocourse(context: BaseComposeContext) -> None:
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    fmt.echo_info("Importing demo course")
    jobs.import_demo_course(runner)


# TODO: this doesn't work; we'd need to subclass both Dev and Local
class ComposeDoContext(BaseComposeContext):
    def __init__(self, root: str, task_options: t.Dict[str, t.Any]):
        super().__init__(root)
        self.task_options = task_options


# @click.option(
#    "--list", is_flag=True, default=False, help="List available tasks and exit."
# )
@click.group(help="Do a task", subcommand_metavar="TASKNAME [ARGS] ...")
@click.pass_context
def do(context: click.Context, **options: t.Dict[str, t.Any]) -> None:
    context.obj = ComposeDoContext(root=context.obj.root, task_options=options)
    _ = """
    if options["list"]:
        tasks: t.Iterable[
            t.Tuple[str, t.List[t.Tuple[str, str]]]
        ] = hooks.Filters.CLI_TASKS.iterate()
        task_names = sorted(set(name for (name, _) in tasks))
        fmt.echo_info("Available tasks:\n\t" + "\n\t".join(task_names))
        raise click.Abort()
    if task_name not in task_names:
       raise TutorError(f"No such task: {task_name}")
    """


def _run_task(context: BaseComposeContext, task_name: str) -> None:
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    tasks: t.Iterable[
        t.Tuple[str, t.List[t.Tuple[str, str]]]
    ] = hooks.Filters.CLI_TASKS.iterate()
    for name, service_commands in tasks:
        if name != task_name:
            continue
        for service, command in service_commands:
            runner.run_job(service, command)


@hooks.Actions.PLUGINS_LOADED.add()
def _add_tasks_to_do_group() -> None:
    tasks: t.Iterable[
        t.Tuple[str, t.List[t.Tuple[str, str]]]
    ] = hooks.Filters.CLI_TASKS.iterate()
    task_names = sorted(set(name for (name, _) in tasks))
    for task_name in task_names:

        @do.command(name=task_name)
        @click.pass_obj
        def _run_the_task(context: ComposeDoContext) -> None:
            _run_task(context, task_name)


@click.command(
    short_help="Run a command in a new container",
    help=(
        "Run a command in a new container. This is a wrapper around `docker-compose run`. Any option or argument passed"
        " to this command will be forwarded to docker-compose. Thus, you may use `-v` or `-p` to mount volumes and"
        " expose ports."
    ),
    context_settings={"ignore_unknown_options": True},
)
@mount_option
@click.argument("args", nargs=-1, required=True)
@click.pass_context
def run(
    context: click.Context,
    mounts: t.Tuple[t.List[MountParam.MountType]],
    args: t.List[str],
) -> None:
    process_mount_arguments(mounts)
    extra_args = ["--rm"]
    if not utils.is_a_tty():
        extra_args.append("-T")
    context.invoke(dc_command, command="run", args=[*extra_args, *args])


@click.command(
    name="bindmount",
    help="Copy the contents of a container directory to a ready-to-bind-mount host directory",
)
@click.argument("service")
@click.argument("path")
@click.pass_obj
def bindmount_command(context: BaseComposeContext, service: str, path: str) -> None:
    """
    This command is made obsolete by the --mount arguments.
    """
    fmt.echo_alert(
        "The 'bindmount' command is deprecated and will be removed in a later release. Use 'copyfrom' instead."
    )
    config = tutor_config.load(context.root)
    host_path = bindmounts.create(context.job_runner(config), service, path)
    fmt.echo_info(
        f"Bind-mount volume created at {host_path}. You can now use it in all `local` and `dev` "
        f"commands with the `--volume={path}` option."
    )


@click.command(
    name="copyfrom",
    help="Copy files/folders from a container directory to the local filesystem.",
)
@click.argument("service")
@click.argument("container_path")
@click.argument(
    "host_path",
    type=click.Path(dir_okay=True, file_okay=False, resolve_path=True),
)
@click.pass_obj
def copyfrom(
    context: BaseComposeContext, service: str, container_path: str, host_path: str
) -> None:
    # Path management
    container_root_path = "/tmp/mount"
    container_dst_path = container_root_path
    if not os.path.exists(host_path):
        # Emulate cp semantics, where if the destination path does not exist
        # then we copy to its parent and rename to the destination folder
        container_dst_path += "/" + os.path.basename(host_path)
        host_path = os.path.dirname(host_path)
    if not os.path.exists(host_path):
        raise TutorError(
            f"Cannot create directory {host_path}. No such file or directory."
        )

    # cp/mv commands
    command = f"cp --recursive --preserve {container_path} {container_dst_path}"
    config = tutor_config.load(context.root)
    runner = context.job_runner(config)
    runner.docker_compose(
        "run",
        "--rm",
        "--no-deps",
        "--user=0",
        f"--volume={host_path}:{container_root_path}",
        service,
        "sh",
        "-e",
        "-c",
        command,
    )


@click.command(
    short_help="Run a command in a running container",
    help=(
        "Run a command in a running container. This is a wrapper around `docker-compose exec`. Any option or argument"
        " passed to this command will be forwarded to docker-compose. Thus, you may use `-e` to manually define"
        " environment variables."
    ),
    context_settings={"ignore_unknown_options": True},
    name="exec",
)
@click.argument("args", nargs=-1, required=True)
@click.pass_context
def execute(context: click.Context, args: t.List[str]) -> None:
    context.invoke(dc_command, command="exec", args=args)


@click.command(
    short_help="View output from containers",
    help="View output from containers. This is a wrapper around `docker-compose logs`.",
)
@click.option("-f", "--follow", is_flag=True, help="Follow log output")
@click.option("--tail", type=int, help="Number of lines to show from each container")
@click.argument("service", nargs=-1)
@click.pass_context
def logs(context: click.Context, follow: bool, tail: bool, service: str) -> None:
    args = []
    if follow:
        args.append("--follow")
    if tail is not None:
        args += ["--tail", str(tail)]
    args += service
    context.invoke(dc_command, command="logs", args=args)


@click.command(help="Print status information for containers")
@click.pass_context
def status(context: click.Context) -> None:
    context.invoke(dc_command, command="ps")


@click.command(
    short_help="Direct interface to docker-compose.",
    help=(
        "Direct interface to docker-compose. This is a wrapper around `docker-compose`. Most commands, options and"
        " arguments passed to this command will be forwarded as-is to docker-compose."
    ),
    context_settings={"ignore_unknown_options": True},
    name="dc",
)
@click.argument("command")
@click.argument("args", nargs=-1)
@click.pass_obj
def dc_command(context: BaseComposeContext, command: str, args: t.List[str]) -> None:
    config = tutor_config.load(context.root)
    volumes, non_volume_args = bindmounts.parse_volumes(args)
    volume_args = []
    for volume_arg in volumes:
        if ":" not in volume_arg:
            # This is a bind-mounted volume from the "volumes/" folder.
            host_bind_path = bindmounts.get_path(context.root, volume_arg)
            if not os.path.exists(host_bind_path):
                raise TutorError(
                    f"Bind-mount volume directory {host_bind_path} does not exist. It must first be created "
                    f"with the '{bindmount_command.name}' command."
                )
            volume_arg = f"{host_bind_path}:{volume_arg}"
        volume_args += ["--volume", volume_arg]
    context.job_runner(config).docker_compose(command, *volume_args, *non_volume_args)


def process_mount_arguments(mounts: t.Tuple[t.List[MountParam.MountType]]) -> None:
    """
    Process --mount arguments.

    Most docker-compose commands support --mount arguments. This option
    is used to bind-mount folders from the host. A docker-compose.tmp.yml is
    generated at runtime and includes the bind-mounted volumes that were passed as CLI
    arguments.

    Bind-mounts that are associated to "*-job" services will be added to the
    docker-compose jobs file.
    """
    app_mounts: t.List[MountParam.MountType] = []
    job_mounts: t.List[MountParam.MountType] = []
    for mount in mounts:
        for service, host_path, container_path in mount:
            if service.endswith("-job"):
                job_mounts.append((service, host_path, container_path))
            else:
                app_mounts.append((service, host_path, container_path))

    def _add_mounts(
        docker_compose: t.Dict[str, t.Any], bind_mounts: t.List[MountParam.MountType]
    ) -> t.Dict[str, t.Any]:
        services = docker_compose.setdefault("services", {})
        for service, host_path, container_path in bind_mounts:
            fmt.echo_info(f"Bind-mount: {host_path} -> {container_path} in {service}")
            services.setdefault(service, {"volumes": []})
            services[service]["volumes"].append(f"{host_path}:{container_path}")
        return docker_compose

    # Save bind-mounts
    @hooks.Filters.COMPOSE_LOCAL_TMP.add()
    def _add_mounts_to_docker_compose_tmp(
        docker_compose_tmp: t.Dict[str, t.Any]
    ) -> t.Dict[str, t.Any]:
        return _add_mounts(docker_compose_tmp, app_mounts)

    @hooks.Filters.COMPOSE_LOCAL_JOBS_TMP.add()
    def _add_mounts_to_docker_compose_jobs_tmp(
        docker_compose_tmp: t.Dict[str, t.Any]
    ) -> t.Dict[str, t.Any]:
        return _add_mounts(docker_compose_tmp, job_mounts)


@hooks.Filters.COMPOSE_MOUNTS.add()
def _mount_edx_platform(
    volumes: t.List[t.Tuple[str, str]], name: str
) -> t.List[t.Tuple[str, str]]:
    """
    When mounting edx-platform with `--mount=/path/to/edx-platform`, bind-mount the host
    repo in the lms/cms containers.
    """
    if name == "edx-platform":
        path = "/openedx/edx-platform"
        volumes += [
            ("lms", path),
            ("cms", path),
            ("lms-worker", path),
            ("cms-worker", path),
            ("lms-job", path),
            ("cms-job", path),
        ]
    return volumes


def add_commands(command_group: click.Group) -> None:
    command_group.add_command(start)
    command_group.add_command(stop)
    command_group.add_command(restart)
    command_group.add_command(reboot)
    command_group.add_command(init)
    command_group.add_command(createuser)
    command_group.add_command(importdemocourse)
    command_group.add_command(settheme)
    command_group.add_command(dc_command)
    command_group.add_command(run)
    command_group.add_command(do)
    command_group.add_command(copyfrom)
    command_group.add_command(bindmount_command)
    command_group.add_command(execute)
    command_group.add_command(logs)
    command_group.add_command(status)
