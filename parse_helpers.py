import json
from dataclasses import dataclass
from typing import Any, Union

from mo_sql_parsing import parse, normal_op


def listwrap(value):
    if value is None:
        return []
    elif isinstance(value, list):
        return value
    else:
        return [value]


def extract_aggregations(select_statement_cols):
    aggregations: dict[str, str] = {}

    def convert_dict_to_key(d):
        return json.dumps(d)

    def get_aggregation_id_map():
        return {value: json.loads(key) for key, value in aggregations.items()}

    def get_aggregation_mapping(node):
        if node in aggregations:
            return aggregations[node]
        else:
            aggregations[node] = f'p{len(aggregations)}'
            return aggregations[node]

    def process_node(node):
        nonlocal aggregations

        if isinstance(node, dict) and 'op' in node:
            if node['op'] in ['sum', 'count', 'avg']:
                return {'variable': get_aggregation_mapping(convert_dict_to_key(node))}
            else:
                args = [process_node(arg) for arg in node.get('args', [])]
                return {'op': node['op'], 'args': args}
        elif isinstance(node, list):
            return [process_node(item) for item in node]
        else:
            return node

    post_aggregations = [process_node(select_col) for select_col in select_statement_cols]

    return get_aggregation_id_map(), post_aggregations


def is_operation(expression):
    return 'op' in expression


def is_column(arg) -> bool:
    return isinstance(arg, str)


def is_variable(arg) -> bool:
    return isinstance(arg, dict) and 'variable' in arg


def is_literal(arg) -> bool:
    return (isinstance(arg, dict) and "literal" in arg) or isinstance(arg, int)


def unpack_literal_value(arg) -> Union[int, str]:
    if isinstance(arg, dict) and "literal" in arg:
        return arg["literal"]
    return arg


def unpack_op_args(expression):
    return expression['op'], expression['args']


@dataclass
class ParsedQuery:
    select_statements: list
    where_conditions: dict[Any, Any]
    group_by_columns: list
    aggregate_expressions: dict
    post_aggregate_expressions: list

    @staticmethod
    def parse_from_sql(sql_statement):
        parsed = parse(sql_statement, calls=normal_op)
        select_statements = [column['value'] for column in listwrap(parsed.get('select'))]
        where_conditions = parsed.get('where', {})
        group_by_columns = [column['value'] for column in listwrap(parsed.get('groupby'))]
        aggregate_expressions, post_aggregate_expressions = extract_aggregations(select_statements)

        return ParsedQuery(
            select_statements=select_statements,
            where_conditions=where_conditions,
            group_by_columns=group_by_columns,
            aggregate_expressions=aggregate_expressions,
            post_aggregate_expressions=post_aggregate_expressions
        )
