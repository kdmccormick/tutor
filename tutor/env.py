import os
import typing as t
from copy import deepcopy

import jinja2
import pkg_resources

from tutor import exceptions, fmt, hooks, plugins, utils
from tutor.__about__ import __app__, __version__
from tutor.types import Config, ConfigValue

TEMPLATES_ROOT = pkg_resources.resource_filename("tutor", "templates")
VERSION_FILENAME = "version"
BIN_FILE_EXTENSIONS = [".ico", ".jpg", ".patch", ".png", ".ttf", ".woff", ".woff2"]
JinjaFilter = t.Callable[..., t.Any]


def _prepare_environment() -> None:
    """
    Prepare environment by adding core data to filters.
    """
    # Core template targets
    hooks.Filters.ENV_TEMPLATE_TARGETS.add_items(
        [
            ("apps/", ""),
            ("build/", ""),
            ("dev/", ""),
            ("k8s/", ""),
            ("local/", ""),
            (VERSION_FILENAME, ""),
            ("kustomization.yml", ""),
        ],
    )
    # Template filters
    hooks.Filters.ENV_TEMPLATE_FILTERS.add_items(
        [
            ("common_domain", utils.common_domain),
            ("encrypt", utils.encrypt),
            ("list_if", utils.list_if),
            ("long_to_base64", utils.long_to_base64),
            ("random_string", utils.random_string),
            ("reverse_host", utils.reverse_host),
            ("rsa_private_key", utils.rsa_private_key),
        ],
    )
    # Template variables
    hooks.Filters.ENV_TEMPLATE_VARIABLES.add_items(
        [
            ("rsa_import_key", utils.rsa_import_key),
            ("HOST_USER_ID", utils.get_user_id()),
            ("TUTOR_APP", __app__.replace("-", "_")),
            ("TUTOR_VERSION", __version__),
        ],
    )


_prepare_environment()


class JinjaEnvironment(jinja2.Environment):
    loader: jinja2.BaseLoader

    def __init__(self, template_roots: t.List[str]) -> None:
        loader = jinja2.FileSystemLoader(template_roots)
        super().__init__(loader=loader, undefined=jinja2.StrictUndefined)


