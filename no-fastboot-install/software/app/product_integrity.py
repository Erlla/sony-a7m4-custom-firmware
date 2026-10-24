from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
_loaded = {}
_release = None
_release_stamp = None
_release_digest = None

def _manifest():
    global _release, _release_stamp, _release_digest
    path = ROOT / 'app/release.json'
    stat = path.stat()
    stamp = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
    if _release_stamp != stamp:
        raw = path.read_bytes()
        current = hashlib.sha256(raw).hexdigest()
        if _release_digest is not None and current != _release_digest:
            raise ValueError('软件运行期间发布清单发生变化')
        _release, _release_stamp, _release_digest = json.loads(raw.decode('utf-8')), stamp, current
    return _release

def pinned(relative):
    if not isinstance(relative, str) or relative.startswith('/') or ':' in relative or '\\' in relative or '..' in relative.split('/'):
        raise ValueError('Invalid product dependency path')
    value = _manifest()['files'][relative]
    if re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('Invalid product dependency digest')
    return value

def state_path(component):
    component = Path(component).resolve()
    relative = component.relative_to(ROOT / 'app')
    if len(relative.parts) != 1:
        raise ValueError('Invalid component state directory')
    return ROOT / 'state' / relative.parts[0]

def verify_release():
    manifest = _manifest()
    if manifest.get('schema') != 'm4-clean-product-release/1' or manifest.get('version') != '1.00':
        raise ValueError('软件清单不匹配')
    for relative, expected in manifest['files'].items():
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError('Dependency escapes product directory')
        stat = path.stat()
        identity = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
        saved = _loaded.get(relative)
        if saved != (identity, expected):
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != expected:
                raise ValueError('软件文件已改变：' + relative)
            _loaded[relative] = (identity, expected)
    return manifest
