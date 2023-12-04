import logging
import mmap

logger = logging.getLogger(__name__)

class Fetcher:
    def __init__(self, file):
        raise NotImplementedError()

    def fetch(self, start, end) -> bytes:
        raise NotImplementedError()


class MmapFetcher:
    def __init__(self, file):
        self.mm = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)

    def fetch(self, start, end):
        return self.mm[start:end]


class FileSeekFetcher:
    def __init__(self, file):
        self.file = file

    def fetch(self, start, end):
        self.file.seek(start)
        return self.file.read(end - start)


class DataAccessor:
    def __init__(self, filepath):
        self.filepath = filepath + ".mastidb"
        self.filepath_metadata = filepath + ".metadata"
        self.file = None
        self.fetcher = None

    def open(self, mode='rb') -> 'DataAccessor':
        self.close_file() # close file before reopening it with given mode
        self.file = open(self.filepath, mode)
        if mode == 'rb':
            self.fetcher = MmapFetcher(self.file)
        return self

    def close_file(self):
        if self.file:
            self.file.close()

    def fetch(self, start, end) -> bytes:
        return self.fetcher.fetch(start, end)

    def fetch_all(self) -> bytes:
        self.file.seek(0)
        return self.file.read()

    def write(self, binary_data: bytes):
        self.file.write(binary_data)
        logger.debug("Written to filepath: " + self.filepath)

    def fetch_metadata(self) -> bytes:
        with open(self.filepath_metadata, 'rb') as file:
            return file.read()

    def write_metadata(self, binary_data: bytes) -> None:
        with open(self.filepath_metadata, 'wb') as file:
            file.write(binary_data)
        logger.debug("Written to filepath: " + self.filepath_metadata)
