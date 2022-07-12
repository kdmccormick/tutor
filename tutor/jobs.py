import typing as t

from tutor import env, fmt, hooks
from tutor.exceptions import TutorError
from tutor.types import Config, get_typed

BASE_OPENEDX_COMMAND = """
echo "Loading settings $DJANGO_SETTINGS_MODULE"
"""


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


def run_task(
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
    tasks: t.Iterable[
        t.Tuple[str, str, t.List[t.Tuple[str, t.Tuple[str, ...]]]]
    ] = hooks.Filters.CLI_TASKS.iterate(context=limited_context)

    # In the unexpected case where a task has no handlers, fail loudly.
    if name not in set(task[0] for task in tasks):
        raise TutorError(f"No CLI_TASKS are defined for '{name}'")

    # For each task, for each service/path handler, render the script at `path`
    # and then run it in `service` and pass it any additional `args`.
    args_str = (" " + " ".join(args)) if args else ""
    for task_name, _task_helptext, task_service_commands in tasks:
        if task_name != name:
            continue
        for service, path in task_service_commands:
            base_command = runner.render(*path)
            runner.run_job(service, base_command + args_str)


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


def create_user_command(
    superuser: str,
    staff: bool,
    username: str,
    email: str,
    password: t.Optional[str] = None,
) -> str:
    command = BASE_OPENEDX_COMMAND

    opts = ""
    if superuser:
        opts += " --superuser"
    if staff:
        opts += " --staff"
    command += """
./manage.py lms manage_user {opts} {username} {email}
"""
    if password:
        command += """
./manage.py lms shell -c "from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='{username}')
u.set_password('{password}')
u.save()"
"""
    else:
        command += """
./manage.py lms changepassword {username}
"""

    return command.format(opts=opts, username=username, email=email, password=password)


def set_theme(
    theme_name: str, domain_names: t.List[str], runner: BaseJobRunner
) -> None:
    """
    For each domain, get or create a Site object and assign the selected theme.
    """
    if not domain_names:
        return
    python_code = "from django.contrib.sites.models import Site"
    for domain_name in domain_names:
        if len(domain_name) > 50:
            fmt.echo_alert(
                "Assigning a theme to a site with a long (> 50 characters) domain name."
                " The displayed site name will be truncated to 50 characters."
            )
        python_code += """
print('Assigning theme {theme_name} to {domain_name}...')
site, _ = Site.objects.get_or_create(domain='{domain_name}')
if not site.name:
    name_max_length = Site._meta.get_field('name').max_length
    name = '{domain_name}'[:name_max_length]
    site.name = name
    site.save()
site.themes.all().delete()
site.themes.create(theme_dir_name='{theme_name}')
""".format(
            theme_name=theme_name, domain_name=domain_name
        )
    command = BASE_OPENEDX_COMMAND + f'./manage.py lms shell -c "{python_code}"'
    runner.run_job("lms", command)


def get_all_openedx_domains(config: Config) -> t.List[str]:
    return [
        get_typed(config, "LMS_HOST", str),
        get_typed(config, "LMS_HOST", str) + ":8000",
        get_typed(config, "CMS_HOST", str),
        get_typed(config, "CMS_HOST", str) + ":8001",
        get_typed(config, "PREVIEW_LMS_HOST", str),
        get_typed(config, "PREVIEW_LMS_HOST", str) + ":8000",
    ]
