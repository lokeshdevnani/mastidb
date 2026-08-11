import logging

from mastidb.non_aggregate_segment_query_processor import NonAggregateSegmentQueryProcessor
from mastidb.result_set import ResultSet
from .aggregator import Aggregator
from .non_aggregate_finalizer import NonAggregateFinalizer
from .parse_helpers import ParsedQuery, QueryType
from .partial_result import AggregatePartial
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
        parsed_query = ParsedQuery.parse_from_sql(sql, self.table.column_names())
        query_type = parsed_query.query_type
        logger.info('Query identifier as %s query', query_type)

        if query_type == QueryType.AGGREGATION:
            # Aggregation Functions are shared by segment aggregation and post-aggregation (p0, p1, ...).
            aggregation_functions = Aggregator.build_aggregation_functions(parsed_query.aggregate_expressions)
            partials = [
                AggregateSegmentQueryProcessor(
                    segment, parsed_query=parsed_query, aggregation_functions=aggregation_functions
                ).process_query()
                for segment in self.table.segments
            ]
            merged = AggregatePartial.merge(partials, aggregation_functions)
            logger.info("[execute] Performing Post-aggregation")
            return PostAggregator(parsed_query, aggregation_functions).perform_post_aggregation(merged)
        elif query_type == QueryType.NON_AGGREGATION:
            # FIXME: multi-segment fan-out / NonAggregatePartial merge not implemented yet.
            if len(self.table.segments) > 1:
                raise NotImplementedError("Non-aggregate queries over multiple segments are not supported yet")
            partial = NonAggregateSegmentQueryProcessor(
                self.table.segments[0], parsed_query=parsed_query
            ).process_query()
            return NonAggregateFinalizer(parsed_query).finalize(partial)
        else:
            raise NotImplementedError("Unknown query type: %s" % query_type)


if __name__ == '__main__':
    x = QueryExecutor.from_data_dir("/tmp/wikidata").execute("SELECT cityName order by cityName asc")

    print(x.get_results())
