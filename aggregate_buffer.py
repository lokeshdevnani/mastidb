class AggregateBuffer:
    _buffer: dict[tuple, list]

    def __init__(self, value_length: int):
        self.value_length = value_length
        self._buffer = {}

    def get(self, keys: tuple, value_index: int):
        if keys in self._buffer:
            return self._buffer[keys][value_index]

        return None

    def set(self, keys: tuple, value_index, value):
        if keys not in self._buffer:
            self._buffer[keys] = [0] * self.value_length

        self._buffer[keys][value_index] = value

    def get_results(self):
        return self._buffer
