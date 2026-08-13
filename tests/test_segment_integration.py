import unittest

from mastidb.table import Table
from tests.helpers import QueryingTestCase


WIKIDATA_SOURCE = 'tests/datasets/wikipedia.json'


class TestSegmentIntegration(QueryingTestCase, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.table = Table.from_ingest_source('/tmp/wikidata', WIKIDATA_SOURCE)

    def test_group_by_sum(self):
        rows = self.query(
            "SELECT cityName, SUM(added) AS sum_added, COUNT(added) AS count_added "
            "FROM segment WHERE countryName = 'India' GROUP BY cityName"
        )
        by_city = rows.by('cityName')
        self.assertEqual(by_city['Bengaluru'], {'cityName': 'Bengaluru', 'sum_added': 134, 'count_added': 6})
        self.assertEqual(by_city['Delhi'], {'cityName': 'Delhi', 'sum_added': 123, 'count_added': 7})
        self.assertEqual(sum(rows.col('sum_added')), 4360)
        self.assertEqual(sum(rows.col('count_added')), 79)

    def test_count_without_filter(self):
        rows = self.query("SELECT COUNT(added) FROM segment")
        self.assertEqual(rows, [[24433]])

    def test_count_star_without_filter(self):
        rows = self.query("SELECT COUNT(*) FROM segment")
        self.assertEqual(rows, [[24433]])

    def test_sum_of_added_by_channel(self):
        rows = self.query("SELECT channel, SUM(added) AS sum_added FROM dataset GROUP BY channel")
        by_channel = rows.by('channel')
        self.assertEqual(by_channel['#en.wikipedia']['sum_added'], 2068620)
        self.assertEqual(by_channel['#sv.wikipedia']['sum_added'], 2748599)

    def test_average_comment_length_by_country(self):
        rows = self.query(
            "SELECT countryName, AVG(commentLength) AS avg_comment_length "
            "FROM dataset GROUP BY countryName"
        )
        self.assertAlmostEqual(
            rows.by('countryName')['Argentina']['avg_comment_length'], 25.6, places=1
        )

    def test_distinct_count(self):
        rows = self.query(
            "SELECT COUNT(DISTINCT isRobot) AS distinct_count, COUNT(isRobot) AS count "
            "FROM dataset GROUP BY isNew"
        )
        self.assertEqual(rows, [[2, 3221], [2, 21212]])

    @unittest.skip("boolean not supported")
    def test_count_of_minor_edits_by_namespace(self):
        rows = self.query(
            "SELECT namespace, COUNT(*) AS count FROM dataset "
            "WHERE isMinor = 'true' GROUP BY namespace"
        )
        self.assertEqual(rows.by('namespace')['Main']['count'], 1)

    @unittest.skip("DATE() not supported")
    def test_comments_per_day_in_june_2016(self):
        rows = self.query(
            "SELECT DATE(timestamp) AS day, COUNT(*) AS comments_per_day "
            "FROM dataset WHERE timestamp BETWEEN '2016-06-01' AND '2016-06-30' GROUP BY day"
        )
        self.assertEqual(rows.by('day')['2016-06-27']['comments_per_day'], 2)

    def test_top_users_by_comment_length(self):
        rows = self.query(
            "SELECT user, SUM(commentLength) AS total_comment_length "
            "FROM dataset GROUP BY user ORDER BY SUM(commentLength) DESC LIMIT 5"
        )
        self.assertEqual(rows[0]['user'], 'Kolega2357')
        self.assertEqual(rows[0]['total_comment_length'], 467634)
        self.assertEqual(rows[1]['user'], 'EmausBot')
        self.assertEqual(rows[1]['total_comment_length'], 144260)

    @unittest.skip("FIXME: ORDER BY on decoded string group keys (see build_sort_tuple_from_sort_order)")
    def test_lexicographic_multisort_with_opposite_directions(self):
        rows = self.query(
            "SELECT countryName, cityName, SUM(commentLength) AS total_comment_length "
            "FROM dataset WHERE countryName='India' GROUP BY countryName, cityName "
            "ORDER BY countryName asc, cityName desc LIMIT 3"
        )
        self.assertEqual(rows.col('countryName'), ['India', 'India', 'India'])
        self.assertEqual(rows.col('cityName'), ['Thrissur', 'Thiruvananthapuram', 'Pune'])

    def test_empty_group_by_when_filter_matches_nothing(self):
        rows = self.query(
            "SELECT cityName, COUNT(*) FROM segment "
            "WHERE countryName = '__NO_SUCH_COUNTRY__' GROUP BY cityName"
        )
        self.assertEqual(rows, [])

    def test_or_filter_count(self):
        rows = self.query(
            "SELECT COUNT(*) FROM segment WHERE countryName = 'India' OR countryName = 'Argentina'"
        )
        self.assertEqual(rows, [[139]])

    def test_and_filter_count(self):
        rows = self.query(
            "SELECT COUNT(*) FROM segment WHERE countryName = 'India' AND cityName = 'Mumbai'"
        )
        self.assertEqual(rows, [[9]])


class TestMultiSegmentIntegration(TestSegmentIntegration):
    """Same tests as single-segment, against a 2-segment table."""

    @classmethod
    def setUpClass(cls):
        cls.table = Table.from_ingest_source(
            '/tmp/wikidata_multi', WIKIDATA_SOURCE, num_segments=2
        )

    def test_loads_two_segments(self):
        self.assertEqual(len(self.table.segments), 2)


if __name__ == '__main__':
    unittest.main()
