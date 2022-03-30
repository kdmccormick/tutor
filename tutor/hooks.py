# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"

import sys
import typing as t
from contextlib import contextmanager
from dataclasses import dataclass

# In Py3.10, change these type synonyms to ``TypeAlias``es.

HookName = str

ActionName = HookName
ActionCallback = t.Callable[..., None]

T = t.TypeVar("T")
FilterName = HookName
FilterCallback = t.Callable[..., t.Any]

Context = str


@dataclass(frozen=True)
class Action:
    """
    Named extension point that triggers callbacks when a particular action occurs.
    """

    name: ActionName

    def fire(self, *, context: t.Optional[Context] = None, **kwargs: t.Any) -> None:
        """
        Trigger callbacks registered for this action.
        """
        for callback in _REGISTRY.get(self.name, context):
            try:
                callback(**kwargs)
            except:
                sys.stderr.write(
                    f"Error applying action '{self.name}': func={callback} context={context}'\n"
                )
                raise

    def handle(self, *, priority: t.Optional[int] = None) -> t.Callable[..., None]:
        """
        Register the decorated function as a callback for this action.
        """

        def inner(callback: ActionCallback) -> None:
            _REGISTRY.register(self.name, callback, priority=priority)

        if callable(priority):
            return inner(priority)
        return inner

    def clear(self, *, context: t.Optional[Context] = None) -> None:
        """
        Clear registered callbacks for this action.
        """
        _REGISTRY.clear(self.name, context=context)


class Actions:
    """
    This class is a container for the names of all actions used across Tutor
    (see :py:mod:`tutor.Action.fire`). For each action, we describe the
    arguments that are passed to the callback functions.

    To create a new callback for an existing action, write the following::

        @hooks.Actions.SOME_ACTION.handle()
        def _your_callback():
            # Do stuff here

    You can also define arbitrarily-named custom actions::

        MY_NEW_ACTION = hooks.Action("myapp:my_cool_action")

    And register callbacks for them::

        @MY_NEW_ACTION.handle()
        def _your_callback():
            # Do stuff here
    """

    #: Called whenever the core project is ready to run. This is the right time to install plugins, for instance.
    #:
    #: This action does not have any parameter.
    CORE_READY = Action("core:ready")

    #: Called as soon as we have access to the Tutor project root.
    #:
    #: :parameter str root: absolute path to the project root.
    CORE_ROOT_READY = Action("core:root:ready")

    #: Enable a specific plugin. Only plugins that have previously been installed can be enabled. (see :py:data:`INSTALL_PLUGINS`)
    #:
    #: Most plugin developers will not have to implement this action themselves, unless
    #: they want to perform a specific action at the moment the plugin is enabled.
    #:
    #: This action does not have any parameter.
    @staticmethod
    def ENABLE_PLUGIN(plugin_name: str) -> Action:  # pylint: disable=invalid-name
        return Action(f"plugins:enable:{plugin_name}")

    #: This action is done to auto-detect plugins. In particular, we load the following plugins:
    #:
    #:   - Python packages that declare a "tutor.plugin.v0" entrypoint.
    #:   - YAML plugins stored in ~/.local/share/tutor-plugins (as indicated by ``tutor plugins printroot``)
    #:   - When running the binary version of Tutor, official plugins that ship with the binary are automatically installed.
    #:
    #: Installing a plugin is typically done by the Tutor plugin mechanism. Thus, plugin
    #: developers don't have to implement this action themselves.
    #:
    #: This action does not have any parameter.
    INSTALL_PLUGINS = Action("plugins:install")