class Renderer:
    @classmethod
    def instance(cls: t.Type["Renderer"], config: Config) -> "Renderer":
        # Load template roots: these are required to be able to use
        # {% include .. %} directives
        template_roots = hooks.Filters.ENV_TEMPLATE_ROOTS.apply([TEMPLATES_ROOT])
        return cls(config, template_roots, ignore_folders=["partials"])

    def __init__(
        self,
        config: Config,
        template_roots: t.List[str],
        ignore_folders: t.Optional[t.List[str]] = None,
    ):
        self.config = deepcopy(config)
        self.template_roots = template_roots
        self.ignore_folders = ignore_folders or []
        self.ignore_folders.append(".git")

        # Create environment with extra filters and globals
        self.environment = JinjaEnvironment(template_roots)

        # Filters
        plugin_filters: t.Iterator[
            t.Tuple[str, JinjaFilter]
        ] = hooks.Filters.ENV_TEMPLATE_FILTERS.iterate()
        for name, func in plugin_filters:
            if name in self.environment.filters:
                fmt.echo_alert(f"Found conflicting template filters named '{name}'")
            self.environment.filters[name] = func
        self.environment.filters["walk_templates"] = self.walk_templates

        # Globals
        plugin_globals: t.Iterator[
            t.Tuple[str, JinjaFilter]
        ] = hooks.Filters.ENV_TEMPLATE_VARIABLES.iterate()
        for name, value in plugin_globals:
            if name in self.environment.globals:
                fmt.echo_alert(f"Found conflicting template variables named '{name}'")
            self.environment.globals[name] = value
        self.environment.globals["iter_values_named"] = self.iter_values_named
        self.environment.globals["patch"] = self.patch

    def iter_templates_in(self, *prefix: str) -> t.Iterable[str]:
        """
        The elements of `prefix` must contain only "/", and not os.sep.
        """
        full_prefix = "/".join(prefix)
        env_templates: t.List[str] = self.environment.loader.list_templates()
        for template in env_templates:
            if template.startswith(full_prefix) and self.is_part_of_env(template):
                yield template

    def iter_values_named(
        self,
        prefix: t.Optional[str] = None,
        suffix: t.Optional[str] = None,
        allow_empty: bool = False,
    ) -> t.Iterable[ConfigValue]:
        """
        Iterate on all config values for which the name match the given pattern.

        Note that here we only iterate on the values, not the key names. Empty
        values (those that evaluate to boolean `false`) will not be yielded, unless
        `allow_empty` is True.
        """
        for var_name, value in self.config.items():
            if prefix is not None and not var_name.startswith(prefix):
                continue
            if suffix is not None and not var_name.endswith(suffix):
                continue
            if not allow_empty and not value:
                continue
            yield value

    def walk_templates(self, subdir: str) -> t.Iterable[str]:
        """
        Iterate on the template files from `templates/<subdir>`.

        Yield:
            path: template path relative to the template root
        """
        yield from self.iter_templates_in(subdir + "/")

    def is_part_of_env(self, path: str) -> bool:
        """
        Determines whether a template should be rendered or not. Note that here we don't
        rely on the OS separator, as we are handling templates
        """
        parts = path.split("/")
        basename = parts[-1]
        is_excluded = False
        is_excluded = (
            is_excluded or basename.startswith(".") or basename.endswith(".pyc")
        )
        is_excluded = is_excluded or basename == "__pycache__"
        for ignore_folder in self.ignore_folders:
            is_excluded = is_excluded or ignore_folder in parts
        return not is_excluded

    def find_os_path(self, template_name: str) -> str:
        path = template_name.replace("/", os.sep)
        for templates_root in self.template_roots:
            full_path = os.path.join(templates_root, path)
            if os.path.exists(full_path):
                return full_path
        raise ValueError("Template path does not exist")

    def patch(self, name: str, separator: str = "\n", suffix: str = "") -> str:
        """
        Render calls to {{ patch("...") }} in environment templates from plugin patches.
        """
        patches = []
        for patch in plugins.iter_patches(name):
            try:
                patches.append(self.render_str(patch))
            except exceptions.TutorError:
                fmt.echo_error(f"Error rendering patch '{name}': {patch}")
                raise
        rendered = separator.join(patches)
        if rendered:
            rendered += suffix
        return rendered

    def render_str(self, text: str) -> str:
        template = self.environment.from_string(text)
        return self.__render(template)

    def render_template(self, template_name: str) -> t.Union[str, bytes]:
        """
        Render a template file. Return the corresponding string. If it's a binary file
        (as indicated by its path), return bytes.

        The template_name *always* uses "/" separators, and is not os-dependent. Do not pass the result of
        os.path.join(...) to this function.
        """
        if is_binary_file(template_name):
            # Don't try to render binary files
            with open(self.find_os_path(template_name), "rb") as f:
                return f.read()

        try:
            template = self.environment.get_template(template_name)
        except Exception:
            fmt.echo_error("Error loading template " + template_name)
            raise

        try:
            return self.__render(template)
        except (jinja2.exceptions.TemplateError, exceptions.TutorError):
            fmt.echo_error("Error rendering template " + template_name)
            raise
        except Exception:
            fmt.echo_error("Unknown error rendering template " + template_name)
            raise

    def render_all_to(self, dst: str, *prefix: str) -> None:
        """
        `prefix` can be used to limit the templates to render.
        """
        for template_name in self.iter_templates_in(*prefix):
            rendered = self.render_template(template_name)
            template_dst = os.path.join(dst, template_name.replace("/", os.sep))
            write_to(rendered, template_dst)

    def __render(self, template: jinja2.Template) -> str:
        try:
            return template.render(**self.config)
        except jinja2.exceptions.UndefinedError as e:
            raise exceptions.TutorError(f"Missing configuration value: {e.args[0]}")


def save(root: str, config: Config) -> None:
    """
    Save the full environment, including version information.
    """
    root_env = pathjoin(root)
    targets: t.Iterator[
        t.Tuple[str, str]
    ] = hooks.Filters.ENV_TEMPLATE_TARGETS.iterate()
    for src, dst in targets:
        save_all_from(src, os.path.join(root_env, dst), config)

    upgrade_obsolete(root)
    fmt.echo_info(f"Environment generated in {base_dir(root)}")


def upgrade_obsolete(_root: str) -> None:
    """
    Add here ad-hoc commands to upgrade the environment.
    """


