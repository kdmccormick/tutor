"""
List of all the action, filter and context names used across Tutor. This module is used
to generate part of the reference documentation.
"""
# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"

from tutor import hooks

__all__ = ["Actions", "Filters", "Contexts"]


class Actions:
    """
    This class is a container for the names of all actions used across Tutor
    (see :py:mod:`tutor.hooks.actions.do`). For each action, we describe the
    arguments that are passed to the callback functions.

    To create a new callback for an existing action, write the following::

        @hooks.Actions.YOUR_ACTION.add()
        def your_action():
            # Do stuff here
    """

    #: Called whenever the core project is ready to run. This is the right time to install plugins, for instance.
    #:
    #: This action does not have any parameter.
    CORE_READY = hooks.actions.get("core:ready")

    #: Called as soon as we have access to the Tutor project root.
    #:
    #: :parameter str root: absolute path to the project root.
    CORE_ROOT_READY = hooks.actions.get("core:root:ready")

    #: This action is done to auto-detect plugins. In particular, we auto-discover the following plugins:
    #:
    #:   - Python packages that declare a "tutor.plugin.v0" entrypoint.
    #:   - Python packages that declare a "tutor.plugin.v1" entrypoint.
    #:   - YAML and Python plugins stored in ~/.local/share/tutor-plugins (as indicated by ``tutor plugins printroot``)
    #:   - When running the binary version of Tutor, official plugins that ship with the binary are automatically discovered.
    #:
    #: Discovering a plugin is typically done by the Tutor plugin mechanism. Thus, plugin
    #: developers probably don't have to implement this action themselves.
    #:
    #: This action does not have any parameter.
    DISCOVER_PLUGINS = hooks.actions.get("plugins:discover")

    #: Load a specific plugin. Only plugins that have previously been discovered can be loaded.
    #: (see :py:data:`DISCOVER_PLUGINS`)
    #:
    #: Plugins are typically loaded because they are enabled.
    #:
    #: Most plugin developers will not have to implement this action themselves, unless
    #: they want to perform a specific action at the moment the plugin is enabled.
    #:
    #: This action does not have any parameter.
    LOAD_PLUGIN = hooks.actions.get_template("plugins:load:{0}")

    #: Load a list of plugins. This action triggers :py:data:`LOAD_PLUGIN` for every
    #: loaded plugin. Plugins are loaded in alphabetical order.
    #:
    #: :parameter list[str] names: list of plugin names.
    LOAD_PLUGINS = hooks.actions.get("plugins:load")

    #: Triggered after all plugins have been loaded.
    #:
    #: This action does not have any parameter.
    LOAD_PLUGINS_POST = hooks.actions.get("plugins:load-post")