@dataclass(frozen=True)
class Filter:
    """
    Named extension point allowing modification of a particular value by registered callbacks.
    """

    name: FilterName

    def apply(
        self, starting_value: T, *, context: t.Optional[Context] = None, **kwargs: t.Any
    ) -> T:
        """
        Apply callbacks registered for this filter to a starting value.
        """
        value = starting_value
        for callback in _REGISTRY.get(self.name, context=context):
            try:
                value = callback(value, **kwargs)
            except:
                sys.stderr.write(
                    f"Error applying filter '{self.name}': func={callback} context={context}'\n"
                )
                raise
        return value

    def iterate(
        self, *, context: t.Optional[Context] = None, **kwargs: t.Any
    ) -> t.Iterator[T]:
        """
        Apply callbacks registered for this filter, starting with an empty list.
        """
        yield from self.apply([], context=context, **kwargs)

    def add(self, callback: FilterCallback) -> None:
        """
        Register the decorated function as a callback for this filter.
        """
        _REGISTRY.register(self.name, callback)

    def add_items(self, items: t.List[T]) -> None:
        """
        Register an anonymous callback for this filter that simply adds items.
        """

        @self.add
        def callback(value: t.List[T], **_kwargs: t.Any) -> t.List[T]:
            return value + items

    def add_item(self, item: T) -> None:
        """
        Register an anonymous callback for this filter that simply appends an item.
        """
        self.add_items([item])

    def clear(self, *, context: t.Optional[Context] = None) -> None:
        """
        Clear registered callbacks for this filter.
        """
        _REGISTRY.clear(self.name, context=context)


