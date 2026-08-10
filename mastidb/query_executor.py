import logging

from mastidb.non_aggregate_segment_query_processor import NonAggregateSegmentQueryProcessor
from mastidb.result_set import ResultSet
from .parse_helpers import ParsedQuery, QueryType
from .segment import Segment
from .segment_ingester import SegmentIngester
from .aggregate_segment_query_processor import AggregateSegmentQueryProcessor

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self, segment: Segment):
        self.segment = segment

    @staticmethod
    def from_data_dir(data_dir: str) -> 'QueryExecutor':
        segment = Segment.load(data_dir)
        return QueryExecutor(segment)

    @staticmethod
    def from_ingest_source(data_dir: str, source_file: str) -> 'QueryExecutor':
        segment = SegmentIngester.ingest(data_dir, source_file)
        return QueryExecutor(segment)

    def execute(self, sql: str) -> ResultSet:
        parsed_query = ParsedQuery.parse_from_sql(sql, self.segment.column_names())
        query_type = parsed_query.query_type
        logger.info('Query identifier as %s query', query_type)

        if query_type == QueryType.AGGREGATION:
            processor = AggregateSegmentQueryProcessor(self.segment, parsed_query=parsed_query)
            partial = processor.process_query()
            logger.info("[execute] Performing Post-aggregation")
            return processor.perform_post_aggregation(partial)
        elif query_type == QueryType.NON_AGGREGATION:
            return NonAggregateSegmentQueryProcessor(self.segment, parsed_query=parsed_query).process_query()
        else:
            raise NotImplementedError("Unknown query type: %s" % query_type)


if __name__ == '__main__':
    x = QueryExecutor.from_data_dir("/tmp/wikidata").execute("SELECT cityName order by cityName asc")

    print(x.get_results())
