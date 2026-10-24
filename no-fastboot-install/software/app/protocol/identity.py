from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'app/usb'
LIBRARIES = {'/usr/lib/libJiritsu.so': '3b19665f84bcd1b837a3b9377b40a91893010ff9732be71a430f3d0265c72c69', '/lib/ld-2.25.so': '90b4fe734ba7faa08d4591b1363bff478e7bde399a821fc0b2d021c062a58a9a'}

def backend(output):
    sys.path.insert(0, str(BACKEND))
    spec = importlib.util.spec_from_file_location('bound_m4_usb_session', BACKEND / 'usb_session.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    load = module.load_backend
    raw_path = output / 'raw_transfers.private.jsonl'

    def capture_backend():
        probe = load()

        class CapturingDriver(probe.LibusbCameraDriver):

            def save(self, direction, data):
                with raw_path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'time_ns': time.time_ns(), 'direction': direction, 'length': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'hex': bytes(data).hex()}) + '\n')

            def read(self, n, ep=0, timeout=None):
                data = super().read(n, ep, timeout)
                self.save('IN', data)
                return data

            def write(self, data, ep=0):
                result = super().write(data, ep)
                self.save('OUT', data)
                return result
        probe.LibusbCameraDriver = CapturingDriver
        return probe
    module.load_backend = capture_backend
    return module

def read(session, path, maximum):
    if path not in LIBRARIES and path not in ('/proc/mounts', '/etc/fstab', '/tmp/jbusy', '/tmp/jiritsu/libJit.so') and (not (path.startswith('/tmp/jiritsu/m4jit_') and path.endswith('.bin'))):
        raise ValueError('Path is outside the diagnostic read scope')
    session._select('/tmp/jiritsu/../..' + path)
    return session._read_selected(maximum)

def libraries(session, output):
    result = {}
    for path, expected in LIBRARIES.items():
        data = read(session, path, 300000)
        digest = hashlib.sha256(data).hexdigest()
        (output / Path(path).name).write_bytes(data)
        result[path] = {'bytes': len(data), 'sha256': digest, 'matches': digest == expected}
        if digest != expected:
            raise RuntimeError(f'Current library differs from offline binding: {path}')
    return result
