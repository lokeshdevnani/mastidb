import time

import pandas as pd

from segment import Segment
from parse_helpers import ParsedQuery
from segment_query_processor import SegmentQueryProcessor


if __name__ == '__main__':


    data = pd.read_csv("MenuItem.csv")
    df = pd.DataFrame(data)
    # segment = Segment.create('/tmp/menuitem', df)
    segment = Segment.load('/tmp/menuitem')



    sql = """
        SELECT COUNT(id) 
        FROM segment
    """
    t0 = time.time()
    parsed_query = ParsedQuery.parse_from_sql(sql)
    qp = SegmentQueryProcessor(segment, parsed_query)
    print(qp.process_query())
    print(time.time() - t0)

