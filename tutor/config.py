import os
import typing as t

from tutor import env, exceptions, fmt, hooks, plugins, serialize, utils
from tutor.types import Config, ConfigValue, cast_config, get_typed

CONFIG_FILENAME = "config.yml"


def load(root: str) -> Config:
    """
    Load full configuration.

    This will raise an exception if there is no current configuration in the
    project root. A warning will also be printed if the version from disk
    differs from the package version.
    """
    if not os.path.exists(config_path(root)):
        raise exceptions.TutorError(
            "Project root does not exist. Make sure to generate the initial "
            "configuration with `tutor config save --interactive` or `tutor local "
            "quickstart` prior to running other commands."
        )
    env.check_is_up_to_date(root)
    return load_full(root)


def load_minimal(root: str) -> Config:
    """
    Load a minimal configuration composed of the user and the base config.

    This configuration is not suitable for rendering templates, as it is incomplete.
    """
    config = get_user(root)
    update_with_base(config)
    render_full(config)
    return config


def load_full(root: str) -> Config:
    """
    Load a full configuration, with user, base and defaults.

    Return:
        current (dict): params currently saved in config.yml
        defaults (dict): default values of params which might be missing from the
        current config
    """
    config = get_user(root)
    update_with_base(config)
    update_with_defaults(config)
    render_full(config)
    return config


def update_with_base(config: Config) -> None:
    """
    Add base configuration to the config object.

    Note that configuration entries are unrendered at this point.
    """
    base = get_base()
    merge(config, base)


def update_with_defaults(config: Config) -> None:
    """
    Add default configuration to the config object.

    Note that configuration entries are unrendered at this point.
    """
    defaults = get_defaults()
    merge(config, defaults)


def update_with_env(config: Config) -> None:
    """
    Override config values from environment variables.
    """
    overrides = {}
    for k in config.keys():
        env_var = "TUTOR_" + k
        if env_var in os.environ:
            overrides[k] = serialize.parse(os.environ[env_var])
    config.update(overrides)


def get_user(root: str) -> Config:
    """
    Get the user configuration from the tutor root.

    Overrides from environment variables are loaded as well.
    """
    convert_json2yml(root)
    path = config_path(root)
    config = {}
    if os.path.exists(path):
        config = get_yaml_file(path)
    upgrade_obsolete(config)
    update_with_env(config)
    return config


def get_base() -> Config:
    """
    Load the base configuration.

    Entries in this configuration are unrendered.
    """
    base = get_template("base.yml")
    extra_base: t.List[t.Tuple[str, ConfigValue]] = []
    extra_base = hooks.filters.apply(hooks.Filters.CONFIG_BASE, extra_base)
    extra_base = hooks.filters.apply(hooks.Filters.CONFIG_OVERRIDES, extra_base)
    for name, value in extra_base:
        if name in base:
            fmt.echo_alert(
                f"Found conflicting values for setting '{name}': '{value}' or '{base[name]}'"
            )
        base[name] = value
    return base


def get_defaults() -> Config:
    """
    Get default configuration, including from plugins.

    Entries in this configuration are unrendered.
    """
    defaults = get_template("defaults.yml")
    extra_defaults: t.Iterator[t.Tuple[str, ConfigValue]] = hooks.filters.iterate(
        hooks.Filters.CONFIG_DEFAULTS
    )
    for name, value in extra_defaults:
        defaults[name] = value
    update_with_env(defaults)
    return defaults


def get_template(filename: str) -> Config:
    """
    Get one of the configuration templates.

    Entries in this configuration are unrendered.
    """
    config = serialize.load(env.read_template_file("config", filename))
    return cast_config(config)


def get_yaml_file(path: str) -> Config:
    """
    Load config from yaml file.
    """
    with open(path, encoding="utf-8") as f:
        config = serialize.load(f.read())
    return cast_config(config)


def merge(config: Config, base: Config) -> None:
    """
    Merge base values with user configuration. Values are only added if not
    already present.

    Note that this function does not perform the rendering step of the
    configuration entries.
    """
    for key, value in base.items():
        if key not in config:
            config[key] = value


def render_full(config: Config) -> None:
    """
    Fill and render an existing configuration with defaults.

    It is generally necessary to apply this function before rendering templates,
    otherwise configuration entries may not be rendered.
    """
    for key, value in config.items():
        config[key] = env.render_unknown(config, value)


def is_service_activated(config: Config, service: str) -> bool:
    return config["RUN_" + service.upper()] is not False


