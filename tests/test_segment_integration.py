import logging
import unittest
import pandas as pd

from mastidb.parse_helpers import ParsedQuery
from mastidb.segment import Segment
from mastidb.segment_query_processor import SegmentQueryProcessor
from mastidb.segment_ingester import SegmentIngester


class TestSegmentIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load the data and create a common Segment instance for reuse
        segment = SegmentIngester.ingest('/tmp/wikidata', 'tests/datasets/wikipedia.json')
        cls.segment = Segment.load('/tmp/wikidata')

    def get_response(self, sql, headers):
        parsed_query = ParsedQuery.parse_from_sql(sql)
        buffer = SegmentQueryProcessor(self.segment, parsed_query=parsed_query).process_query().get_results()
        df = pd.DataFrame(buffer, columns=headers)
        # df = pd.DataFrame(list(buffer.items()), columns=['Tuple', 'List'])
        # # Flatten the Tuple and List columns
        # df[['k{}'.format(i) for i in range(len(df['Tuple'][0]))]] = pd.DataFrame(df['Tuple'].tolist(), index=df.index)
        # df[['v{}'.format(i) for i in range(len(df['List'][0]))]] = pd.DataFrame(df['List'].tolist(), index=df.index)
        #
        # # Drop the original Tuple and List columns
        # df = df.drop(['Tuple', 'List'], axis=1)
        return df, buffer

    def test_group_by_sum(self):
        sql = "SELECT cityName, SUM(added), COUNT(added) FROM segment WHERE countryName = 'India' GROUP BY cityName"
        df, buffer = self.get_response(sql, ['cityName', 'sum_added', 'count_added'])
        self.assertEqual(df[df.cityName == 'Bengaluru'].values.tolist(), [['Bengaluru', 134, 6]])
        self.assertEqual(df[df.cityName == 'Delhi'].values.tolist(), [['Delhi', 123, 7]])
        self.assertEqual(df['sum_added'].sum(), 4360)
        self.assertEqual(df['count_added'].sum(), 79)

    def test_count_without_filter(self):
        sql = "SELECT COUNT(added) FROM segment"
        df, buffer = self.get_response(sql, ['count_added'])
        self.assertEqual(df.values.tolist(), [[24433]])

    def test_sum_of_added_by_channel(self):
        sql = "SELECT channel, SUM(added) FROM dataset GROUP BY channel"
        df, buffer = self.get_response(sql, ['channel', 'sum_added'])
        self.assertEqual(df[df.channel == '#en.wikipedia']['sum_added'].sum(), 2068620)
        self.assertEqual(df[df.channel == '#sv.wikipedia']['sum_added'].sum(), 2748599)

    def test_average_comment_length_by_country(self):
        sql = "SELECT countryName, AVG(commentLength) FROM dataset GROUP BY countryName"
        df, buffer = self.get_response(sql, ['countryName', 'avg_comment_length'])
        self.assertAlmostEqual(df[df.countryName == 'Argentina']['avg_comment_length'].mean(), 25.6, places=1)

    @unittest.skip("boolean not supported")
    def test_count_of_minor_edits_by_namespace(self):
        sql = "SELECT namespace, COUNT(*) FROM dataset WHERE isMinor = 'true' GROUP BY namespace"
        df, buffer = self.get_response(sql, ['namespace', 'count'])
        self.assertEqual(df[df.namespace == 'Main']['count'].iloc[0], 1)

    @unittest.skip("DATE() not supported")
    def test_comments_per_day_in_june_2016(self):
        sql = "SELECT DATE(timestamp) as day, COUNT(*) as comments_per_day FROM dataset WHERE timestamp BETWEEN '2016-06-01' AND '2016-06-30' GROUP BY day"
        df, buffer = self.get_response(sql, ['day', 'comments_per_day'])
        self.assertEqual(df[df.day == '2016-06-27']['comments_per_day'].sum(), 2)

    @unittest.skip("ORDER BY and LIMIT not supported")
    def test_top_users_by_comment_length(self):
        sql = "SELECT user, SUM(commentLength) as total_comment_length FROM dataset GROUP BY user ORDER BY total_comment_length DESC LIMIT 5"
        df, buffer = self.get_response(sql, ['user', 'total_comment_length'])
        self.assertEqual(df.iloc[0]['user'], 'Lsjbot')
        self.assertEqual(df.iloc[0]['total_comment_length'], 35)
        self.assertEqual(df.iloc[1]['user'], '181.230.118.178')
        self.assertEqual(df.iloc[1]['total_comment_length'], 12)


if __name__ == '__main__':
    unittest.main()
