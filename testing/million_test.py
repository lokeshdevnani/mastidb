import logging
import time
from pprint import pprint

from parse_helpers import ParsedQuery
from segment import Segment
from segment_query_processor import SegmentQueryProcessor


class PerfTest:
    def __init__(self):
        self.segment = Segment.load('/tmp/menuitem')
        self.results = []

    def get_results(self, sql):
        t0_total, t0_cpu = time.time(), time.process_time()
        parsed_query = ParsedQuery.parse_from_sql(sql)
        qp = SegmentQueryProcessor(self.segment, parsed_query)
        results = qp.process_query()
        time_total, time_cpu = time.time() - t0_total, time.process_time() - t0_cpu
        return results, time_total, time_cpu

    def record_run(self, sql):
        _, time_total, time_cpu = self.get_results(sql)
        print(f"Run finished for {sql}")
        self.results.append([sql, time_total, time_cpu])
        return self


# id,menu_page_id,price,high_price,dish_id,created_at,updated_at,xpos,ypos
def run():
    pt = PerfTest()
    pt.record_run("SELECT COUNT(id)")
    pt.record_run("SELECT menu_page_id, count(id) GROUP BY menu_page_id")
    pt.record_run("SELECT count(id) WHERE price = '0.25'")
    pt.record_run("SELECT COUNT(menu_page_id) WHERE dish_id ='1'")
    pt.record_run("SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id")
    print(pt.results)

# Results - Sat Nov 25 01:31:32 2023 +0530
 # ['SELECT COUNT(id)', 8.769065380096436, 8.742272],
 # ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 10.568114995956421, 10.551099],
 # ["SELECT count(id) WHERE price = '0.25'", 0.5852417945861816, 0.5835250000000016],
 # ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.0034050941467285156, 0.0034050000000007685],
 # ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 27.292393922805786, 27.211709999999997]

# Results - Sun Nov 26 01:25:32 2023 +0530 (Mypyc after adding types)
# ['SELECT COUNT(id)', 3.408392906188965, 3.404943]
# ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 4.0435850620269775, 4.039897]
# ["SELECT count(id) WHERE price = '0.25'", 0.22108221054077148, 0.2208509999999997]
# ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.003361940383911133, 0.0033620000000009753]
# ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 10.046894073486328, 10.038578999999999]]


# Results - (After using value matrix to dedup column fetch - Fetch is still iterative (non-batch))
# ['SELECT COUNT(id)', 3.6398770809173584, 3.6353199999999997]
# ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 4.444060802459717, 4.438077000000001]
# ["SELECT count(id) WHERE price = '0.25'", 0.25745320320129395, 0.2567850000000007]
# ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.0029723644256591797, 0.002957999999999572]
# ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 5.535712003707886, 5.530883999999999]


#
# [['SELECT COUNT(id)', 3.6876718997955322, 3.6422830000000004],
#  ['SELECT menu_page_id, count(id) GROUP BY menu_page_id',
#   3.6838231086730957,
#   3.679194999999999],
#  ["SELECT count(id) WHERE price = '0.25'",
#   0.28359293937683105,
#   0.2828499999999998],
#  ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'",
#   0.00292205810546875,
#   0.002920999999998841],
#  ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY '
#   'menu_page_id',
#   4.9840710163116455,
#   4.975963]]

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s')


if __name__ == '__main__':
    run()