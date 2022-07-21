import shlex
import typing as t

import click

from .. import config as tutor_config
from .. import hooks
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


# Add built-in tasks to CLI_TASKS.
with hooks.Contexts.APP("lms").enter():
    hooks.Filters.CLI_TASKS.add_items(
        [
            (
                "createuser",
                "Create and LMS user (TODO expand on this)",
                [("lms", ("hooks", "lms", "createuser"))],
            )
        ]
    )
with hooks.Contexts.APP("cms").enter():
    hooks.Filters.CLI_TASKS.add_items(
        [
            (
                "importdemocourse",
                "Import the demo course",
                [("cms", ("hooks", "cms", "importdemocourse"))],
            )
        ]
    )


def add_tasks_as_subcommands(command_group: click.Group) -> None:
    """
    Add subcommands to `command_group` for handling tasks as defined in CLI_TASKS.
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
    args = args or []

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
    for name, _helptext, service_commands in tasks:
        if name != task_name:
            continue
        for service, path in service_commands:
            command = shlex.join(["sh", "-c", runner.render(*path), "--", *args])
            runner.run_job(service, command)
