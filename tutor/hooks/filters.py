# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"

import sys
import typing as t

from . import contexts

# For now, this signature is not very restrictive. In the future, we could improve it by writing:
#
# P = ParamSpec("P")
# CallableFilter = t.Callable[Concatenate[T, P], T]
#
# See PEP-612: https://www.python.org/dev/peps/pep-0612/
# Unfortunately, this piece of code fails because of a bug in mypy:
# https://github.com/python/mypy/issues/11833
# https://github.com/python/mypy/issues/8645
# https://github.com/python/mypy/issues/5876
# https://github.com/python/typing/issues/696
T = t.TypeVar("T")
CallableFilter = t.Callable[..., t.Any]


class Filter(contexts.Contextualized):
    """
    A filter is simply a function associated to a context.
    """

    def __init__(self, func: CallableFilter):
        super().__init__()
        self.func = func

    def apply(
        self, value: T, *args: t.Any, context: t.Optional[str] = None, **kwargs: t.Any
    ) -> T:
        if self.is_in_context(context):
            value = self.func(value, *args, **kwargs)
        return value


class Filters:
    """
    Singleton set of named filters.
    """

    INSTANCE = None

    @classmethod
    def instance(cls) -> "Filters":
        if cls.INSTANCE is None:
            cls.INSTANCE = cls()
        return cls.INSTANCE

    def __init__(self) -> None:
        self.filters: t.Dict[str, t.List[Filter]] = {}

    def add(self, name: str, func: CallableFilter) -> None:
        self.filters.setdefault(name, []).append(Filter(func))

    def iterate(
        self, name: str, *args: t.Any, context: t.Optional[str] = None, **kwargs: t.Any
    ) -> t.Iterator[T]:
        """
        Convenient function to iterate over the results of a filter result list.

        This pieces of code are equivalent::

            for value in filters.apply("my-filter", [], *args, **kwargs):
                ...

            for value in filters.iterate("my-filter", *args, **kwargs):
                ...

        :rtype iterator[T]: iterator over the list items from the filter with the same name.
        """
        yield from self.apply(name, [], *args, context=context, **kwargs)

    def apply(
        self,
        name: str,
        value: T,
        *args: t.Any,
        context: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> T:
        """
        Apply all declared filters to a single value, passing along the additional arguments.

        The return value of every filter is passed as the first argument to the next callback.

        Usage::

            results = filters.apply("my-filter", ["item0"])

        :type value: object
        :rtype: same as the type of ``value``.
        """
        for filtre in self.filters.get(name, []):
            try:
                value = filtre.apply(value, *args, context=context, **kwargs)
            except:
                sys.stderr.write(
                    f"Error applying filter '{name}': func={filtre.func} contexts={filtre.contexts}'\n"
                )
                raise
        return value

    def clear_all(self, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined filter with the  given context.
        """
        for name in self.filters:
            self.clear(name, context=context)

    def clear(self, name: str, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined filter with the given name and context.
        """
        if name not in self.filters:
            return
        self.filters[name] = [
            filtre for filtre in self.filters[name] if not filtre.is_in_context(context)
        ]


def add(name: str) -> t.Callable[[CallableFilter], CallableFilter]:
    """
    Decorator for functions that will be applied to a single named filter.

    :param name: name of the filter to which the decorated function should be added.

    The return value of each filter function will be passed as the first argument to the next one.

    Usage::

        from tutor import hooks

        @hooks.filters.add("my-filter")
        def my_func(value, some_other_arg):
            # Do something with `value`
            ...
            return value

        # After filters have been created, the result of calling all filter callbacks is obtained by running:
        hooks.filters.apply("my-filter", initial_value, some_other_argument_value)
    """

    def inner(func: CallableFilter) -> CallableFilter:
        Filters.instance().add(name, func)
        return func

    return inner


def add_item(name: str, item: T) -> None:
    """
    Convenience function to add a single item to a filter that returns a list of items.

    :param name: filter name.
    :param object item: item that will be appended to the resulting list.

    Usage::

        from tutor import hooks

        hooks.filters.add_item("my-filter", "item1")
        hooks.filters.add_item("my-filter", "item2")

        assert ["item1", "item2"] == hooks.filters.apply("my-filter", [])
    """
    add_items(name, [item])


def add_items(name: str, items: t.List[T]) -> None:
    """
    Convenience function to add multiple item to a filter that returns a list of items.

    :param name: filter name.
    :param list[object] items: items that will be appended to the resulting list.

    Usage::

        from tutor import hooks

        hooks.filters.add_items("my-filter", ["item1", "item2"])

        assert ["item1", "item2"] == hooks.filters.apply("my-filter", [])
    """

    @add(name)
    def callback(value: t.List[T], *_args: t.Any, **_kwargs: t.Any) -> t.List[T]:
        return value + items


iterate = Filters.instance().iterate
apply = Filters.instance().apply
clear = Filters.instance().clear
clear_all = Filters.instance().clear_all
