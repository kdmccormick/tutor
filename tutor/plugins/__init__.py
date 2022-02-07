"""
Provide API for plugin features.
"""
import typing as t
from copy import deepcopy

from tutor import exceptions, hooks
from tutor.types import Config, get_typed

# Import modules to trigger hook creation
from . import v0
from . import v1


@hooks.actions.on(hooks.Actions.CORE_READY)
def _install() -> None:
    """
    Find all installed plugins.

    This method must be called once prior to loading enabled plugins. Plugins are
    installed within a context, such that they can easily be disabled later, for
    instance in tests.
    """
    with hooks.contexts.enter(hooks.Contexts.PLUGINS):
        hooks.actions.do(hooks.Actions.INSTALL_PLUGINS)


@hooks.actions.on(hooks.Actions.CORE_ROOT_READY, priority=50)
def _install_plugin_patches(_root: str) -> None:
    """
    Some patches are added as (name, content) tuples with the ENV_PATCHES
    filter. We convert these patches to add them to ENV_PATCH. This makes it
    easier for end-user to declare patches, and it's more performant.

    This action is run after plugins have been enabled.
    """
    patches: t.Iterable[t.Tuple[str, str]] = hooks.filters.iterate(
        hooks.Filters.ENV_PATCHES
    )
    for name, content in patches:
        hooks.filters.add_item(hooks.Filters.ENV_PATCH.format(name), content)


def is_installed(name: str) -> bool:
    """
    Return true if the plugin is installed.

    The _install() method must have been called prior to calling this one,
    otherwise no installed plugin will be detected.
    """
    return name in iter_installed()


def iter_installed() -> t.Iterator[str]:
    """
    Iterate on all installed plugins, sorted by name.

    This will yield all plugins, including those that have the same name.
    """
    plugins: t.Iterator[str] = hooks.filters.iterate(hooks.Filters.PLUGINS_INSTALLED)
    yield from sorted(plugins)


def iter_info() -> t.Iterator[t.Tuple[str, t.Optional[str]]]:
    """
    Iterate on the information of all installed plugins.

    Yields (<plugin name>, <info>) tuples.
    """
    versions: t.Iterator[t.Tuple[str, t.Optional[str]]] = hooks.filters.iterate(
        hooks.Filters.PLUGINS_INFO
    )
    yield from sorted(versions, key=lambda v: v[0])


def is_enabled(name: str) -> bool:
    for plugin in iter_enabled():
        if plugin == name:
            return True
    return False


def enable(name: str) -> None:
    """
    Enable a given plugin.

    Enabling a plugin is done within a context, such that we can remove all hooks when a
    plugin is disabled, or during unit tests.
    """
    if not is_installed(name):
        raise exceptions.TutorError(f"plugin '{name}' is not installed.")
    with hooks.contexts.enter(hooks.Contexts.PLUGINS, hooks.Contexts.APP.format(name)):
        hooks.actions.do(hooks.Actions.ENABLE_PLUGIN.format(name))


def iter_enabled() -> t.Iterator[str]:
    """
    Iterate on the list of enabled plugin names, sorted in alphabetical order.

    Note that enabled plugin names are deduplicated. Thus, if two plugins have
    the same name, just one name will be displayed.
    """
    plugins: t.Iterable[str] = hooks.filters.iterate(hooks.Filters.PLUGINS_ENABLED)
    yield from sorted(set(plugins))


def iter_patches(name: str) -> t.Iterator[str]:
    """
    Yields: patch (str)
    """
    yield from hooks.filters.apply(hooks.Filters.ENV_PATCH.format(name), [])


def disable(plugin: str) -> None:
    """
    Remove all filters and actions associated to a given plugin.
    """
    hooks.clear_all(context=hooks.Contexts.APP.format(plugin))
