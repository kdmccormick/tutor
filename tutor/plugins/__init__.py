"""
Provide API for plugin features.
"""
import typing as t
from copy import deepcopy

from tutor import exceptions, fmt, hooks
from tutor.types import Config, get_typed

# Import modules to trigger hook creation
from . import v0
from . import v1


@hooks.Actions.CORE_READY.add()
def _discover_all_plugins() -> None:
    """
    Find all installed plugins.

    This method must be called once prior to loading enabled plugins. Plugins are
    installed within a context, such that they can easily be disabled later, for
    instance in tests.
    """
    with hooks.Contexts.PLUGINS.enter():
        hooks.Actions.DISCOVER_PLUGINS.do()


@hooks.Actions.LOAD_PLUGINS.add()
def _load_plugins(names: t.Iterable[str]) -> None:
    """
    Load all plugins one by one.

    Plugins are loaded in alphabetical order. We ignore plugins which failed to load.
    After all plugins have been loaded, the LOAD_PLUGINS_POST action is triggered.
    """
    names = sorted(set(names))
    for name in names:
        try:
            load(name)
        except exceptions.TutorError as e:
            fmt.echo_alert(f"Failed to enable plugin '{name}' : {e.args[0]}")
    hooks.Actions.LOAD_PLUGINS_POST.do()


@hooks.Actions.LOAD_PLUGINS_POST.add()
def _convert_plugin_patches() -> None:
    """
    Some patches are added as (name, content) tuples with the ENV_PATCHES
    filter. We convert these patches to add them to ENV_PATCH. This makes it
    easier for end-user to declare patches, and it's more performant.

    This action is run after plugins have been loaded.
    """
    patches: t.Iterable[t.Tuple[str, str]] = hooks.Filters.ENV_PATCHES.iterate()
    for name, content in patches:
        hooks.Filters.ENV_PATCH(name).add_item(content)


def is_installed(name: str) -> bool:
    """
    Return true if the plugin is installed.

    The DISCOVER_PLUGINS action must have been triggered prior to calling this function,
    otherwise no installed plugin will be detected.
    """
    return name in iter_installed()


def iter_installed() -> t.Iterator[str]:
    """
    Iterate on all installed plugins, sorted by name.

    This will yield all plugins, including those that have the same name.
    """
    plugins: t.Iterator[str] = hooks.Filters.PLUGINS_INSTALLED.iterate()
    yield from sorted(plugins)


def iter_info() -> t.Iterator[t.Tuple[str, t.Optional[str]]]:
    """
    Iterate on the information of all installed plugins.

    Yields (<plugin name>, <info>) tuples.
    """
    versions: t.Iterator[
        t.Tuple[str, t.Optional[str]]
    ] = hooks.Filters.PLUGINS_INFO.iterate()
    yield from sorted(versions, key=lambda v: v[0])


def is_loaded(name: str) -> bool:
    return name in iter_loaded()


def load(name: str) -> None:
    """
    Load a given plugin, thus declaring all its hooks.

    Loading a plugin is done within a context, such that we can remove all hooks when a
    plugin is disabled, or during unit tests.
    """
    if not is_installed(name):
        raise exceptions.TutorError(f"plugin '{name}' is not installed.")
    with hooks.Contexts.PLUGINS.enter():
        with hooks.Contexts.APP(name).enter():
            hooks.Actions.LOAD_PLUGIN(name).do()


def iter_loaded() -> t.Iterator[str]:
    """
    Iterate on the list of loaded plugin names, sorted in alphabetical order.

    Note that loaded plugin names are deduplicated. Thus, if two plugins have
    the same name, just one name will be displayed.
    """
    plugins: t.Iterable[str] = hooks.Filters.PLUGINS_LOADED.iterate()
    yield from sorted(set(plugins))


def iter_patches(name: str) -> t.Iterator[str]:
    """
    Yields: patch (str)
    """
    yield from hooks.Filters.ENV_PATCH(name).iterate()


def disable(plugin: str) -> None:
    """
    Remove all filters and actions associated to a given plugin.
    """
    hooks.clear_all(context=hooks.Contexts.APP(plugin).name)
