# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"

import sys
import typing as t

from . import contexts

# Similarly to CallableFilter, it should be possible to refine the definition of
# CallableAction in the future.
CallableAction = t.Callable[..., None]

DEFAULT_PRIORITY = 10


class Action(contexts.Contextualized):
    def __init__(self, func: CallableAction, priority: t.Optional[int] = None):
        super().__init__()
        self.func = func
        self.priority = priority or DEFAULT_PRIORITY

    def do(
        self, *args: t.Any, context: t.Optional[str] = None, **kwargs: t.Any
    ) -> None:
        if self.is_in_context(context):
            self.func(*args, **kwargs)


class Actions:
    """
    Singleton set of named actions.
    """

    INSTANCE = None

    @classmethod
    def instance(cls) -> "Actions":
        if cls.INSTANCE is None:
            cls.INSTANCE = cls()
        return cls.INSTANCE

    def __init__(self) -> None:
        self.actions: t.Dict[str, t.List[Action]] = {}

    def on(
        self, name: str, func: CallableAction, priority: t.Optional[int] = None
    ) -> None:
        actions = self.actions.setdefault(name, [])
        action = Action(func, priority=priority)
        # I wish we could use bisect.insort_right here but the `key=` parameter
        # is unsupported in Python 3.9
        position = 0
        while position < len(actions) and actions[position].priority <= action.priority:
            position += 1
        actions.insert(position, action)

    def do(
        self, name: str, *args: t.Any, context: t.Optional[str] = None, **kwargs: t.Any
    ) -> None:
        """
        Run callback actions associated to a name.

        :param name: name of the action for which callbacks will be run.
        :param context: limit the set of callback actions to those that
            were declared within a certain context (see
            :py:func:`tutor.hooks.contexts.enter`).

        Extra ``*args`` and ``*kwargs`` arguments will be passed as-is to
        callback functions.

        Callbacks are executed in the order they were added. There is no error
        management here: a single exception will cause all following callbacks
        not to be run and the exception to be bubbled up.
        """
        for action in self.actions.get(name, []):
            try:
                action.do(*args, context=context, **kwargs)
            except:
                sys.stderr.write(
                    f"Error applying action '{name}': func={action.func} contexts={action.contexts}'\n"
                )
                raise

    def clear_all(self, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined filter with the  given context.

        This will call :py:func:`clear` with all action names.
        """
        for name in self.actions:
            self.clear(name, context=context)

    def clear(self, name: str, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined action with the given name and context.

        :param name: name of the action callbacks to remove.
        :param context: when defined, will clear only the actions that were
            created within that context.

        Actions will be removed from the list of callbacks and will no longer be
        run in :py:func:`do` calls.

        This function should almost certainly never be called by plugins. It is
        mostly useful to disable some plugins at runtime or in unit tests.
        """
        if name not in self.actions:
            return
        self.actions[name] = [
            action for action in self.actions[name] if not action.is_in_context(context)
        ]


def on(
    name: str, priority: t.Optional[int] = None
) -> t.Callable[[CallableAction], CallableAction]:
    """
    Decorator to add a callback action associated to a name.

    :param name: name of the action. For forward compatibility, it is
        recommended not to hardcode any string here, but to pick a value from
        :py:class:`tutor.hooks.Actions` instead.
    :param priority: order in which the action callbacks are performed. Higher
        values mean that they will be performed later. The default value is
        ``DEFAULT_PRIORITY`` (10). Actions that should be performed last should
        have a priority of 100.

    Use as follows::

        from tutor import hooks

        @hooks.actions.on("my-action")
        def do_stuff():
            ...

    The ``do_stuff`` callback function will be called on ``hooks.actions.do("my-action")``. (see :py:func:`do`)

    The signature of each callback action function must match the signature of the corresponding ``hooks.actions.do`` call. Callback action functions are not supposed to return any value. Returned values will be ignored.
    """

    def inner(action_func: CallableAction) -> CallableAction:
        Actions.instance().on(name, action_func, priority=priority)
        return action_func

    return inner


do = Actions.instance().do
clear = Actions.instance().clear
clear_all = Actions.instance().clear_all
