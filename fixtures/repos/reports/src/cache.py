"""A small in-process cache shared by the reporting code."""


class Cache:
    def __init__(self):
        self._data = {}
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key, compute):
        """The value stored under key, or compute() stored under key on first use."""
        if key in self._data:
            self.hits += 1
            return self._data[key]
        self.misses += 1
        value = compute()
        self._data[key] = value
        return value
