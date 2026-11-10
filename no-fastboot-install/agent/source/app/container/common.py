from __future__ import annotations
from product_integrity import pinned, state_path
import hashlib
import json
from pathlib import Path
import stat
ROOT = Path(__file__).resolve().parents[2]

def require(ok, message):
    if not ok:
        raise ValueError(message)

def local_path(value, *, existing=False):
    text = str(value).replace('\\', '/')
    require(not text.startswith(('//', '/dev/')), 'Device/UNC paths are forbidden')
    require(not (len(text) == 2 and text[1] == ':'), 'A drive is not a file')
    require(':' not in text[2:], 'Alternate streams are forbidden')
    p = Path(value).absolute()
    for part in (p, *p.parents):
        if part.exists():
            s = part.lstat()
            require(not stat.S_ISLNK(s.st_mode), 'Symbolic links are forbidden')
            if getattr(s, 'st_file_attributes', 0) & 1024:
                require(part.is_junction() and part.is_relative_to(ROOT) and part.resolve().is_relative_to(ROOT), 'External/unreviewed reparse path')
    p = p.resolve()
    if existing:
        require(stat.S_ISREG(p.stat().st_mode), 'Input must be an existing regular file')
    return p

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    with local_path(path, existing=True).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def locked(path, expected):
    p = local_path(path, existing=True)
    require(len(expected) == 64 and file_sha(p) == expected.lower(), 'Input SHA-256 mismatch')
    return p

def new_dir(path):
    p = local_path(path)
    p.mkdir(parents=True, exist_ok=False)
    return p

def save_json(path, obj):
    with local_path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

def dependencies():
    import sys
    for rel in ('vendor/python', 'vendor/squashfs', 'vendor'):
        value = str(ROOT / rel)
        if value not in sys.path:
            sys.path.insert(0, value)
