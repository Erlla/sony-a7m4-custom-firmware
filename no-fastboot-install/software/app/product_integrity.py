from pathlib import Path
import hashlib
import json
import re
import os
from data_paths import data_root
from integrity_lease import acquire

ROOT = Path(__file__).resolve().parents[1]
_loaded = {}
_release = None
_release_digest = None

def _manifest():
    global _release, _release_digest
    path = ROOT / 'app/release.json'
    raw = path.read_bytes()
    current = hashlib.sha256(raw).hexdigest()
    expected = _release_digest or os.environ.get('M4_RUNTIME_MANIFEST_SHA256')
    if expected is not None and current != expected:
        raise ValueError('软件运行期间发布清单发生变化')
    _release, _release_digest = json.loads(raw.decode('utf-8')), current
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
    return data_root(ROOT) / relative.parts[0]

def verify_release():
    manifest = _manifest()
    if manifest.get('schema') != 'm4-clean-product-release/1' or manifest.get('version') != '1.0.0':
        raise ValueError('软件清单不匹配')
    for relative, expected in manifest['files'].items():
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError('Dependency escapes product directory')
        saved = _loaded.get(relative)
        if saved is not None:
            if saved[1] == expected and saved[0].handle is not None and saved[0].same_path(path):
                continue
            saved[0].close()
            del _loaded[relative]
        lease = acquire(path)
        if lease is not None:
            actual = lease.sha256
            if actual != expected:
                lease.close()
                raise ValueError('软件文件已改变：' + relative)
            _loaded[relative] = (lease, expected)
        else:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != expected:
                raise ValueError('软件文件已改变：' + relative)
    return manifest
