"""ORDER BY direction helpers.

Two consumers need opposite conventions:
- ascending sorted(): smaller key wins → wrap/negate on DESC
- max-heap / nlargest: larger key wins → wrap/negate on ASC
"""

from typing import Any, Optional


class _Reverse:
    __slots__ = ('value',)

    def __init__(self, value: Any):
        self.value = value

    def __lt__(self, other: '_Reverse') -> bool:
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Reverse) and self.value == other.value


def _flip(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return -value
    return _Reverse(value)


def ascending_key(value: Any, sort: Optional[str]) -> Any:
    """Component for sorted(..., reverse=False)."""
    return _flip(value) if sort == 'desc' else value


def max_heap_key(value: Any, sort: Optional[str]) -> Any:
    """Component where larger is better (nlargest / winner min-heap)."""
    return value if sort == 'desc' else _flip(value)
