from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Tuple

T = TypeVar('T')


class AggregationFunction(Generic[T], ABC):    
    @abstractmethod
    def get_initial_value(self) -> T:
      pass

    @abstractmethod
    def aggregate(self, value: int, current: T) -> T:
        pass

    def finalize(self, current: T):
        return current


class AggregationFunctionCount(AggregationFunction[int]):    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: int, current: int):
        return current + 1


class AggregationFunctionSum(AggregationFunction[int]):
    
    def get_initial_value(self) -> int:
        return 0

    def aggregate(self, value: int, current: int):
        return current + value


class AggregationFunctionAvg(AggregationFunction[tuple[int, int]]):
    
    def get_initial_value(self) -> Tuple[int, int]:
        return 0, 0

    def aggregate(self, value: int, current: tuple[int, int]):
        return value + current[0], current[1] + 1

    def finalize(self, current: tuple[int, int]):
        return current[0] / current[1]
