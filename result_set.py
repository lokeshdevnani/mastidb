from typing import Any


class ResultSet:
    def __init__(self, columns: list[str]):
        self.results: list[list[Any]] = []
        self.columns: list[str] = columns

    def append(self, row: list[Any]):
        self.results.append(row)

    def get_results(self) -> list[list[Any]]:
        return self.results
