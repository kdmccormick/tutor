import typing as t

from tutor import env, exceptions, hooks, fmt, utils
from tutor.types import Config


class BaseJobRunner:
    """
    A job runner is responsible for running tasks or sets of tasks.

    A task is a command to be run in a particular service container.
    """

    def __init__(self, root: str, config: Config):
        self.root = root
        self.config = config

    def render(self, *path: str) -> str:
        rendered = env.render_file(self.config, *path).strip()
        if isinstance(rendered, bytes):
            raise TypeError("Cannot load task from binary file")
        return rendered

    def run_task(self, service: str, command: str) -> int:
        """
        Given a (potentially large) string command, run it with the
        corresponding service. Implementations will differ depending on the
        deployment strategy.
        """
        raise NotImplementedError

    def run_job(
        self,
        job_name: str,
        limit_to: str = "",
        extra_args: t.Tuple[str, ...] = (),
        job_call_stack: t.Optional[t.List[str]] = None,
    ) -> None:
        """
        Run a job defined by JOB_TASKS within job containers.
        """

        # Call prequisite jobs.
        # Avoid infinite recursion by using `job_task` to detect prereq cycles.
        job_prereqs: t.List[t.Tuple[str, str]] = list(
            hooks.Filters.JOB_PREREQS.iterate()
        )
        for name, prereq_name in job_prereqs:
            if name == job_name:
                if job_call_stack and job_name in job_call_stack:
                    raise exceptions.TutorError(
                        "Cyclic job prerequisite detected between "
                        f"{job_name!r} and {prereq_name!r}. "
                        + "Job call chain: "
                        + "->".join(job_call_stack)
                        + f"->{job_name}"
                    )
                self.run_job(
                    job_name=prereq_name,
                    limit_to=limit_to,
                    extra_args=extra_args,  # TODO: should we pass extra args down?
                    job_call_stack=((job_call_stack or []) + [job_name]),
                )

        # Get tasks for this job.
        # Execution may be limited to:
        #   * a core app, specifically 'lms', 'cms', or 'mysql'; or
        #   * any plugin.
        # If limited, we will only run tasks defined within that context.
        limited_context = hooks.Contexts.APP(limit_to).name if limit_to else None
        job_tasks: t.List[t.Tuple[str, str, t.Tuple[str, ...]]] = list(
            hooks.Filters.JOB_TASKS.iterate(context=limited_context)
        )
        tasks: t.List[t.Tuple[str, t.Tuple[str, ...]]] = [
            (task_service, task_command)
            for name, task_service, task_command in job_tasks
            if name == job_name
        ]

        # Backwards compatibility:
        # If we're running init or pre-init, then load up additional
        # tasks from the old COMMANDS[_PRE]_INIT filters.
        # Unlike JOB_TASKS, these commands are provided as paths to templates files,
        # so we must render them into proper shell commands.
        compat_tasks: t.List[t.Tuple[str, t.Tuple[str, ...]]]
        if job_name == "init":
            compat_tasks = list(
                hooks.Filters.COMMANDS_INIT.iterate(context=limited_context)
            )
        elif job_name == "pre-init":
            compat_tasks = list(
                hooks.Filters.COMMANDS_PRE_INIT.iterate(context=limited_context)
            )
        else:
            compat_tasks = []
        for service, path in compat_tasks:
            rendered_command: str = self.render(*path)
            tasks.append((service, ("sh", "-c", rendered_command)))

        # Run tasks.
        fmt.echo(f"Running {len(tasks)} task(s) for job {job_name!r}.")
        for service, command in tasks:
            command_string = utils.shlex_join(*command, *extra_args)
            self.run_task(service, command_string)


class BaseComposeJobRunner(BaseJobRunner):
    def docker_compose(self, *command: str) -> int:
        raise NotImplementedError


@hooks.Actions.CORE_READY.add()
def _add_core_jobs() -> None:
    """
    Declare core jobs at runtime.

    The context is important, because it allows us to select the init scripts based on
    the --limit argument.
    """
    hooks.Filters.JOB_HELPTEXTS.add_items(
        [
            (
                "pre-init",
                "Jobs that should run before initialisation",
            ),
            (
                "init",
                "Initialise all applications.",
            ),
            (
                "createuser",
                (
                    "Create an Open edX user and set their password. "
                    "If you do not supply a --password, you will be prompted for it. "
                    "Usage: createuser USERNAME EMAIL [--password PASSWORD] [--staff] [--superuser]"
                ),
            ),
            (
                "importdemocourse",
                "Import the demo course",
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
            ),
        ]
    )
    hooks.Filters.JOB_PREREQS.add_items(
        [
            ("init", "pre-init"),
        ]
    )
    with hooks.Contexts.APP("lms").enter():
        hooks.Filters.JOB_TASKS.add_items(
            [
                (
                    "init",
                    "lms",
                    ("sh", "/openedx/tasks/openedx/lms/init"),
                ),
                (
                    "createuser",
                    "lms",
                    ("sh", "/openedx/tasks/openedx/lms/createuser"),
                ),
                (
                    "settheme",
                    "lms",
                    ("sh", "/openedx/tasks/openedx/lms/settheme"),
                ),
            ]
        )
    with hooks.Contexts.APP("cms").enter():
        hooks.Filters.JOB_TASKS.add_items(
            [
                (
                    "init",
                    "cms",
                    ("sh", "/openedx/tasks/openedx/cms/init"),
                ),
                (
                    "importdemocourse",
                    "cms",
                    ("sh", "/openedx/tasks/openedx/cms/importdemocourse"),
                ),
            ]
        )
    with hooks.Contexts.APP("mysql").enter():
        hooks.Filters.JOB_TASKS.add_items(
            [
                (
                    "init",
                    "mysql",
                    ("sh", "/openedx/tasks/openedx/mysql/init"),
                ),
            ],
        )
