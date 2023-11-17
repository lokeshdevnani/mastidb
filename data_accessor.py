

class DataAccessor:
    def __init__(self, filepath):
        self.filepath = filepath + ".mastidb"
        self.filepath_metadata = filepath + ".metadata"

    def fetch(self, start, end) -> bytes:
        with open(self.filepath, 'rb') as file:
            file.seek(start)
            binary_data = file.read(end - start)
            return binary_data

    def fetch_all(self) -> bytes:
        with open(self.filepath, 'rb') as file:
            return file.read()

    def write(self, binary_data):
        with open(self.filepath, 'wb') as file:
            file.write(binary_data)
        print("Written to filepath: " + self.filepath)

    def fetch_metadata(self) -> bytes:
        with open(self.filepath_metadata, 'rb') as file:
            return file.read()

    def write_metadata(self, binary_data):
        with open(self.filepath_metadata, 'wb') as file:
            file.write(binary_data)
        print("Written to filepath: " + self.filepath_metadata)
