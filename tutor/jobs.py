import typing as t

from tutor import env
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


def get_all_openedx_domains(config: Config) -> t.List[str]:
    return [
        get_typed(config, "LMS_HOST", str),
        get_typed(config, "LMS_HOST", str) + ":8000",
        get_typed(config, "CMS_HOST", str),
        get_typed(config, "CMS_HOST", str) + ":8001",
        get_typed(config, "PREVIEW_LMS_HOST", str),
        get_typed(config, "PREVIEW_LMS_HOST", str) + ":8000",
    ]
