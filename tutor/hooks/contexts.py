# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"

import typing as t
from contextlib import contextmanager


class Contextualized:
    """
    This is a simple class to store the current context in hooks.

    The current context is stored as a static variable.
    """

    CURRENT: t.List[str] = []

    def __init__(self) -> None:
        self.contexts = self.CURRENT[:]

    def is_in_context(self, context: t.Optional[str]) -> bool:
        return context is None or context in self.contexts

    @classmethod
    @contextmanager
    def enter(cls, *names: str) -> t.Iterator[None]:
        """
        Identify created hooks with one or multiple context strings.

        :param names: names of the contexts that will be attached to hooks. Multiple
            context names may be defined.

        Usage::

            from tutor import hooks

            with hooks.contexts.enter("my-context"):
                # declare new actions and filters
                ...

            # Later on, actions and filters can be disabled with:
            hooks.actions.clear_all(context="my-context")
            hooks.filters.clear_all(context="my-context")

        This is a context manager that will attach a context name to all hooks
        created within its scope. The purpose of contexts is to solve an issue that
        is inherent to pluggable hooks: it is difficult to track in which part of the
        code each hook was created. This makes things hard to debug when a specific
        hook goes wrong. It also makes it impossible to disable some hooks after
        they have been created.

        We resolve this issue by storing the current contexts in a static list.
        Whenever a hook is created, the list of current contexts is copied as a
        ``contexts`` attribute. This attribute can be later examined, either for
        removal or for limiting the set of hooks that should be applied.
        """
        try:
            for name in names:
                cls.CURRENT.append(name)
            yield
        finally:
            for _ in range(len(names)):
                cls.CURRENT.pop()


enter = Contextualized.enter
