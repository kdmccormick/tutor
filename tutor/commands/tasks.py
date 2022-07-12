import shlex
import typing as t

import click

from .. import config as tutor_config
from .. import fmt, hooks
from ..jobs import BaseJobRunner
from .context import BaseJobContext


class RunTaskContextObject:
    """
    A Click context object that bundles a Tutor BaseJobContext together with
    any options (eg, limit_to) that need to passed down to the task subcommands.
    """

    def __init__(self, job_context: BaseJobContext, limit_to: str):
        self.job_context = job_context
        self.limit_to = limit_to


@hooks.Actions.CORE_READY.add()
def _add_core_tasks() -> None:
    """
    Declare core tasks at runtime.

    The context is important, because it allows us to select the init scripts based on
    the --limit argument.
    """
    with hooks.Contexts.APP("lms").enter():
        hooks.Filters.CLI_TASKS.add_items(
            [
                (
                    "pre-init",
                    "Tasks that should run before initialisation",
                    [],
                ),
                (
                    "init",
                    "Initialise all applications.",
                    [("lms", ("tasks", "lms", "init"))],
                ),
                (
                    "createuser",
                    (
                        "Create an Open edX user and set their password. "
                        "If you do not supply a --password, you will be prompted for it. "
                        "Usage: createuser USERNAME EMAIL [--password PASSWORD] [--staff] [--superuser]"
                    ),
                    [("lms", ("tasks", "lms", "createuser"))],
                ),
                (
                    "settheme",
                    (
                        "Assign a theme to the LMS and the CMS. "
                        "To reset to the default theme, use 'default' as the theme name. "
                        "Theme is limited to supplied domain names. "
                        "By default, the theme is applied to the LMS and the CMS, "
                        "both in development and production mode. "
                        "Usage: setthem THEME (--domain DOMAIN)+"
                    ),
                    [("lms", ("tasks", "lms", "settheme"))],
                ),
            ]
        )
    with hooks.Contexts.APP("cms").enter():
        hooks.Filters.CLI_TASKS.add_items(
            [
                (
                    "init",
                    None,
                    [("cms", ("tasks", "cms", "init"))],
                ),
                (
                    "importdemocourse",
                    "Import the demo course",
                    [("cms", ("tasks", "cms", "importdemocourse"))],
                ),
            ]
        )
    with hooks.Contexts.APP("mysql").enter():
        hooks.Filters.CLI_TASKS.add_items(
            [
                (
                    "init",
                    None,
                    [("mysql", ("tasks", "mysql", "init"))],
                ),
            ],
        )


def add_tasks_as_subcommands(command_group: click.Group) -> None:
    """
    Add subcommands to `command_group` for handling tasks as defined in CLI_TASKS.
    """
    tasks: t.List[
        t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]
    ] = _get_cli_tasks()

    # Generate mapping of task names to helptexts.
    # In the event that multiple CLI_TASKS entries have the same name,
    # take the helptext of the first entry.
    task_name_helptext: t.Dict[str, str] = {}
    for name, helptext, _service_commands in tasks:
        if name not in task_name_helptext:
            task_name_helptext[name] = helptext

    # Add tasks as subcommands, in alphabetical order by name.
    for name, helptext in sorted(task_name_helptext.items()):
        _add_task_as_subcommand(command_group, name, helptext)


def _add_task_as_subcommand(
    command_group: click.Group, task_name: str, helptext: str
) -> None:
    """
    Add a single subcommand to `command_group` for handling `task_name`, as defined in CLI_TASKS.
    """

    @command_group.command(
        name=task_name, help=helptext, context_settings={"ignore_unknown_options": True}
    )
    @click.pass_obj
    @click.argument("args", nargs=-1)
    def _task_handler(obj: RunTaskContextObject, args: t.List[str]) -> None:
        """
        Handle a particular subcommand invocation by running the corresponding task.
        """
        config = tutor_config.load(obj.job_context.root)
        runner = obj.job_context.job_runner(config)
        run_task(runner=runner, task_name=task_name, limit_to=obj.limit_to, args=args)


def run_task(
    runner: BaseJobRunner,
    task_name: str,
    limit_to: str = "",
    args: t.Optional[t.List[str]] = None,
) -> None:
    """
    Run a task defined by CLI_TASKS within job containers.
    """
    # Special case: If running 'init' task, run the 'pre-init'
    # task first.
    if task_name == "init":
        run_task(runner, "pre-init", limit_to, args)
    args = args or []

    tasks: t.List[
        t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]
    ] = _get_cli_tasks(limit_to)

    # For each task, for each service/path handler, render the script at `path`
    # and then run it in `service` and pass it any additional `args`.
    for name, _helptext, service_commands in tasks:
        if name != task_name:
            continue
        for service, path in service_commands:
            command = shlex.join(["sh", "-c", runner.render(*path), "--", *args])
            runner.run_job(service, command)


def add_deprecated_task_alias(
    parent_group: click.Group,
    parent_command_text: str,  # TODO is there a less hacky way to do this?
    do_group: click.Group,
    task_name: str,
) -> None:
    """
    TODO add docstring
    """
    old_command_spelling = f"{parent_command_text} {task_name}"
    new_command_spelling = f"{parent_command_text} do {task_name}"

    @parent_group.command(
        name=task_name,
        help=f"DEPRECATED: Use '{new_command_spelling}' instead!",
        context_settings={"ignore_unknown_options": True},
    )
    @click.pass_context
    @click.option(
        "-l",
        "--limit",
        help="Limit scope of task execution. Valid values: lms, cms, mysql, or a plugin name.",
    )
    def _handle_deprecated_task_alias(
        context: click.Context,
        limit: str,
    ) -> None:
        do_task_command: click.Command = do_group.get_command(context, task_name)  # type: ignore
        fmt.echo_alert(
            f"""'{old_command_spelling}' has been renamed to '{new_command_spelling}'.
   '{old_command_spelling}' (without 'do') will stop working in a future release."""
        )
        context.obj = RunTaskContextObject(job_context=context.obj, limit_to=limit)
        context.invoke(do_task_command)


def _get_cli_tasks(
    limit_to: t.Optional[str] = None,
) -> t.List[t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]]:
    """
    Apply the CLI_TASKS filter, adding in COMAMNDS[_PRE]_INIT for backwards compatibility.
    """
    # Execution may be limited to:
    #   * a core app, specifically 'lms', 'cms', or 'mysql'; or
    #   * any plugin.
    # If limited, we will only run commands defined within that context.
    limited_context = hooks.Contexts.APP(limit_to).name if limit_to else None
    tasks: t.List[t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]] = list(
        hooks.Filters.CLI_TASKS.iterate(context=limited_context)
    )
    init_tasks: t.List[t.Tuple[str, t.Tuple[str, ...]]] = list(
        hooks.Filters.COMMANDS_INIT.iterate(context=limited_context)
    )
    tasks.append(("init", "", init_tasks))
    pre_init_tasks: t.List[t.Tuple[str, t.Tuple[str, ...]]] = list(
        hooks.Filters.COMMANDS_PRE_INIT.iterate(context=limited_context)
    )
    tasks.append(("pre-init", "", pre_init_tasks))
    return tasks