class Filters:
    """
    Here are the names of all filters used across Tutor. For each filter, the
    type of the first argument also indicates the type of the expected returned value.

    Filter names are all namespaced with domains separated by colons (":").

    To add custom data to any filter, write the following in your plugin::

        import typing as t from tutor import hooks

        @hooks.Filters.YOUR_FILTER.add()
        def your_filter(items):
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
    APP_TASK_IMAGES_BUILD = hooks.filters.get("app:tasks:images:build")

    #: List of images to be pulled when we run ``tutor images pull ...``.
    #:
    #: :parameter list[tuple[str, str]] tasks: list of ``(name, tag)`` tuples.
    #:
    #:    - ``name`` is the name of the image, as in ``tutor images pull myimage``.
    #:    - ``tag`` is the Docker tag that will be applied to the image. (see :py:data:`APP_TASK_IMAGES_BUILD`).
    #: :parameter dict config: user configuration.
    APP_TASK_IMAGES_PULL = hooks.filters.get("app:tasks:images:pull")

    #: List of images to be pulled when we run ``tutor images push ...``.
    #: Parameters are the same as for :py:data:`APP_TASK_IMAGES_PULL`.
    APP_TASK_IMAGES_PUSH = hooks.filters.get("app:tasks:images:push")

    #: List of tasks to be performed during initialization. These tasks typically
    #: include database migrations, setting feature flags, etc.
    #:
    #: :parameter list[tuple[str, tuple[str, ...]]] tasks: list of ``(service, path)`` tasks.
    #:
    #:     - ``service`` is the name of the container in which the task will be executed.
    #:     - ``path`` is a tuple that corresponds to a template relative path. Example:
    #:       ``("myplugin", "hooks", "myservice", "pre-init")`` (see :py:data:`APP_TASK_IMAGES_BUILD`).
    APP_TASK_INIT = hooks.filters.get("app:tasks:init")

    #: List of tasks to be performed prior to initialization. These tasks are run even
    #: before the mysql databases are created and the migrations are applied.
    #:
    #: :parameter list[tuple[str, tuple[str, ...]]] tasks: list of ``(service, path)`` tasks. (see :py:data:`APP_TASK_INIT`).
    APP_TASK_PRE_INIT = hooks.filters.get("app:tasks:pre-init")

    # TODO
    APP_MOUNT_CLAIMS = hooks.filters.get("app:mounts:claims")

    #: List of command line interface (CLI) commands.
    #:
    #: :parameter list commands: commands are instances of ``click.Command``. They will
    #:   all be added as subcommands of the main ``tutor`` command.
    CLI_COMMANDS = hooks.filters.get("cli:commands")

    #: Declare new configuration settings that must be saved in the user ``config.yml`` file. This is where
    #: you should declare passwords and randomly-generated values.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) new settings. All
    #:   names must be prefixed with the plugin name in all-caps.
    CONFIG_BASE = hooks.filters.get("config:base")

    #: Declare new default configuration settings that don't necessarily have to be saved in the user
    #: ``config.yml`` file. Default settings may be overridden with ``tutor config save --set=...``, in which
    #: case they will automatically be added to ``config.yml``.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) new settings. All
    #:    new entries must be prefixed with the plugin name in all-caps.
    CONFIG_DEFAULTS = hooks.filters.get("config:defaults")

    #: Modify existing settings, either from Tutor core or from other plugins. Beware not to override any
    #: important setting, such as passwords! Overridden setting values will be printed to stdout when the plugin
    #: is disabled, such that users have a chance to back them up.
    #:
    #: :parameter list[tuple[str, ...]] items: list of (name, value) settings.
    CONFIG_OVERRIDES = hooks.filters.get("config:overrides")

    #: List of patches that should be inserted in a given location of the templates. The
    #: filter name must be formatted with the patch name.
    #: This filter is not so convenient and plugin developers will probably
    #: prefer :py:data:`ENV_PATCHES`.
    #:
    #: :parameter list[str] patches: each item is the unrendered patch content.
    ENV_PATCH = hooks.filters.get_template("env:patches:{0}")

    #: List of patches that should be inserted in a given location of the templates. This is very similar to :py:data:`ENV_PATCH`, except that the patch is added as a ``(name, content)`` tuple.
    #:
    #: :parameter list[tuple[str, str]] patches: pairs of (name, content) tuples. Use this
    #:   filter to modify the Tutor templates.
    ENV_PATCHES = hooks.filters.get("env:patches")

    #: List of all template root folders.
    #:
    #: :parameter list[str] templates_root: absolute paths to folders which contain templates.
    #:   The templates in these folders will then be accessible by the environment
    #:   renderer using paths that are relative to their template root.
    ENV_TEMPLATE_ROOTS = hooks.filters.get("env:templates:roots")

    #: List of template source/destination targets.
    #:
    #: :parameter list[tuple[str, str]] targets: list of (source, destination) pairs.
    #:   Each source is a path relative to one of the template roots, and each destination
    #:   is a path relative to the environment root. For instance: adding ``("c/d",
    #:   "a/b")`` to the filter will cause all files from "c/d" to be rendered to the ``a/b/c/d``
    #:   subfolder.
    ENV_TEMPLATE_TARGETS = hooks.filters.get("env:templates:targets")

    #: List of `Jinja2 filters <https://jinja.palletsprojects.com/en/latest/templates/#filters>`__ that will be
    #: available in templates. Jinja2 filters are basically functions that can be used
    #: as follows within templates::
    #:
    #:    {{ "somevalue"|my_filter }}
    #:
    #: Note that Jinja2 filters are a completely different thing than the Tutor hook
    #: filters, although they share the same name.
    #:
    #: :parameter filters: list of (name, function) tuples. The function signature
    #:   should correspond to its usage in templates.
    ENV_TEMPLATE_FILTERS = hooks.filters.get("env:templates:filters")

    #: List of extra variables to be included in all templates.
    #:
    #: :parameter filters: list of (name, value) tuples.
    ENV_TEMPLATE_VARIABLES = hooks.filters.get("env:templates:variables")

    #: List of installed plugins. In order to be added to this list, a plugin must first
    #: be discovered (see :py:data:`Actions.DISCOVER_PLUGINS`).
    #:
    #: :param list[str] plugins: plugin developers probably don't have to implement this
    #:   filter themselves, but they can apply it to check for the presence of other
    #:   plugins.
    PLUGINS_INSTALLED = hooks.filters.get("plugins:installed")

    #: Information about each installed plugin, including its version.
    #: Keep this information to a single line for easier parsing by 3rd-party scripts.
    #:
    #: :param list[tuple[str, str]] versions: each pair is a ``(plugin, info)`` tuple.
    PLUGINS_INFO = hooks.filters.get("plugins:installed:versions")

    #: List of loaded plugins.
    #:
    #: :param list[str] plugins: plugin developers probably don't have to modify this
    #:   filter themselves, but they can apply it to check whether other plugins are enabled.
    PLUGINS_LOADED = hooks.filters.get("plugins:loaded")


class Contexts:
    """
    Contexts are used to track in which parts of the code filters and actions have been
    declared. Let's look at an example::

        from tutor import hooks

        with hooks.contexts.enter("c1"):
            @hooks.filters.add("f1") def add_stuff_to_filter(...):
                ...

    The fact that our custom filter was added in a certain context allows us to later
    remove it. To do so, we write::

        from tutor import hooks
        hooks.filters.clear("f1", context="c1")

    This makes it easy to disable side-effects by plugins, provided they were created with appropriate contexts.

    Here we list all the contexts that are used across Tutor.
    """

    #: We enter this context whenever we create hooks for a specific application or :
    #: plugin. For instance, plugin "myplugin" will be enabled within the "app:myplugin"
    #: context.
    APP = hooks.contexts.ContextTemplate("app:{0}")

    #: Plugins will be installed and enabled within this context.
    PLUGINS = hooks.contexts.Context("plugins")

    #: YAML-formatted v0 plugins will be installed within that context.
    PLUGINS_V0_YAML = hooks.contexts.Context("plugins:v0:yaml")

    #: Python entrypoint plugins will be installed within that context.
    PLUGINS_V0_ENTRYPOINT = hooks.contexts.Context("plugins:v0:entrypoint")