class Filters:
    """
    Here are the names of all filters used across Tutor. For each filter, the
    type of the first argument also indicates the type of the expected returned value.

    Filter names are all namespaced with domains separated by colons (":").

    To add custom data to any filter, write the following in your plugin::

        from tutor import hooks

        @hooks.Filters.SOME_FILTER.add
        def _your_callback(items):
            # do stuff with items
            ...
            # return the modified list of items
            return items
    """

    #: List of images to be built when we run ``tutor images build ...``.
    #:
    #: :parameter list[tuple[str, tuple[str, ...], str, tuple[str, ...]]] tasks: list of ``(name, path, tag, args)`` tuples.
    #:
    #:    - ``name`` is the name of the image, as in ``tutor images build myimage``.
    #:    - ``path`` is the relative path to the folder that contains the Dockerfile.
    #:      For instance ``("myplugin", "build", "myservice")`` indicates that the template will be read from
    #:      ``myplugin/build/myservice/Dockerfile``
    #:    - ``tag`` is the Docker tag that will be applied to the image. It will
    #:      rendered at runtime with the user configuration. Thus, the image tag could be ``"{{
    #:      DOCKER_REGISTRY }}/myimage:{{ TUTOR_VERSION }}"``.
    #:    - ``args`` is a list of arguments that will be passed to ``docker build ...``.
    #: :parameter dict config: user configuration.
    APP_TASK_IMAGES_BUILD = Filter("app:tasks:images:build")

    #: List of images to be pulled when we run ``tutor images pull ...``.
    #:
    #: :parameter list[tuple[str, str]] tasks: list of ``(name, tag)`` tuples.
    #:
    #:    - ``name`` is the name of the image, as in ``tutor images pull myimage``.
    #:    - ``tag`` is the Docker tag that will be applied to the image. (see :py:data:`APP_TASK_IMAGES_BUILD`).
    #: :parameter dict config: user configuration.
    APP_TASK_IMAGES_PULL = Filter("app:tasks:images:pull")

    #: List of images to be pulled when we run ``tutor images push ...``.
    #: Parameters are the same as for :py:data:`APP_TASK_IMAGES_PULL`.
    APP_TASK_IMAGES_PUSH = Filter("app:tasks:images:push")

    #: List of tasks to be performed during initialization. These tasks typically
    #: include database migrations, setting feature flags, etc.
    #:
    #: :parameter list[tuple[str, tuple[str, ...]]] tasks: list of ``(service, path)`` tasks.
    #:
    #:     - ``service`` is the name of the container in which the task will be executed.
    #:     - ``path`` is a tuple that corresponds to a template relative path. Example:
    #:       ``("myplugin", "hooks", "myservice", "pre-init")`` (see :py:data:`APP_TASK_IMAGES_BUILD`).
    APP_TASK_INIT = Filter("app:tasks:init")

    #: List of tasks to be performed prior to initialization. These tasks are run even
    #: before the mysql databases are created and the migrations are applied.
    #:
    #: :parameter list[tuple[str, tuple[str, ...]]] tasks: list of ``(service, path)`` tasks. (see :py:data:`APP_TASK_INIT`).
    APP_TASK_PRE_INIT = Filter("app:tasks:pre-init")

    #: List of command line interface (CLI) commands.
    #:
    #: :parameter list commands: commands are instances of ``click.Command``. They will
    #:   all be added as subcommands of the main ``tutor`` command.
    CLI_COMMANDS = Filter("cli:commands")

    #: Declare new configuration settings that must be saved in the user ``config.yml`` file. This is where
    #: you should declare passwords and randomly-generated values.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) new settings. All
    #:   names must be prefixed with the plugin name in all-caps.
    CONFIG_BASE = Filter("config:base")

    #: Declare new default configuration settings that don't necessarily have to be saved in the user
    #: ``config.yml`` file. Default settings may be overridden with ``tutor config save --set=...``, in which
    #: case they will automatically be added to ``config.yml``.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) new settings. All
    #:    new entries must be prefixed with the plugin name in all-caps.
    CONFIG_DEFAULTS = Filter("config:defaults")

    #: Modify existing settings, either from Tutor core or from other plugins. Beware not to override any
    #: important setting, such as passwords! Overridden setting values will be printed to stdout when the plugin
    #: is disabled, such that users have a chance to back them up.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) settings.
    CONFIG_OVERRIDES = Filter("config:overrides")

    #: List of patches that should be inserted in a given location of the templates. The
    #: filter name must be formatted with the patch name.
    #: This filter is not so convenient and plugin developers will probably
    #: prefer :py:data:`ENV_PATCHES`.
    #:
    #: :parameter list[str] patches: each item is the unrendered patch content.
    @staticmethod
    def ENV_PATCH(patch_name: str) -> Filter:  # pylint: disable=invalid-name
        return Filter(f"env:patches:{patch_name}")

    #: List of patches that should be inserted in a given location of the templates. This is very similar to :py:data:`ENV_PATCH`, except that the patch is added as a ``(name, content)`` tuple.
    #:
    #: :parameter list[tuple[str, str]] patches: pairs of (name, content) tuples. Use this
    #:   filter to modify the Tutor templates.
    ENV_PATCHES = Filter("env:patches")

    #: List of all template root folders.
    #:
    #: :parameter list[str] templates_root: absolute paths to folders which contain templates.
    #:   The templates in these folders will then be accessible by the environment
    #:   renderer using paths that are relative to their template root.
    ENV_TEMPLATE_ROOTS = Filter("env:templates:roots")

    #: List of template source/destination targets.
    #:
    #: :parameter list[tuple[str, str]] targets: list of (source, destination) pairs.
    #:   Each source is a path relative to one of the template roots, and each destination
    #:   is a path relative to the environment root. For instance: adding ``("c/d",
    #:   "a/b")`` to the filter will cause all files from "c/d" to be rendered to the ``a/b/c/d``
    #:   subfolder.
    ENV_TEMPLATE_TARGETS = Filter("env:templates:targets")

    #: List of `Jinja2 filters <https://jinja.palletsprojects.com/en/latest/templates/#filters>`__ that will be
    #: available in templates. Jinja2 filters are basically functions that can be used
    #: as follows within templates::
    #:
    #:    {{ "somevalue"|my_filter }}
    #:
    #: :parameter filters: list of (name, function) tuples. The function signature
    #:   should correspond to its usage in templates.
    ENV_TEMPLATE_FILTERS = Filter("env:templates:filters")

    #: List of extra variables to be included in all templates.
    #:
    #: :parameter filters: list of (name, value) tuples.
    ENV_TEMPLATE_VARIABLES = Filter("env:templates:variables")

    #: List of installed plugins. A plugin is first installed, then enabled.
    #:
    #: :param list[str] plugins: plugin developers probably don't have to modify this
    #:   filter themselves, but they can apply it to check for the presence of other
    #:   plugins.
    PLUGINS_INSTALLED = Filter("plugins:installed")

    #: Information about each installed plugin, including its version.
    #: Keep this information to a single line for easier parsing by 3rd-party scripts.
    #:
    #: :param list[tuple[str, str]] versions: each pair is a ``(plugin, info)`` tuple.
    PLUGINS_INFO = Filter("plugins:installed:versions")

    #: List of enabled plugins.
    #:
    #: :param list[str] plugins: plugin developers probably don't have to modify this
    #:   filter themselves, but they can apply it to check whether other plugins are enabled.
    PLUGINS_ENABLED = Filter("plugins:enabled")


