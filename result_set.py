class ResultSet:
    def __init__(self, columns: list[str]):
        self.results = []
        self.columns = columns

    def append(self, row):
        self.results.append(row)

    def get_results(self):
        return self.results
