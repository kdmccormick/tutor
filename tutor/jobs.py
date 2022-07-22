import typing as t

from tutor import env, fmt, hooks
from tutor.types import Config, get_typed


class BaseJobRunner:
    """
    A job runner is responsible for getting a certain task to complete.
    """

    def __init__(self, root: str, config: Config):
        self.root = root
        self.config = config

    def run_job_from_template(self, service: str, *path: str) -> None:
        command = self.render(*path)
        self.run_job(service, command)

    def render(self, *path: str) -> str:
        rendered = env.render_file(self.config, *path).strip()
        if isinstance(rendered, bytes):
            raise TypeError("Cannot load job from binary file")
        return rendered

    def run_job(self, service: str, command: str) -> int:
        """
        Given a (potentially large) string command, run it with the
        corresponding service. Implementations will differ depending on the
        deployment strategy.
        """
        raise NotImplementedError


class BaseComposeJobRunner(BaseJobRunner):
    def docker_compose(self, *command: str) -> int:
        raise NotImplementedError


@hooks.Actions.CORE_READY.add()
def _add_core_init_tasks() -> None:
    """
    Declare core init scripts at runtime.

    The context is important, because it allows us to select the init scripts based on
    the --limit argument.
    """
    with hooks.Contexts.APP("mysql").enter():
        hooks.Filters.COMMANDS_INIT.add_item(("mysql", ("hooks", "mysql", "init")))
    with hooks.Contexts.APP("lms").enter():
        hooks.Filters.COMMANDS_INIT.add_item(("lms", ("hooks", "lms", "init")))
    with hooks.Contexts.APP("cms").enter():
        hooks.Filters.COMMANDS_INIT.add_item(("cms", ("hooks", "cms", "init")))


def initialise(runner: BaseJobRunner, limit_to: t.Optional[str] = None) -> None:
    fmt.echo_info("Initialising all services...")
    filter_context = hooks.Contexts.APP(limit_to).name if limit_to else None

    # Pre-init tasks
    iter_pre_init_tasks: t.Iterator[
        t.Tuple[str, t.Iterable[str]]
    ] = hooks.Filters.COMMANDS_PRE_INIT.iterate(context=filter_context)
    for service, path in iter_pre_init_tasks:
        fmt.echo_info(f"Running pre-init task: {'/'.join(path)}")
        runner.run_job_from_template(service, *path)

    # Init tasks
    iter_init_tasks: t.Iterator[
        t.Tuple[str, t.Iterable[str]]
    ] = hooks.Filters.COMMANDS_INIT.iterate(context=filter_context)
    for service, path in iter_init_tasks:
        fmt.echo_info(f"Running init task: {'/'.join(path)}")
        runner.run_job_from_template(service, *path)

    fmt.echo_info("All services initialised.")


def get_all_openedx_domains(config: Config) -> t.List[str]:
    return [
        get_typed(config, "LMS_HOST", str),
        get_typed(config, "LMS_HOST", str) + ":8000",
        get_typed(config, "CMS_HOST", str),
        get_typed(config, "CMS_HOST", str) + ":8001",
        get_typed(config, "PREVIEW_LMS_HOST", str),
        get_typed(config, "PREVIEW_LMS_HOST", str) + ":8000",
    ]
