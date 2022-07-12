import typing as t

import click

from .. import config as tutor_config
from .. import hooks
from ..jobs import BaseJobRunner
from .context import BaseJobContext


@click.group(
    name="do",
    help="Run a predefined task in new containers",
    subcommand_metavar="TASKNAME [ARGS] ...",
)
def do_command() -> None:
    """
    A command group for predefined tasks: `tutor (dev|local|k8s) do TASKNAME ARGS`

    Subcommands will be populated dynamically based on the CLI_TASKS filter.
    """
    # TODO: We need to call process_mount_arguments here.
    # Because that doesn't apply in k8s mode, we will probably need
    # separate versions of do_command() for compose and k8s, although
    # we can still use shared implementations for ``_add_tasks_to_do_command``
    # as well as ``_run_task``.
    pass


# Add built-in tasks to CLI_TASKS.
hooks.Filters.CLI_TASKS.add_items(
    [
        (
            "importdemocourse",
            "Import the demo course",
            [("cms", ("hooks", "cms", "importdemocourse"))],
        )
    ]
)


@hooks.Actions.PLUGINS_LOADED.add()
def _add_tasks_to_do_command() -> None:
    """
    Dynamically populate the 'do' command group based on CLI_TASKS.

    We do this after plugins are loaded to ensure that all plugins have had a chance
    to add their entries to CLI_TASKS.
    """
    tasks: t.Iterable[
        t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]
    ] = hooks.Filters.CLI_TASKS.iterate()

    # Generate mapping of task names to helptexts.
    # In the event that multiple CLI_TASKS entries have the same name,
    # take the helptext of the first entry.
    task_name_helptext: t.Dict[str, str] = {}
    for name, helptext, _service_commands in tasks:
        if name not in task_name_helptext:
            task_name_helptext[name] = helptext

    # Add tasks as subcommands, in alphabetical order by name.
    for name, helptext in sorted(task_name_helptext.items()):

        @do_command.command(
            name=name, help=helptext, context_settings={"ignore_unknown_options": True}
        )
        @click.pass_obj
        @click.option(
            "-l",
            "--limit",
            help="Limit scope of task execution. Valid values: lms, cms, mysql, or a plugin name.",
        )
        @click.argument("args", nargs=-1)
        def _do_subcommand(
            context: BaseJobContext, limit: str, args: t.List[str]
        ) -> None:
            """
            Handle a particular 'do' subcommand invocation by running the corresponding task.
            """
            config = tutor_config.load(context.root)
            runner = context.job_runner(config)
            _run_task(runner=runner, name=name, limit_to=limit, args=args)


def _run_task(
    runner: BaseJobRunner,
    name: str,
    limit_to: str = "",
    args: t.Optional[t.List[str]] = None,
) -> None:
    """
    Run a task defined by CLI_TASKS within job containers.
    """

    # Execution may be limited to:
    #   * a core app, specifically 'lms', 'cms', or 'mysql'; or
    #   * any plugin.
    # If limited, we will only run commands defined within that context.
    limited_context = hooks.Contexts.APP(limit_to).name if limit_to else None
    tasks: t.List[t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]] = list(
        hooks.Filters.CLI_TASKS.iterate(context=limited_context)
    )

    # For each task, for each service/path handler, render the script at `path`
    # and then run it in `service` and pass it any additional `args`.
    args_str = (" " + " ".join(args)) if args else ""
    for task_name, _task_helptext, task_service_commands in tasks:
        if task_name != name:
            continue
        for service, path in task_service_commands:
            base_command = runner.render(*path)
            runner.run_job(service, base_command + args_str)