def upgrade_obsolete(config: Config) -> None:
    # Openedx-specific mysql passwords
    if "MYSQL_PASSWORD" in config:
        config["MYSQL_ROOT_PASSWORD"] = config["MYSQL_PASSWORD"]
        config["OPENEDX_MYSQL_PASSWORD"] = config["MYSQL_PASSWORD"]
        config.pop("MYSQL_PASSWORD")
    if "MYSQL_DATABASE" in config:
        config["OPENEDX_MYSQL_DATABASE"] = config.pop("MYSQL_DATABASE")
    if "MYSQL_USERNAME" in config:
        config["OPENEDX_MYSQL_USERNAME"] = config.pop("MYSQL_USERNAME")
    if "RUN_NOTES" in config:
        if config["RUN_NOTES"]:
            plugins.enable("notes")
            save_enabled_plugins(config)
        config.pop("RUN_NOTES")
    if "RUN_XQUEUE" in config:
        if config["RUN_XQUEUE"]:
            plugins.enable("xqueue")
            save_enabled_plugins(config)
        config.pop("RUN_XQUEUE")
    if "SECRET_KEY" in config:
        config["OPENEDX_SECRET_KEY"] = config.pop("SECRET_KEY")
    # Replace WEB_PROXY by RUN_CADDY
    if "WEB_PROXY" in config:
        config["RUN_CADDY"] = not config.pop("WEB_PROXY")
    # Rename ACTIVATE_HTTPS to ENABLE_HTTPS
    if "ACTIVATE_HTTPS" in config:
        config["ENABLE_HTTPS"] = config.pop("ACTIVATE_HTTPS")
    # Replace RUN_* variables by RUN_*
    for name in [
        "ACTIVATE_LMS",
        "ACTIVATE_CMS",
        "ACTIVATE_ELASTICSEARCH",
        "ACTIVATE_MONGODB",
        "ACTIVATE_MYSQL",
        "ACTIVATE_REDIS",
        "ACTIVATE_SMTP",
    ]:
        if name in config:
            config[name.replace("ACTIVATE_", "RUN_")] = config.pop(name)
    # Replace RUN_CADDY by ENABLE_WEB_PROXY
    if "RUN_CADDY" in config:
        config["ENABLE_WEB_PROXY"] = config.pop("RUN_CADDY")
    # Replace RUN_CADDY by ENABLE_WEB_PROXY
    if "NGINX_HTTP_PORT" in config:
        config["CADDY_HTTP_PORT"] = config.pop("NGINX_HTTP_PORT")


def convert_json2yml(root: str) -> None:
    """
    Older versions of tutor used to have json config files.
    """
    json_path = os.path.join(root, "config.json")
    if not os.path.exists(json_path):
        return
    if os.path.exists(config_path(root)):
        raise exceptions.TutorError(
            f"Both config.json and {CONFIG_FILENAME} exist in {root}: only one of these files must exist to continue"
        )
    config = get_yaml_file(json_path)
    save_config_file(root, config)
    os.remove(json_path)
    fmt.echo_info(
        f"File config.json detected in {root} and converted to {CONFIG_FILENAME}"
    )


def save_config_file(root: str, config: Config) -> None:
    path = config_path(root)
    utils.ensure_file_directory_exists(path)
    with open(path, "w", encoding="utf-8") as of:
        serialize.dump(config, of)
    fmt.echo_info(f"Configuration saved to {path}")


def config_path(root: str) -> str:
    return os.path.join(root, CONFIG_FILENAME)


# Key name under which plugins are listed
PLUGINS_CONFIG_KEY = "PLUGINS"


def enable_plugins(config: Config) -> None:
    """
    Enable all plugins listed in the configuration.
    """
    names: t.List[str] = get_typed(config, PLUGINS_CONFIG_KEY, list, [])
    names = sorted(set(names))
    installed = set(plugins.iter_installed())
    for name in names:
        if name in installed:
            try:
                plugins.enable(name)
            except exceptions.TutorError as e:
                fmt.echo_alert(f"Failed to enable plugin '{name}' : {e.args[0]}")


def save_enabled_plugins(config: Config) -> None:
    """
    Save the list of enabled plugins.

    Plugins are deduplicated by name.
    """
    config[PLUGINS_CONFIG_KEY] = list(plugins.iter_enabled())


def disable_plugin(config: Config, plugin: str) -> None:
    # Find the configuration entries that were overridden by the plugin and
    # remove them from the current config
    plugin_context = hooks.Contexts.APP.format(plugin)
    overriden_config_items: t.Iterator[
        t.Tuple[str, ConfigValue]
    ] = hooks.filters.iterate(hooks.Filters.CONFIG_OVERRIDES, context=plugin_context)
    for key, _value in overriden_config_items:
        value = config.pop(key, None)
        value = env.render_unknown(config, value)
        fmt.echo_info(f"Disabling {plugin}: removing config entry {key}={value}")

    # Disable plugin and remove it from the list of enabled plugins
    plugins.disable(plugin)
    save_enabled_plugins(config)


@hooks.actions.on(hooks.Actions.CORE_ROOT_READY, priority=20)
def _enable_plugins(root: str) -> None:
    """
    Plugins must be enabled after they are installed, hence the higher priority
    value.
    """
    config = load_minimal(root)
    enable_plugins(config)
