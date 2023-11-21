import parse_helpers
from aggregate_buffer import AggregateBuffer
from aggregate_functions import AggregationFunction, AggregationFunctionSum, AggregationFunctionCount, \
    AggregationFunctionAvg


class Aggregator:
    def __init__(self, aggregate_buffer, aggregation_function, value_idx):
        self.aggregate_buffer: AggregateBuffer = aggregate_buffer
        self.aggregation_function: AggregationFunction = aggregation_function
        self.value_idx = value_idx

    def record(self, aggregation_key: tuple, value):
        current = self.aggregate_buffer.get(aggregation_key, self.value_idx)
        new_value = self.aggregate(value, current or self.aggregation_function.initial_value)
        self.aggregate_buffer.set(aggregation_key, self.value_idx, new_value)

    def aggregate(self, value, current):
        return self.aggregation_function.aggregate(value, current)

    def finalize_values(self, value):
        return self.aggregation_function.finalize(value)

    @staticmethod
    def create_from_expression(expression, aggregate_buffer, value_idx):
        agg_function_cls = Aggregator.find_aggregation_function(expression)
        return Aggregator(
            aggregate_buffer=aggregate_buffer,
            aggregation_function=agg_function_cls(),
            value_idx=value_idx
        )

    @staticmethod
    def find_aggregation_function(expression):
        op, args = parse_helpers.unpack_op_args(expression)
        if op == 'sum':
            return AggregationFunctionSum
        elif op == 'count':
            # TODO: Handle DISTINCT column case
            return AggregationFunctionCount
        elif op == "avg":
            return AggregationFunctionAvg
        else:
            raise NotImplementedError("Only aggregations are supported on a root level of SELECT statement. "
                                      f"Unsupported operation: {op}. Statement: {expression}")
