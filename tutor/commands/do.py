import typing as t

import click

from .. import config as tutor_config
from .. import fmt, hooks
from . import context


class DoJobCommandContext:
    """
    A Click context object for bundling a Tutor BaseJobContext together with
    any options (eg, limit_to) that need to passed down to the job subcommands.
    """

    def __init__(self, job_context: context.BaseJobContext, limit_to: str):
        self.job_context = job_context
        self.limit_to = limit_to


def add_jobs_as_subcommands(command_group: click.Group) -> None:
    """
    Add a subcommand to `command_group` for each job defined in JOB_TASKS.
    """
    # Generate mapping of job names to helptexts.
    # If a job in JOB_TASKS has no helptext defined, use an empty string.
    # If a job has multiple helptexts defined, use the latest one.
    job_tasks: t.List[t.Tuple[str, str, t.Tuple[str, ...]]] = list(
        hooks.Filters.JOB_TASKS.iterate()
    )
    job_helptexts: t.List[t.Tuple[str, str]] = list(
        hooks.Filters.JOB_HELPTEXTS.iterate()
    )
    helptexts_by_job: t.Dict[str, str] = {}
    for name, _, __ in job_tasks:
        helptexts_by_job[name] = ""
    for name, helptext in job_helptexts:
        helptexts_by_job[name] = helptext

    # Add jobs as subcommands, in alphabetical order by name.
    for name, helptext in sorted(helptexts_by_job.items()):
        _add_job_as_subcommand(command_group, name, helptext)


def _add_job_as_subcommand(
    command_group: click.Group, job_name: str, helptext: str
) -> None:
    """
    Add a single subcommand to `command_group` for handling `job_name`.
    """

    @command_group.command(
        name=job_name, help=helptext, context_settings={"ignore_unknown_options": True}
    )
    @click.pass_obj
    @click.argument("args", nargs=-1)
    def _job_handler(obj: DoJobCommandContext, args: t.Tuple[str]) -> None:
        """
        Handle a particular subcommand invocation by running the corresponding task.
        """
        config = tutor_config.load(obj.job_context.root)
        runner = obj.job_context.job_runner(config)
        runner.run_job(
            job_name=job_name,
            limit_to=obj.limit_to,
            extra_args=args,
        )


def add_deprecated_job_alias(
    parent_group: click.Group,
    parent_command_text: str,  # TODO is there a less hacky way to do this?
    do_group: click.Group,
    job_name: str,
) -> None:
    """
    TODO add docstring
    """
    old_command_spelling = f"{parent_command_text} {job_name}"
    new_command_spelling = f"{parent_command_text} do {job_name}"

    @parent_group.command(
        name=job_name,
        help=f"DEPRECATED: Use '{new_command_spelling}' instead!",
        context_settings={"ignore_unknown_options": True},
    )
    @click.pass_context
    @click.option(
        "-l",
        "--limit",
        help="Limit scope of job execution. Valid values: lms, cms, mysql, or a plugin name.",
    )
    def _handle_deprecated_job_alias(
        context: click.Context,
        limit: str,
    ) -> None:
        do_job_command: click.Command = do_group.get_command(context, job_name)  # type: ignore
        fmt.echo_alert(
            f"""'{old_command_spelling}' has been renamed to '{new_command_spelling}'.
   '{old_command_spelling}' (without 'do') will stop working in a future release."""
        )
        context.obj = DoJobCommandContext(job_context=context.obj, limit_to=limit)
        context.invoke(do_job_command)
