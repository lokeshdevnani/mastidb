from abc import abstractmethod
from typing import TypeVar, Generic, Tuple

T = TypeVar('T')


class AggregationFunction(Generic[T]):
    initial_value: T

    @abstractmethod
    def aggregate(self, value: int, current: T) -> T:
        pass

    def finalize(self, current: T):
        return current


class AggregationFunctionCount(AggregationFunction[int]):
    initial_value = 0

    def aggregate(self, value, current: int):
        return current + 1


class AggregationFunctionSum(AggregationFunction[int]):
    initial_value = 0

    def aggregate(self, value, current: int):
        return current + value


class AggregationFunctionAvg(AggregationFunction[tuple[int, int]]):
    initial_value = 0, 0

    def aggregate(self, value: int, current: tuple[int, int]):
        return value + current[0], current[1] + 1

    def finalize(self, current: tuple[int, int]):
        return current[0] / current[1]
