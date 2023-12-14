import logging
import unittest
import pandas as pd
from mastidb.non_aggregate_segment_query_processor import NonAggregateSegmentQueryProcessor

from mastidb.parse_helpers import ParsedQuery
from mastidb.segment import Segment
from mastidb.segment_ingester import SegmentIngester


class TestSegmentIntegrationNonAggregate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load the data and create a common Segment instance for reuse
        segment = SegmentIngester.ingest('/tmp/wikidata', 'tests/datasets/wikipedia.json')
        cls.segment = Segment.load('/tmp/wikidata')

    def get_response(self, sql, headers):
        parsed_query = ParsedQuery.parse_from_sql(sql)
        buffer = NonAggregateSegmentQueryProcessor(self.segment, parsed_query=parsed_query).process_query().get_results()
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
        expected_list = [['92', '#en.wikipedia', 'None', '/* Extensions */', '16', 'US', 'United States', '0', '92', '0', 'https://en.wikipedia.org/w/index.php?diff=727271150&oldid=727270612', '', 'True', 'False', 'False', 'False', 'False', 'nan', 'Main', 'KeyCreator', 'IL', 'Illinois', '2016-06-27 21:23:20.497000+00:00', '12.145.185.163']]
        self.assertEqual(buffer, expected_list)

    @unittest.skip("SELECT * not supported")
    def test_select_star_with_sort(self):
        columns = ['added', 'channel', 'cityName', 'comment', 'commentLength', 'countryIsoCode', 'countryName', 'deleted', 'delta', 'deltaBucket', 'diffUrl', 'flags', 'isAnonymous', 'isMinor', 'isNew', 'isRobot', 'isUnpatrolled', 'metroCode', 'namespace', 'page', 'regionIsoCode', 'regionName', 'timestamp', 'user']
        sql = f"SELECT * FROM segment WHERE regionName='Illinois' ORDER BY user LIMIT 1"
        df, buffer = self.get_response(sql, columns)
        expected_list = [['92', '#en.wikipedia', 'None', '/* Extensions */', '16', 'US', 'United States', '0', '92', '0', 'https://en.wikipedia.org/w/index.php?diff=727271150&oldid=727270612', '', 'True', 'False', 'False', 'False', 'False', 'nan', 'Main', 'KeyCreator', 'IL', 'Illinois', '2016-06-27 21:23:20.497000+00:00', '12.145.185.163']]
        self.assertEqual(buffer, expected_list)
        
    @unittest.skip("metroCode is a float field because of NaN values therefore the bitmap search fails")
    def test_float64_column_filter(self):
        sql = f"SELECT metroCode FROM segment WHERE metroCode='602' ORDER BY metroCode LIMIT 5"
        df, buffer = self.get_response(sql, ['metroCode'])
        expected_list = [['602']]
        self.assertEqual(buffer, expected_list)
         
        
if __name__ == '__main__':
    unittest.main()
