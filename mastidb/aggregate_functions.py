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

    def finalize(self, current: T):
        return current


class AggregationFunctionCount(AggregationFunction[int]):    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: Any, current: int):
        return current + 1


class AggregationFunctionSum(AggregationFunction[int]):
    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: Any, current: int):
        return current + parse_int(value)


class AggregationFunctionAvg(AggregationFunction[tuple[int, int]]):
    
    def get_initial_value(self) -> Tuple[int, int]:
        return 0, 0

    def aggregate(self, value: Any, current: tuple[int, int]):
        return parse_int(value) + current[0], current[1] + 1

    def finalize(self, current: tuple[int, int]):
        return current[0] / current[1]


class AggregationFunctionDistinctCount(AggregationFunction[set[int]]):    
    def get_initial_value(self) -> set[int]:
        return set()

    def aggregate(self, value: Any, current: set[int]):
        current.add(value)
        return current
      
    def finalize(self, current: set[int]):
        return len(current)
