"""Small portable interfaces used by the retained research arithmetic."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import numpy as np
import tifffile
import native_codec as native
import look_v2 as fmt

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf8', newline='\n')


def pin(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return dict(path=path.as_posix(), bytes=path.stat().st_size, sha256=digest.hexdigest())


def checked(row):
    actual = pin(row['path'])
    if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
        raise ValueError('Asset identity differs: ' + row['path'])
    return Path(row['path'])


def raw_module():
    import rawpy
    return rawpy


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


host = SimpleNamespace(fmt=fmt, verify_raw=lambda raw: (fmt.parse(raw), None, None))
