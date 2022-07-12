import typing as t

import click

from .. import config as tutor_config
from .. import hooks
from ..jobs import run_task
from .context import BaseJobContext


@click.group(name="do", help="Do a task", subcommand_metavar="TASKNAME [ARGS] ...")
def do_command() -> None:
    pass


@hooks.Actions.PLUGINS_LOADED.add()
def _add_tasks_to_do_command() -> None:
    tasks: t.Iterable[
        t.Tuple[str, str, t.List[t.Tuple[str, str]]]
    ] = hooks.Filters.CLI_TASKS.iterate()

    task_name_helptext: t.Dict[str, str] = {}
    for name, helptext, _service_commands in tasks:
        # In the that CLI_TASKS returns multiple entries with the same
        # name, take the helptext of the first entry.
        if name not in task_name_helptext:
            task_name_helptext[name] = helptext

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
        def _do_task_command(
            context: BaseJobContext, limit: str, args: t.List[str]
        ) -> None:
            config = tutor_config.load(context.root)
            runner = context.job_runner(config)
            run_task(runner=runner, name=name, limit_to=limit, args=args)
