import copy
from typing import Tuple, Any, List


class AggregateBuffer:
    _buffer: dict[Tuple[int, ...], list[Any]]
    _default_value: list[Any]

    def __init__(self, value_length: int):
        self.value_length = value_length
        self._buffer: dict[Tuple[int, ...], list[Any]] = {}
        self.default_value: List[Any] = []

    def get(self, keys: Tuple[int, ...], value_index: int) -> Any:
        return self._buffer[keys][value_index]

    def set(self, keys: Tuple[int, ...], value_index: int, value: Any) -> None:
        self._buffer[keys][value_index] = value

    def init_empty_buffer_for_keys(self, keys: Tuple[int, ...]) -> None:
        if keys not in self._buffer:
            self._buffer[keys] = copy.copy(self.default_value)

    def set_default_value(self, default_value: list[Any]) -> None:
        self.default_value = default_value

    def get_results(self) -> dict[Tuple[int, ...], list[Any]]:
        return self._buffer
