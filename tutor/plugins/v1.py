from glob import glob
import importlib.util
import os
import pkg_resources

from tutor import hooks

from .base import PLUGINS_ROOT


@hooks.actions.on(hooks.Actions.INSTALL_PLUGINS)
def _install_module_plugins() -> None:
    for path in glob(os.path.join(PLUGINS_ROOT, "*.py")):
        install_module(path)


@hooks.actions.on(hooks.Actions.INSTALL_PLUGINS)
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
    hooks.filters.add_item(hooks.Filters.PLUGINS_INSTALLED, name)

    # Add plugin information
    hooks.filters.add_item(hooks.Filters.PLUGINS_INFO, (name, path))

    # Import module on enable
    @hooks.actions.on(hooks.Actions.ENABLE_PLUGIN.format(name))
    def enable() -> None:
        # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
        spec = importlib.util.spec_from_file_location("tutor.plugin.v1.{name}", path)
        if spec is None or spec.loader is None:
            raise ValueError("Plugin could not be found: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Add to enabled plugins
        hooks.filters.add_item(hooks.Filters.PLUGINS_ENABLED, name)


def install_package(entrypoint: pkg_resources.EntryPoint) -> None:
    """
    Install a plugin from a python package.
    """
    name = entrypoint.name

    # Add plugin to the list of installed plugins
    hooks.filters.add_item(hooks.Filters.PLUGINS_INSTALLED, name)

    # Add plugin information
    if entrypoint.dist is None:
        raise ValueError(f"Could not read plugin version: {name}")
    hooks.filters.add_item(hooks.Filters.PLUGINS_INFO, (name, entrypoint.dist.version))

    # Import module on enable
    @hooks.actions.on(hooks.Actions.ENABLE_PLUGIN.format(name))
    def enable() -> None:
        entrypoint.load()
        # Add to enabled plugins
        hooks.filters.add_item(hooks.Filters.PLUGINS_ENABLED, name)