@dataclass(frozen=True)
class _HookCallbackRegistration:
    contexts: t.FrozenSet[Context]
    callback: t.Callable[..., t.Any]
    priority: int


class _HookCallbackRegistry:
    """
    Singleton that keeps track of which callbacks are registered for which
    hooks and in which contexts.
    """

    _INSTANCE: t.Optional["_HookCallbackRegistry"] = None

    @classmethod
    def instance(cls) -> "_HookCallbackRegistry":
        """
        Return a singleton of this class.
        """
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self) -> None:
        self.current_contexts: t.List[Context] = []
        self.registrations_by_hook: t.Dict[
            HookName, t.List[_HookCallbackRegistration]
        ] = {}

    @contextmanager
    def enter_context(self, context: Context) -> t.Iterator[None]:
        """
        Add a context to the stack of current contexts, execute code within
        the context manager, and then pop the context off the stack.
        """
        try:
            self.current_contexts.append(context)
            yield
        finally:
            self.current_contexts.pop()

    def register(
        self,
        name: HookName,
        callback: t.Callable[..., t.Any],
        priority: t.Optional[int] = None,
    ) -> None:
        """
        Register a callback for a hook, in the current context(s).
        """
        registrations = self.registrations_by_hook.setdefault(name, [])
        new_registration = _HookCallbackRegistration(
            contexts=frozenset(self.current_contexts),
            callback=callback,
            priority=priority or 0,
        )
        position = 0
        while (
            position < len(registrations)
            and registrations[position].priority <= new_registration.priority
        ):
            position += 1
        registrations.insert(position, new_registration)

    def get(
        self, hook_name: HookName, context: t.Optional[Context] = None
    ) -> t.Iterator[t.Callable[..., t.Any]]:
        """
        Retrieve the list of callbacks registered for a hook (in a particular context).
        """
        for registration in self.registrations_by_hook.get(hook_name, []):
            if (not context) or context in registration.contexts:
                yield registration.callback

    def clear_all(self, context: t.Optional[Context] = None) -> None:
        """
        Un-register callbacks for all hooks, either for one context or for all.
        """
        for hook_name in self.registrations_by_hook:
            self.clear(hook_name, context=context)

    def clear(self, hook_name: HookName, context: t.Optional[Context] = None) -> None:
        """
        Un-register callbacks for a particular hook, either for one context or for all.
        """
        if hook_name not in self.registrations_by_hook:
            return
        self.registrations_by_hook[hook_name] = [
            registration
            for registration in self.registrations_by_hook[hook_name]
            if context and context not in registration.contexts
        ]


class Contexts:
    """
    Contexts are used to track in which parts of the code filters and actions have been
    declared. Let's look at an example::

        from tutor import hooks

        with hooks.enter_context("c1"):
            @hooks.Filter("f1").add
            def add_stuff_to_filter(...):
                ...

    The fact that our custom filter was added in a certain context allows us to later
    remove it. To do so, we write::

        from tutor import hooks
        hooks.Filter("f1").clear(context="c1")

    This makes it easy to disable side-effects by plugins, provided they were created with appropriate contexts.

    Here we list all the contexts that are used across Tutor.
    """

    #: We enter this context whenever we create hooks for a specific application or :
    #: plugin. For instance, plugin "myplugin" will be enabled within the "app:myplugin"
    #: context.
    @staticmethod
    def APP(plugin_name: str) -> Context:  # pylint: disable=invalid-name
        return f"app:{plugin_name}"

    #: Plugins will be installed and enabled within this context.
    PLUGINS = "plugins"

    #: YAML-formatted v0 plugins will be installed within that context.
    PLUGINS_V0_YAML = "plugins:v0:yaml"

    #: Python entrypoint plugins will be installed within that context.
    PLUGINS_V0_ENTRYPOINT = "plugins:v0:entrypoint"


_REGISTRY = _HookCallbackRegistry.instance()

enter_context = _REGISTRY.enter_context
clear_all = _REGISTRY.clear_all
