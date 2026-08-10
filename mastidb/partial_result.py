from dataclasses import dataclass
from typing import Any


@dataclass
class AggregatePartial:
    """Snapshot of AggregateBuffer with decoded group keys and unfinalized aggregate states."""
    groups: dict[tuple[Any, ...], list[Any]]
