from typing import Tuple, Any

import parse_helpers
from aggregate_buffer import AggregateBuffer
from aggregate_functions import AggregationFunction, AggregationFunctionSum, AggregationFunctionCount, \
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
    def create_from_expression(expression: dict[str, Any], aggregate_buffer: AggregateBuffer, value_idx: int):
        op, args = parse_helpers.unpack_op_args(expression)
        agg_function_cls = Aggregator.find_aggregation_function(op)
        return Aggregator(aggregate_buffer=aggregate_buffer,
                          aggregation_function=agg_function_cls(),
                          value_idx=value_idx,
                          expression_args=args)

    @staticmethod
    def find_aggregation_function(op):
        if op == 'sum':
            return AggregationFunctionSum
        elif op == 'count':
            # TODO: Handle DISTINCT column case
            return AggregationFunctionCount
        elif op == "avg":
            return AggregationFunctionAvg
        else:
            raise NotImplementedError("Only aggregations are supported on a root level of SELECT statement. "
                                      f"Unsupported operation: {op}")
