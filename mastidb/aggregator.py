from typing import Tuple, Any

from . import parse_helpers
from .aggregate_buffer import AggregateBuffer
from .aggregate_functions import AggregationFunction, AggregationFunctionDistinctCount, AggregationFunctionSum, AggregationFunctionCount, \
    AggregationFunctionAvg


class Aggregator:
    def __init__(self, aggregate_buffer: AggregateBuffer, aggregation_function: AggregationFunction,
                 value_idx: int, expression_args: list[Any]):
        self.aggregate_buffer: AggregateBuffer = aggregate_buffer
        self.aggregation_function: AggregationFunction = aggregation_function
        self.value_idx = value_idx
        self.expression_args = expression_args

    def record(self, aggregation_key: Tuple[int, ...], value):
        current = self.aggregate_buffer.get(aggregation_key, self.value_idx) # 1s
        new_value = self.aggregation_function.aggregate(value, current) # 1.3s
        self.aggregate_buffer.set(aggregation_key, self.value_idx, new_value)

    def finalize_values(self, value):
        return self.aggregation_function.finalize(value)

    @staticmethod
    def build_aggregation_functions(aggregate_expressions: dict) -> list[AggregationFunction]:
        """Discover aggregation functions once, in p0/p1/… order matching partial value slots."""
        functions: list[AggregationFunction] = []
        for expression in aggregate_expressions.values():
            op, _args = parse_helpers.unpack_op_args(expression)
            functions.append(Aggregator.find_aggregation_function(op, expression)())
        return functions

    @staticmethod
    def create_from_expression(expression: dict[str, Any], aggregate_buffer: AggregateBuffer, value_idx: int,
                                aggregation_function: AggregationFunction) -> 'Aggregator':
        _op, args = parse_helpers.unpack_op_args(expression)
        return Aggregator(aggregate_buffer=aggregate_buffer,
                          aggregation_function=aggregation_function,
                          value_idx=value_idx,
                          expression_args=args)

    @staticmethod
    def find_aggregation_function(op, expression):
        if op == 'sum':
            return AggregationFunctionSum
        elif op == 'count':
            if expression.get('kwargs', {}).get('distinct', None) is not None:
              return AggregationFunctionDistinctCount
            else:
              return AggregationFunctionCount
        elif op == "avg":
            return AggregationFunctionAvg
        else:
            raise NotImplementedError("Only aggregations are supported on a root level of SELECT statement. "
                                      f"Unsupported operation: {op}")
