from typing import Any


class ResultSet:
    def __init__(self, columns: list[str], row_count: int = -1):
        self.results: list[list[Any]] = []
        
        if row_count != -1:
          self.results = [[]]*row_count
          
        self.columns: list[str] = columns

    def append(self, row: list[Any]):
        self.results.append(row)
      
    def insert_at(self, i: int, row: list[Any]):
        self.results[i] = row

    def get_results(self) -> list[list[Any]]:
        return self.results
    
    def current_index(self) -> int:
      return len(self.results)
    
    def rearrange(self, index_order: list[int]):
      self.results = [self.results[index] for index in index_order]