from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic, Tuple

from .common_utils import parse_int

T = TypeVar('T')


class AggregationFunction(Generic[T], ABC):    
    @abstractmethod
    def get_initial_value(self) -> T:
      pass

    @abstractmethod
    def aggregate(self, value: Any, current: T) -> T:
        pass

    @abstractmethod
    def merge(self, a: T, b: T) -> T:
        pass

    def finalize(self, current: T):
        return current


class AggregationFunctionCount(AggregationFunction[int]):    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: Any, current: int):
        return current + 1

    def merge(self, a: int, b: int) -> int:
        return a + b


class AggregationFunctionSum(AggregationFunction[int]):
    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: Any, current: int):
        return current + parse_int(value)

    def merge(self, a: int, b: int) -> int:
        return a + b


class AggregationFunctionAvg(AggregationFunction[tuple[int, int]]):
    
    def get_initial_value(self) -> Tuple[int, int]:
        return 0, 0

    def aggregate(self, value: Any, current: tuple[int, int]):
        return parse_int(value) + current[0], current[1] + 1

    def merge(self, a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
        return a[0] + b[0], a[1] + b[1]

    def finalize(self, current: tuple[int, int]):
        return current[0] / current[1]


class AggregationFunctionDistinctCount(AggregationFunction[set[int]]):    
    def get_initial_value(self) -> set[int]:
        return set()

    def aggregate(self, value: Any, current: set[int]):
        current.add(value)
        return current

    def merge(self, a: set[int], b: set[int]) -> set[int]:
        # FIXME: Since we're dealing with multiple segments now, the dictIDs are not the same.
        # We need to decode the group keys and merge the sets of values.
        return a | b
      
    def finalize(self, current: set[int]):
        return len(current)
