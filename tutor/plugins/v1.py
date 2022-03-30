from glob import glob
import importlib.util
import os
import pkg_resources

from tutor import hooks

from .base import PLUGINS_ROOT


@hooks.Actions.INSTALL_PLUGINS.handle()
def _install_module_plugins() -> None:
    for path in glob(os.path.join(PLUGINS_ROOT, "*.py")):
        install_module(path)


@hooks.Actions.INSTALL_PLUGINS.handle()
def _install_packages() -> None:
    """
    Install all plugins that declare a "tutor.plugin.v1alpha" entrypoint.
    """
    for entrypoint in pkg_resources.iter_entry_points("tutor.plugin.v1alpha"):
        install_package(entrypoint)


def install_module(path: str) -> None:
    """
    Install a plugin written as a single file module.
    """
    name = os.path.splitext(os.path.basename(path))[0]

    # Add plugin to the list of installed plugins
    hooks.Filters.PLUGINS_INSTALLED.add_item(name)

    # Add plugin information
    hooks.Filters.PLUGINS_INFO.add_item((name, path))

    # Import module on enable
    plugin_action = hooks.Actions.ENABLE_PLUGIN(name)

    @plugin_action.handle()
    def enable() -> None:
        # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
        spec = importlib.util.spec_from_file_location("tutor.plugin.v1.{name}", path)
        if spec is None or spec.loader is None:
            raise ValueError("Plugin could not be found: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Add to enabled plugins
        hooks.Filters.PLUGINS_ENABLED.add_item(name)


def install_package(entrypoint: pkg_resources.EntryPoint) -> None:
    """
    Install a plugin from a python package.
    """
    name = entrypoint.name

    # Add plugin to the list of installed plugins
    hooks.Filters.PLUGINS_INSTALLED.add_item(name)

    # Add plugin information
    if entrypoint.dist is None:
        raise ValueError(f"Could not read plugin version: {name}")
    hooks.Filters.PLUGINS_INFO.add_item((name, entrypoint.dist.version))

    # Import module on enable
    plugin_action = hooks.Actions.ENABLE_PLUGIN(name)

    @plugin_action.handle()
    def enable() -> None:
        entrypoint.load()
        # Add to enabled plugins
        hooks.Filters.PLUGINS_ENABLED.add_item(name)
