import unittest

from mastidb.table import Table
from tests.helpers import QueryingTestCase


ILLINOIS_ROW = {
    'added': '92',
    'channel': '#en.wikipedia',
    'cityName': 'None',
    'comment': '/* Extensions */',
    'commentLength': '16',
    'countryIsoCode': 'US',
    'countryName': 'United States',
    'deleted': '0',
    'delta': '92',
    'deltaBucket': '0.0',
    'diffUrl': 'https://en.wikipedia.org/w/index.php?diff=727271150&oldid=727270612',
    'flags': '',
    'isAnonymous': 'True',
    'isMinor': 'False',
    'isNew': 'False',
    'isRobot': 'False',
    'isUnpatrolled': 'False',
    'metroCode': 'None',
    'namespace': 'Main',
    'page': 'KeyCreator',
    'regionIsoCode': 'IL',
    'regionName': 'Illinois',
    'timestamp': '2016-06-27T21:23:20.497Z',
    'user': '12.145.185.163',
}


class TestSegmentIntegrationNonAggregate(QueryingTestCase, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.table = Table.from_ingest_source('/tmp/wikidata', 'tests/datasets/wikipedia.json')

    def test_single_column_select_order_by(self):
        rows = self.query(
            "SELECT cityName FROM segment WHERE countryName = 'India' ORDER BY cityName LIMIT 100"
        )
        expected = [
            'Ahmedabad', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bengaluru',
            'Bengaluru', 'Bhandup', 'Chandigarh', 'Chandigarh', 'Chandigarh', 'Chennai',
            'Chennai', 'Chennai', 'Chennai', 'Chennai', 'Coimbatore', 'Dam Dam', 'Delhi',
            'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Dibrugarh', 'Erode',
            'Hyderabad', 'Hyderabad', 'Hyderabad', 'Hyderabad', 'Indore', 'Indore',
            'Kakinada', 'Kolkata', 'Mahim', 'Meenangadi', 'Mumbai', 'Mumbai', 'Mumbai',
            'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'New Delhi',
            'Noida', 'Panjim', 'Pathankot', 'Pune', 'Thiruvananthapuram', 'Thrissur',
            'Thrissur',
        ]
        self.assertEqual([name for name in rows.col('cityName') if name != 'None'], expected)

    def test_multicolumn_column_select_order_by(self):
        rows = self.query(
            "SELECT countryName, cityName, timestamp FROM segment "
            "WHERE countryName = 'India' ORDER BY cityName desc, timestamp LIMIT 10"
        )
        self.assertEqual(rows, [
            ['India', 'Thrissur', '2016-06-27T04:56:30.491Z'],
            ['India', 'Thrissur', '2016-06-27T13:14:24.333Z'],
            ['India', 'Thiruvananthapuram', '2016-06-27T06:47:47.514Z'],
            ['India', 'Pune', '2016-06-27T08:47:37.777Z'],
            ['India', 'Pathankot', '2016-06-27T05:13:42.629Z'],
            ['India', 'Panjim', '2016-06-27T14:44:48.828Z'],
            ['India', 'None', '2016-06-27T04:49:39.741Z'],
            ['India', 'None', '2016-06-27T05:53:13.371Z'],
            ['India', 'None', '2016-06-27T06:51:09.486Z'],
            ['India', 'None', '2016-06-27T06:59:33.963Z'],
        ])

    def test_select_all_columns_with_sort(self):
        columns = ', '.join(ILLINOIS_ROW)
        rows = self.query(
            f"SELECT {columns} FROM segment WHERE regionName='Illinois' ORDER BY user LIMIT 1"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ILLINOIS_ROW)

    def test_select_star_with_sort(self):
        rows = self.query(
            "SELECT * FROM segment WHERE regionName='Illinois' ORDER BY user LIMIT 1"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ILLINOIS_ROW)

    def test_metro_code_filter(self):
        rows = self.query(
            "SELECT metroCode FROM segment WHERE metroCode='602' ORDER BY metroCode LIMIT 5"
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows.col('metroCode'), ['602'] * 5)

    def test_select_with_limit_without_order_by(self):
        # Row order is not guaranteed without ORDER BY; only cardinality + filter correctness.
        rows = self.query(
            "SELECT cityName, countryName FROM segment WHERE countryName = 'India' LIMIT 5"
        )
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row['countryName'] == 'India' for row in rows))

    def test_empty_result_when_filter_matches_nothing(self):
        rows = self.query(
            "SELECT cityName FROM segment WHERE countryName = '__NO_SUCH_COUNTRY__' LIMIT 5"
        )
        self.assertEqual(rows, [])

    def test_and_filter_with_order_by(self):
        rows = self.query(
            "SELECT cityName FROM segment "
            "WHERE countryName = 'India' AND cityName = 'Mumbai' "
            "ORDER BY timestamp LIMIT 3"
        )
        self.assertEqual(rows, [['Mumbai'], ['Mumbai'], ['Mumbai']])

    def test_or_filter_select(self):
        rows = self.query(
            "SELECT countryName FROM segment "
            "WHERE countryName = 'India' OR countryName = 'Argentina' "
            "ORDER BY countryName LIMIT 200"
        )
        self.assertEqual(len(rows), 139)
        self.assertEqual(set(rows.col('countryName')), {'India', 'Argentina'})

    def test_order_by_add_expression(self):
        rows = self.query(
            "SELECT cityName, added, deleted FROM segment "
            "WHERE countryName = 'India' ORDER BY added + deleted DESC LIMIT 5"
        )
        self.assertEqual(rows, [
            ['None', '890', '0'],
            ['Dibrugarh', '0', '500'],
            ['Mumbai', '384', '0'],
            ['Hyderabad', '369', '0'],
            ['Mumbai', '320', '0'],
        ])


class TestMultiSegmentIntegrationNonAggregate(TestSegmentIntegrationNonAggregate):
    """Same non-aggregate tests against a 2-segment table."""

    @classmethod
    def setUpClass(cls):
        cls.table = Table.from_ingest_source(
            '/tmp/wikidata_multi', 'tests/datasets/wikipedia.json', num_segments=2
        )

    def test_loads_two_segments(self):
        self.assertEqual(len(self.table.segments), 2)


if __name__ == '__main__':
    unittest.main()
