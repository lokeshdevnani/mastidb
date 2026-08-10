import logging
import unittest
import pandas as pd

from mastidb.query_executor import QueryExecutor
from mastidb.segment import Segment
from mastidb.segment_ingester import SegmentIngester
from mastidb.table import Table


class TestSegmentIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load the data and create a common Segment instance for reuse
        segment = SegmentIngester.ingest('/tmp/wikidata', 'tests/datasets/wikipedia.json')
        cls.segment = Segment.load('/tmp/wikidata')

    def get_response(self, sql, headers):
        buffer = QueryExecutor(Table([self.segment])).execute(sql).get_results()
        df = pd.DataFrame(buffer, columns=headers)
        return df, buffer

    def test_group_by_sum(self):
        sql = "SELECT cityName, SUM(added), COUNT(added) FROM segment WHERE countryName = 'India' GROUP BY cityName"
        df, buffer = self.get_response(sql, ['cityName', 'sum_added', 'count_added'])
        self.assertEqual(df[df.cityName == 'Bengaluru'].iloc[0].tolist(), ['Bengaluru', 134, 6])
        self.assertEqual(df[df.cityName == 'Delhi'].iloc[0].tolist(), ['Delhi', 123, 7])
        self.assertEqual(df['sum_added'].sum(), 4360)
        self.assertEqual(df['count_added'].sum(), 79)

    def test_count_without_filter(self):
        sql = "SELECT COUNT(added) FROM segment"
        df, buffer = self.get_response(sql, ['count_added'])
        self.assertEqual(df.values.tolist(), [[24433]])
        
    def test_count_star_without_filter(self):
        sql = "SELECT COUNT(*) FROM segment"
        df, buffer = self.get_response(sql, ['count'])
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

    def test_distinct_count(self):
        sql = "SELECT COUNT(DISTINCT isRobot), COUNT(isRobot) FROM dataset GROUP BY isNew"
        df, buffer = self.get_response(sql, ['distinct_count', 'count'])
        self.assertEqual(df.values.tolist(), [[2, 3221], [2, 21212]])

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

    def test_top_users_by_comment_length(self):
        sql = "SELECT user, SUM(commentLength) as total_comment_length FROM dataset GROUP BY user ORDER BY total_comment_length DESC LIMIT 5"
        sql = "SELECT user, SUM(commentLength) as total_comment_length FROM dataset GROUP BY user ORDER BY SUM(commentLength) DESC LIMIT 5"
        df, buffer = self.get_response(sql, ['user', 'total_comment_length'])
        self.assertEqual(df['user'][0], 'Kolega2357')
        self.assertEqual(df['total_comment_length'][0], 467634)
        self.assertEqual(df['user'][1], 'EmausBot')
        self.assertEqual(df['total_comment_length'][1], 144260)
        
    @unittest.skip("FIXME: ORDER BY on decoded string group keys (see build_sort_tuple_from_sort_order)")
    def test_lexicographic_multisort_with_opposite_directions(self):
        sql = "SELECT countryName, cityName, SUM(commentLength) as total_comment_length FROM dataset WHERE countryName='India' GROUP BY countryName, cityName ORDER BY countryName asc, cityName desc LIMIT 3"
        df, buffer = self.get_response(sql, ['countryName', 'cityName', 'total_comment_length'])
        
        self.assertEqual(df['countryName'].tolist(), ['India', 'India', 'India'])
        self.assertEqual(df['cityName'].tolist(), ['Thrissur', 'Thiruvananthapuram', 'Pune'])

    def test_empty_group_by_when_filter_matches_nothing(self):
        sql = ("SELECT cityName, COUNT(*) FROM segment "
               "WHERE countryName = '__NO_SUCH_COUNTRY__' GROUP BY cityName")
        df, buffer = self.get_response(sql, ['cityName', 'count'])
        self.assertEqual(buffer, [])

    def test_or_filter_count(self):
        sql = "SELECT COUNT(*) FROM segment WHERE countryName = 'India' OR countryName = 'Argentina'"
        df, buffer = self.get_response(sql, ['count'])
        self.assertEqual(buffer, [[139]])

    def test_and_filter_count(self):
        sql = "SELECT COUNT(*) FROM segment WHERE countryName = 'India' AND cityName = 'Mumbai'"
        df, buffer = self.get_response(sql, ['count'])
        self.assertEqual(buffer, [[9]])
        
        
if __name__ == '__main__':
    unittest.main()
