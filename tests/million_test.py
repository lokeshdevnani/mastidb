import cProfile
import logging
import time

from mastidb.query_executor import QueryExecutor
from mastidb.table import Table


# Fetch this file first: mastidb demo menuitem
#   (or: python scripts/download_menu_dataset.py)
MENUITEM_SOURCE = 'tests/dataset_menu/MenuItem.csv'


class PerfTest:
    def __init__(self, table: Table):
        self.table = table
        self.results = []

    def get_results(self, sql):
        t0_total, t0_cpu = time.time(), time.process_time()
        results = QueryExecutor(self.table).execute(sql)
        time_total, time_cpu = time.time() - t0_total, time.process_time() - t0_cpu
        return results, time_total, time_cpu

    def record_run(self, sql):
        _, time_total, time_cpu = self.get_results(sql)
        print(f"Run finished for {sql}")
        self.results.append([sql, time_total, time_cpu])
        return self


# id,menu_page_id,price,high_price,dish_id,created_at,updated_at,xpos,ypos
def run():
    # Load an already-built table (default). To rebuild / split:
    # table = Table.from_ingest_source('/tmp/menuitem', MENUITEM_SOURCE)
    # table = Table.from_ingest_source('/tmp/menuitem_multi', MENUITEM_SOURCE, num_segments=2)
    table = Table.from_data_dir('/tmp/menuitem')
    pt = PerfTest(table)
    pt.record_run("SELECT COUNT(id)")
    pt.record_run("SELECT menu_page_id, count(id) GROUP BY menu_page_id")
    pt.record_run("SELECT count(id) WHERE price = '0.25'")
    pt.record_run("SELECT COUNT(menu_page_id) WHERE dish_id ='1'")
    pt.record_run("SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id")
    pt.record_run("SELECT menu_page_id, COUNT(id) GROUP BY menu_page_id ORDER BY COUNT(id) DESC LIMIT 10")
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

# Results - Mon Dec 04
#  ['SELECT COUNT(id)', 1.9458749294281006, 1.7726420000000047]
#  ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 1.8870940208435059, 1.8507920000000055]
#  ["SELECT count(id) WHERE price = '0.25'", 0.13679981231689453, 0.13428099999999432]
#  ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.010632038116455078, 0.0041379999999975325]
#  ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 2.731924057006836, 2.700136999999998]


# Results - Mon Dec 04 23:00 (Post pushing down cast operation)
# [['SELECT COUNT(id)', 1.692824125289917, 1.5971440000000001], ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 1.7722468376159668, 1.7523300000000002], ["SELECT count(id) WHERE price = '0.25'", 0.1878800392150879, 0.15658299999999992], ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.0086669921875, 0.004997999999999614], ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 2.882625102996826, 2.8611500000000003]]

# Results - Tue Aug 11 2026 (warm, mypyc)
# [['SELECT COUNT(id)', 1.446],
#  ['SELECT menu_page_id, count(id) GROUP BY menu_page_id', 1.976],
#  ["SELECT count(id) WHERE price = '0.25'", 0.153],
#  ["SELECT COUNT(menu_page_id) WHERE dish_id ='1'", 0.003],
#  ['SELECT COUNT(price), SUM(price), AVG(price), menu_page_id GROUP BY menu_page_id', 3.013],
#  ['SELECT menu_page_id, COUNT(id) GROUP BY menu_page_id ORDER BY COUNT(id) DESC LIMIT 10', 2.084]]
#
# GROUP BYs are a bit slower vs Dec 04 because we added an extra step: decode group keys
# and rebuild the hash map into AggregatePartial (for multi-segment merge).


logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s')


if __name__ == '__main__':
  run()
  # cProfile.run('run()', sort='tottime')