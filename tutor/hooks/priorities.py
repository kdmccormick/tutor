"""
Predefined priority levels for hook callbacks.
"""

# The Tutor plugin system is licensed under the terms of the Apache 2.0 license.
__license__ = "Apache 2.0"


__all__ = ["Priorities"]


class Priorities:
    """
    Priorities are integers in the range 1-100 that indicate the order in which hook
    callbacks should be executed. A larger numerical value a indicate lower (i.e. later)
    priority. A smaller numberical value indicates a higher (i.e. earlier) priority.
    Hooks callbacks with the same priority level may be executed in any order.

    We provide predefined priorities here for convenience, but any integer 1-100 is valid.
    """

    FIRST = 1
    EARLY = 5
    DEFAULT = 10
    LATE = 50
    LAST = 100
