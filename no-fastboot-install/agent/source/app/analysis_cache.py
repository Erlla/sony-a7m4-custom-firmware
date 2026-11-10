"""Bounded process-local reuse of pure analysis of identical complete bytes.

Never caches file paths, device reads, task authorization or write receipts.
Callers receive their own mutable result; exceptions are never cached.
"""
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from hashlib import sha256
from pathlib import Path
from threading import RLock

_values = OrderedDict()
_lock = RLock()
LIMIT = 4


def content_analysis(source):
    namespace = (str(Path(source).resolve()), sha256(Path(source).read_bytes()).digest())

    def decorate(function):
        @wraps(function)
        def evaluate(*values):
            # Snapshot mutable inputs before hashing and before calling analysis.
            data = tuple(bytes(v) if isinstance(v, (bytes, bytearray)) else v for v in values)
            if not all(isinstance(v, bytes) for v in data):
                return function(*values)
            key = (namespace, function.__name__, tuple((len(v), sha256(v).digest()) for v in data))
            with _lock:
                if key in _values:
                    _values.move_to_end(key)
                    return deepcopy(_values[key])
            result = function(*data)
            with _lock:
                _values[key] = deepcopy(result)
                _values.move_to_end(key)
                while len(_values) > LIMIT:
                    _values.popitem(last=False)
            return result
        return evaluate
    return decorate
