import logging

from mastidb.non_aggregate_segment_query_processor import NonAggregateSegmentQueryProcessor
from mastidb.result_set import ResultSet
from .aggregator import Aggregator
from .parse_helpers import ParsedQuery, QueryType
from .post_aggregator import PostAggregator
from .table import Table
from .aggregate_segment_query_processor import AggregateSegmentQueryProcessor

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self, table: Table):
        self.table = table

    @staticmethod
    def from_data_dir(data_dir: str) -> 'QueryExecutor':
        return QueryExecutor(Table.from_data_dir(data_dir))

    @staticmethod
    def from_ingest_source(data_dir: str, source_file: str) -> 'QueryExecutor':
        return QueryExecutor(Table.from_ingest_source(data_dir, source_file))

    def execute(self, sql: str) -> ResultSet:
        # Single-segment path for now; fan-out over self.table.segments comes later.
        segment = self.table.segments[0]
        parsed_query = ParsedQuery.parse_from_sql(sql, self.table.column_names())
        query_type = parsed_query.query_type
        logger.info('Query identifier as %s query', query_type)

        if query_type == QueryType.AGGREGATION:
            # Aggregation Functions are shared by segment aggregation and post-aggregation (p0, p1, ...).
            aggregation_functions = Aggregator.build_aggregation_functions(parsed_query.aggregate_expressions)
            partial = AggregateSegmentQueryProcessor(
                segment, parsed_query=parsed_query, aggregation_functions=aggregation_functions).process_query()
            logger.info("[execute] Performing Post-aggregation")
            return PostAggregator(parsed_query, aggregation_functions).perform_post_aggregation(partial)
        elif query_type == QueryType.NON_AGGREGATION:
            return NonAggregateSegmentQueryProcessor(segment, parsed_query=parsed_query).process_query()
        else:
            raise NotImplementedError("Unknown query type: %s" % query_type)


if __name__ == '__main__':
    x = QueryExecutor.from_data_dir("/tmp/wikidata").execute("SELECT cityName order by cityName asc")

    print(x.get_results())