def save_all_from(prefix: str, dst: str, config: Config) -> None:
    """
    Render the templates that start with `prefix` and store them with the same
    hierarchy at `dst`. Here, `prefix` can be the result of os.path.join(...).
    """
    renderer = Renderer.instance(config)
    renderer.render_all_to(dst, prefix.replace(os.sep, "/"))


def write_to(content: t.Union[str, bytes], path: str) -> None:
    """
    Write some content to a path. Content can be either str or bytes.
    """
    utils.ensure_file_directory_exists(path)
    if isinstance(content, bytes):
        with open(path, mode="wb") as of_binary:
            of_binary.write(content)
    else:
        with open(path, mode="w", encoding="utf8", newline="\n") as of_text:
            of_text.write(content)


def render_file(config: Config, *path: str) -> t.Union[str, bytes]:
    """
    Return the rendered contents of a template.
    """
    renderer = Renderer.instance(config)
    template_name = "/".join(path)
    return renderer.render_template(template_name)


def render_unknown(config: Config, value: t.Any) -> t.Any:
    """
    Render an unknown `value` object with the selected config.

    If `value` is a dict, its values are also rendered.
    """
    if isinstance(value, str):
        return render_str(config, value)
    if isinstance(value, dict):
        return {k: render_unknown(config, v) for k, v in value.items()}
    return value


def render_str(config: Config, text: str) -> str:
    """
    Args:
        text (str)
        config (dict)

    Return:
        substituted (str)
    """
    return Renderer.instance(config).render_str(text)


def check_is_up_to_date(root: str) -> None:
    if not is_up_to_date(root):
        fmt.echo_alert(
            f"The current environment stored at {base_dir(root)} is not up-to-date: it is at "
            f"v{current_version(root)} while the 'tutor' binary is at v{__version__}. You should upgrade "
            f"the environment by running:\n"
            f"\n"
            f"    tutor config save"
        )


def is_up_to_date(root: str) -> bool:
    """
    Check if the currently rendered version is equal to the current tutor version.
    """
    current = current_version(root)
    return current is None or current == __version__


def should_upgrade_from_release(root: str) -> t.Optional[str]:
    """
    Return the name of the currently installed release that we should upgrade from. Return None If we already run the
    latest release.
    """
    current = current_version(root)
    if current is None:
        return None
    current_as_int = int(current.split(".")[0])
    required_as_int = int(__version__.split(".", maxsplit=1)[0])
    if current_as_int >= required_as_int:
        return None
    return get_release(current)


def get_env_release(root: str) -> t.Optional[str]:
    """
    Return the Open edX release name from the current environment.

    If the current environment has no version, return None.
    """
    version = current_version(root)
    if version is None:
        return None
    return get_release(version)


def get_package_release() -> str:
    """
    Return the release name associated to this package.
    """
    return get_release(__version__)


def get_release(version: str) -> str:
    return {
        "0": "ironwood",
        "3": "ironwood",
        "10": "juniper",
        "11": "koa",
        "12": "lilac",
        "13": "maple",
    }[version.split(".", maxsplit=1)[0]]


def current_version(root: str) -> t.Optional[str]:
    """
    Return the current environment version. If the current environment has no version,
    return None.
    """
    path = pathjoin(root, VERSION_FILENAME)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fi:
        return fi.read().strip()


def read_template_file(*path: str) -> str:
    """
    Read raw content of template located at `path`.
    """
    src = template_path(*path)
    with open(src, encoding="utf-8") as fi:
        return fi.read()


def is_binary_file(path: str) -> bool:
    ext = os.path.splitext(path)[1]
    return ext in BIN_FILE_EXTENSIONS


def template_path(*path: str, templates_root: str = TEMPLATES_ROOT) -> str:
    """
    Return the template file's absolute path.
    """
    return os.path.join(templates_root, *path)


def data_path(root: str, *path: str) -> str:
    """
    Return the file's absolute path inside the data directory.
    """
    return os.path.join(root_dir(root), "data", *path)


def pathjoin(root: str, *path: str) -> str:
    """
    Return the file's absolute path inside the environment.
    """
    return os.path.join(base_dir(root), *path)


def base_dir(root: str) -> str:
    """
    Return the environment base directory.
    """
    return os.path.join(root_dir(root), "env")


def root_dir(root: str) -> str:
    """
    Return the project root directory.
    """
    return os.path.abspath(root)
