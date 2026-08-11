import unittest
import pandas as pd

from mastidb.query_executor import QueryExecutor
from mastidb.table import Table


class TestSegmentIntegrationNonAggregate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.table = Table.from_ingest_source('/tmp/wikidata', 'tests/datasets/wikipedia.json')

    def get_response(self, sql, headers):
        buffer = QueryExecutor(self.table).execute(sql).get_results()
        df = pd.DataFrame(buffer, columns=headers)
        return df, buffer

    def test_single_column_select_order_by(self):
        sql = "SELECT cityName FROM segment WHERE countryName = 'India' ORDER BY cityName LIMIT 100"
        df, buffer = self.get_response(sql, ['cityName'])
        expected_list = ['Ahmedabad', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bengaluru', 'Bhandup', 'Chandigarh', 'Chandigarh', 'Chandigarh', 'Chennai', 'Chennai', 'Chennai', 'Chennai', 'Chennai', 'Coimbatore', 'Dam Dam', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Delhi', 'Dibrugarh', 'Erode', 'Hyderabad', 'Hyderabad', 'Hyderabad', 'Hyderabad', 'Indore', 'Indore', 'Kakinada', 'Kolkata', 'Mahim', 'Meenangadi', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'Mumbai', 'New Delhi', 'Noida', 'Panjim', 'Pathankot', 'Pune', 'Thiruvananthapuram', 'Thrissur', 'Thrissur']
        self.assertEqual([x[0] for x in buffer if x[0] != 'None'], expected_list)
    
    def test_multicolumn_column_select_order_by(self):
        sql = "SELECT countryName, cityName, timestamp FROM segment WHERE countryName = 'India' ORDER BY cityName desc, timestamp LIMIT 10"
        df, buffer = self.get_response(sql, ['countryName', 'cityName', 'timestamp'])
        expected_list = [['India', 'Thrissur', '2016-06-27 04:56:30.491000+00:00'], ['India', 'Thrissur', '2016-06-27 13:14:24.333000+00:00'], ['India', 'Thiruvananthapuram', '2016-06-27 06:47:47.514000+00:00'], ['India', 'Pune', '2016-06-27 08:47:37.777000+00:00'], ['India', 'Pathankot', '2016-06-27 05:13:42.629000+00:00'], ['India', 'Panjim', '2016-06-27 14:44:48.828000+00:00'], ['India', 'None', '2016-06-27 04:49:39.741000+00:00'], ['India', 'None', '2016-06-27 05:53:13.371000+00:00'], ['India', 'None', '2016-06-27 06:51:09.486000+00:00'], ['India', 'None', '2016-06-27 06:59:33.963000+00:00']]
        self.assertEqual(buffer, expected_list)
    
    def test_select_all_columns_with_sort(self):
        columns = ['added', 'channel', 'cityName', 'comment', 'commentLength', 'countryIsoCode', 'countryName', 'deleted', 'delta', 'deltaBucket', 'diffUrl', 'flags', 'isAnonymous', 'isMinor', 'isNew', 'isRobot', 'isUnpatrolled', 'metroCode', 'namespace', 'page', 'regionIsoCode', 'regionName', 'timestamp', 'user']
        sql = f"SELECT {', '.join(columns)} FROM segment WHERE regionName='Illinois' ORDER BY user LIMIT 1"
        df, buffer = self.get_response(sql, columns)
        self.assertEqual(len(buffer), 1)
        
        expected_list = ['92', '#en.wikipedia', 'None', '/* Extensions */', '16', 'US', 'United States', '0', '92', '0', 'https://en.wikipedia.org/w/index.php?diff=727271150&oldid=727270612', '', 'True', 'False', 'False', 'False', 'False', 'nan', 'Main', 'KeyCreator', 'IL', 'Illinois', '2016-06-27 21:23:20.497000+00:00', '12.145.185.163']
        self.assertEqual(buffer[0], expected_list)

    def test_select_star_with_sort(self):
        columns = ['added', 'channel', 'cityName', 'comment', 'commentLength', 'countryIsoCode', 'countryName', 'deleted', 'delta', 'deltaBucket', 'diffUrl', 'flags', 'isAnonymous', 'isMinor', 'isNew', 'isRobot', 'isUnpatrolled', 'metroCode', 'namespace', 'page', 'regionIsoCode', 'regionName', 'timestamp', 'user']
        sql = f"SELECT * FROM segment WHERE regionName='Illinois' ORDER BY user LIMIT 1"
        df, buffer = self.get_response(sql, columns)
        self.assertEqual(len(buffer), 1)
        
        expected_list = ['92', '#en.wikipedia', 'None', '/* Extensions */', '16', 'US', 'United States', '0', '92', '0', 'https://en.wikipedia.org/w/index.php?diff=727271150&oldid=727270612', '', 'True', 'False', 'False', 'False', 'False', 'nan', 'Main', 'KeyCreator', 'IL', 'Illinois', '2016-06-27 21:23:20.497000+00:00', '12.145.185.163']
        self.assertCountEqual(buffer[0], expected_list)
        
    @unittest.skip("metroCode is a float field because of NaN values therefore the bitmap search fails")
    def test_float64_column_filter(self):
        sql = f"SELECT metroCode FROM segment WHERE metroCode='602' ORDER BY metroCode LIMIT 5"
        df, buffer = self.get_response(sql, ['metroCode'])
        expected_list = [['602']]
        self.assertEqual(buffer, expected_list)

    def test_select_with_limit_without_order_by(self):
        # Row order is not guaranteed without ORDER BY; only cardinality + filter correctness.
        sql = "SELECT cityName, countryName FROM segment WHERE countryName = 'India' LIMIT 5"
        df, buffer = self.get_response(sql, ['cityName', 'countryName'])
        self.assertEqual(len(buffer), 5)
        self.assertTrue(all(row[1] == 'India' for row in buffer))

    def test_empty_result_when_filter_matches_nothing(self):
        sql = "SELECT cityName FROM segment WHERE countryName = '__NO_SUCH_COUNTRY__' LIMIT 5"
        df, buffer = self.get_response(sql, ['cityName'])
        self.assertEqual(buffer, [])

    def test_and_filter_with_order_by(self):
        sql = ("SELECT cityName FROM segment "
               "WHERE countryName = 'India' AND cityName = 'Mumbai' "
               "ORDER BY timestamp LIMIT 3")
        df, buffer = self.get_response(sql, ['cityName'])
        self.assertEqual(buffer, [['Mumbai'], ['Mumbai'], ['Mumbai']])

    def test_or_filter_select(self):
        sql = ("SELECT countryName FROM segment "
               "WHERE countryName = 'India' OR countryName = 'Argentina' "
               "ORDER BY countryName LIMIT 200")
        df, buffer = self.get_response(sql, ['countryName'])
        self.assertEqual(len(buffer), 139)
        self.assertEqual(set(row[0] for row in buffer), {'India', 'Argentina'})
        
if __name__ == '__main__':
    unittest.main()
