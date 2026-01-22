"""Compatibility shims for Python 3.10 support.

This module provides backports of Python 3.11+ features to maintain
compatibility with Python 3.10.12 environments.
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    # Backport StrEnum for Python 3.10
    class StrEnum(str, Enum):
        """String enumeration for Python 3.10 compatibility.

        StrEnum was introduced in Python 3.11. This backport provides
        the same functionality for Python 3.10 environments.

        Members are strings and can be compared directly to strings.
        """
        def __new__(cls, value):
            if not isinstance(value, str):
                raise TypeError(f"{cls.__name__} values must be strings")
            obj = str.__new__(cls, value)
            obj._value_ = value
            return obj

        def __str__(self):
            return self.value

        def _generate_next_value_(name, start, count, last_values):
            """Generate the next value when not given.

            By default, uses the member name as the value.
            """
            return name.lower()


__all__ = ["StrEnum"]
