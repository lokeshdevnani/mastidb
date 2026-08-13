from enum import Enum
import json
from dataclasses import dataclass
from typing import Any, Union, Tuple

from mo_sql_parsing import parse, normal_op, format # type: ignore


def listwrap(value):
    if value is None:
        return []
    elif isinstance(value, list):
        return value
    else:
        return [value]


def extract_aggregations(select_statement_cols: list[dict[str, Any]], 
                         order_by_cols: list[dict[str, Any]]):
    aggregations: dict[str, str] = {}
    
    def clean_aggregate_expression(expression):
      op, args = unpack_op_args(expression)
      if op == 'count' and "*" in args:
        # neutralize the COUNT(*) to COUNT(1) to avoid fetching all columns
        expression['args'] = [{'literal': 1}]
      return expression

    def convert_dict_to_key(d):
        return json.dumps(d)

    def get_aggregation_id_map():
        return {value: clean_aggregate_expression(json.loads(key)) 
                for key, value in aggregations.items()}

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

    post_aggregations = [process_node(select_col['value']) for select_col in select_statement_cols]
    substituted_order_by_cols = [{**order_col, 'value': process_node(order_col['value'])} for order_col in order_by_cols]

    return get_aggregation_id_map(), post_aggregations, substituted_order_by_cols


def get_dependent_columns(select_statement_cols: list[dict]) -> list[str]:
    dependent_columns: list[str] = []

    def process_node(current_node):
        nonlocal dependent_columns

        if isinstance(current_node, dict) and 'args' in current_node:
            [process_node(arg) for arg in current_node.get('args', [])]
        elif is_literal(current_node):
            pass
        elif isinstance(current_node, list):
            [process_node(item) for item in current_node]
        else:
            dependent_columns.append(current_node)

    for select_col in select_statement_cols:
        if select_col == "*":
          raise ValueError("* NOT supported")
        process_node(select_col['value'])

    return list(set(dependent_columns) - set('*'))

def convert_star_to_column_list(select_statement_cols: list[Union[str, dict]], column_list: list[str]) -> list[dict]:
    transformed_list: list[dict] = []
    for select_col in select_statement_cols:    
        if select_col == "*":
            print('*', column_list)
            transformed_list += [{'value': col} for col in column_list]
        else:
            assert isinstance(select_col, dict)
            transformed_list.append(select_col)
    return transformed_list


def is_operation(expression) -> bool:
    return 'op' in expression


def is_column(arg: Union[str, dict]) -> bool:
    return isinstance(arg, str)


def is_variable(arg) -> bool:
    return isinstance(arg, dict) and 'variable' in arg


def is_literal(arg) -> bool:
    return (isinstance(arg, dict) and "literal" in arg) or isinstance(arg, int)


def unpack_literal_value(arg) -> Union[int, str]:
    if isinstance(arg, dict) and "literal" in arg:
        return arg["literal"]
    return arg


def unpack_op_args(expression) -> Tuple[str, list[Any]]:
    return expression['op'], expression['args']


def unparse(input_expression) -> str:
    def format_parsed_sql(input_dict):
        result = {}

        if 'op' in input_dict and 'args' in input_dict:
            op, args = input_dict['op'], input_dict['args']
            result[op] = args
            for arg in args:
                if isinstance(arg, dict):
                    result.update(format_parsed_sql(arg))
        else:
            return input_dict
        return result

    return format(format_parsed_sql(input_expression))


def _get_output_cols(select_cols):
    return [select_col.get('name', unparse(select_col['value'])) for select_col in select_cols]


class QueryType(Enum):
    AGGREGATION = 1
    NON_AGGREGATION = 2

@dataclass
class ParsedQuery:
    select_statements: list
    where_conditions: dict[Any, Any]
    group_by_columns: list
    order_by_columns: list[dict[str, Any]]
    aggregate_expressions: dict
    post_aggregate_expressions: list
    dependent_columns: list[str]
    output_columns: list[str]
    query_type: QueryType
    limit: Union[int, None]

    @staticmethod
    def parse_from_sql(sql_statement: str, column_list: list[str]) -> 'ParsedQuery':
        parsed = parse(sql_statement, calls=normal_op)
        select_statements = listwrap(parsed.get('select'))
        select_statements = convert_star_to_column_list(select_statements, column_list)
        where_conditions = parsed.get('where', {})
        group_by_columns = listwrap(parsed.get('groupby'))
        order_by_columns = listwrap(parsed.get('orderby'))
        dependent_columns = get_dependent_columns(select_statements + group_by_columns + order_by_columns)
        aggregate_expressions, post_aggregate_expressions, order_by_columns = extract_aggregations(select_statements, order_by_columns)
        limit = parsed.get('limit')
        
        if len(aggregate_expressions) > 0 or len(group_by_columns) > 0:
          query_type = QueryType.AGGREGATION
        else:
          query_type = QueryType.NON_AGGREGATION

        return ParsedQuery(
            select_statements=select_statements,
            where_conditions=where_conditions,
            group_by_columns=[column['value'] for column in group_by_columns],
            order_by_columns=[column for column in order_by_columns],
            limit=limit,
            aggregate_expressions=aggregate_expressions,
            post_aggregate_expressions=post_aggregate_expressions,
            dependent_columns=dependent_columns,
            output_columns=_get_output_cols(select_statements),
            query_type=query_type
        )
