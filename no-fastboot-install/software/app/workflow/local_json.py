from product_integrity import pinned, state_path
from pathlib import Path
import json
import os
import uuid

def io_path(path):
    """Prefix only the OS I/O path; keep stored paths and identity checks unchanged."""
    value = os.path.abspath(os.fspath(path))
    if os.name != 'nt' or value.startswith('\\\\?\\'):
        return value
    return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value

def atomic(path, value):
    path = Path(path)
    os.makedirs(io_path(path.parent), exist_ok=True)
    temporary = path.parent / ('j' + uuid.uuid4().hex + '.tmp')
    created = False
    try:
        with open(io_path(temporary), 'x', encoding='utf-8', newline='\n') as stream:
            created = True
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(io_path(temporary), io_path(path))
    finally:
        if created:
            try:
                os.unlink(io_path(temporary))
            except FileNotFoundError:
                pass
