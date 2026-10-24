from product_integrity import pinned, state_path
import hashlib
import importlib.util
from pathlib import Path
import secrets
import re
import struct
import time
from senser_wire import SenserWire
from transport import READ_PATHS, AP_KEYS, CP_KEYS

class CameraStatusError(RuntimeError):

    def __init__(self, status):
        self.status = status
        super().__init__(f'Camera returned {status:#010x}; not proof of file absence')

def body_binding(identity):
    """HASP contains changing fields; it is a session observation, not an ID.

    Accept the previous capture's extra HASP digest without rewriting that
    original journal. The normal USB serial is checked before authentication.
    """
    model, serial = (identity.get('model'), identity.get('normal_usb_serial_sha256'))
    if model != 'ILCE-7M4' or not isinstance(serial, str) or (not re.fullmatch('[0-9a-f]{64}', serial)):
        raise ValueError('Invalid normal USB body binding')
    return {'model': model, 'normal_usb_serial_sha256': serial}

def usb_location(device):
    location = (device.bus, tuple(device.port_numbers or ()))
    if location[0] is None or not location[1]:
        raise RuntimeError('USB physical port is unavailable; cannot bind service transition')
    return location

def require_service_location(expected, device):
    if usb_location(device) != expected:
        raise RuntimeError('Service USB physical port differs from the authenticated normal device')

def load_backend():
    root = next((p for p in Path(__file__).resolve().parents if (p / 'vendor').is_dir()), None)
    if root is None:
        raise RuntimeError('Research backend requires the documented firmware workspace')
    path = root / 'app/protocol/auth.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != pinned('app/protocol/auth.py'):
        raise RuntimeError('Reviewed authentication backend changed; inspect it before using USB')
    spec = importlib.util.spec_from_file_location('a7m4_research_auth', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class ResearchSession:

    def __init__(self, evidence, expected=None, *, file_probe=False, progress=None):
        self.evidence = Path(evidence).resolve()
        self.expected = body_binding(expected) if expected is not None else None
        self.file_probe, self.progress = (file_probe, progress)
        self.driver, self.wire, self.probe, self.rec = (None, None, None, None)
        self.identity, self.error = (None, None)

    def _devices(self, pid):
        return list(self.probe.usb.core.find(find_all=True, idVendor=1356, idProduct=pid, backend=self.probe.libusb_package.get_libusb1_backend()))

    def __enter__(self):
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.probe = load_backend()
        self.probe.EVIDENCE = self.evidence
        self.rec = self.probe.Recorder('m4-research-session', 'Authenticated bounded reads; optional unique 32-byte work-area file roundtrip')
        try:
            devices = self._devices(3493)
            if len(devices) != 1 or self._devices(822):
                raise RuntimeError('Start with exactly one ILCE-7M4 in normal 054C:0DA5 identity')
            normal_dev = devices[0]
            try:
                normal_location = usb_location(normal_dev)
                product, serial = (normal_dev.product, normal_dev.serial_number)
                if product != 'ILCE-7M4' or not serial:
                    raise RuntimeError('Normal USB product or serial cannot bind the target body')
                normal_identity = {'model': product, 'normal_usb_serial_sha256': hashlib.sha256(serial.encode('utf-8')).hexdigest()}
                if self.expected is not None and self.expected != normal_identity:
                    raise RuntimeError('Connected normal USB body differs from the backup')
                normal = self.probe.LibusbCameraDriver(normal_dev, self.rec)
                self.probe.authenticate_with_fallback(normal, self.rec, 'first4')
            finally:
                self.probe.usb.util.dispose_resources(normal_dev)
            deadline = time.monotonic() + 90
            while True:
                devices = self._devices(822)
                if len(devices) == 1:
                    break
                if len(devices) > 1 or time.monotonic() >= deadline:
                    raise RuntimeError('Service 0336 did not enumerate uniquely; inspect driver/connection')
                time.sleep(0.5)
            require_service_location(normal_location, devices[0])
            self.driver = self.probe.LibusbCameraDriver(devices[0], self.rec)
            self.probe.authenticate_with_fallback(self.driver, self.rec, 'keyappend')
            self.wire = SenserWire(self.driver, budget=300)
            response, data = self.wire.send(16, struct.pack('<HHB', 0, 31, 0), maximum=88)
            if response != 1 or len(data) != 88:
                raise RuntimeError('ProductInfo is not the verified M4 88-byte response')
            self.identity = normal_identity
            self.rec.note('product_info_observation', {'length': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'stable_body_identifier': False})
            self.rec.note('service_port_binding', {'same_physical_port': True})
            self.rec.note('body_binding', self.identity)
            return self
        except BaseException as error:
            self.error = error
            self._close()
            raise

    def _close(self):
        try:
            if self.driver and self.wire and self.wire.healthy:
                self.probe.SenserAuth(self.driver, self.rec).stop()
        finally:
            if self.driver:
                self.probe.usb.util.dispose_resources(self.driver.dev)
                self.driver = None
            if self.rec:
                self.rec.note('transport_outcome_known', bool(self.wire and self.wire.healthy))
                self.rec.finish('failed' if self.error else 'completed', self.error)
                self.rec = None

    def __exit__(self, kind, error, tb):
        self.error = error
        self._close()
        return False

    def _adjust(self, category, command, body=b'', *, maximum=4, progress=None):
        response, data = self.wire.send(64, struct.pack('<HH', category, command) + body, maximum=maximum, progress=progress)
        if response != 0:
            raise RuntimeError(f'Outer adjust response {response}')
        return data

    def _jiritsu(self, command, body, *, maximum=4, progress=None):
        data = self._adjust(4097, command, body, maximum=maximum, progress=progress)
        if len(data) < 4:
            raise RuntimeError('Missing Jiritsu status')
        status = struct.unpack_from('<I', data)[0]
        if status:
            raise CameraStatusError(status)
        return data[4:]

    def _select(self, path):
        if not path.startswith('/tmp/jiritsu/') or '\x00' in path or len(path.encode('ascii')) > 510:
            raise ValueError('Invalid work-area selected path')
        self._jiritsu(15, b'\x00' + path.encode('ascii') + b'\x00')

    def _read_selected(self, maximum, progress=None):
        callback = (lambda done, total: progress(max(done - 4, 0), max(total - 4, 0))) if progress else None
        return self._jiritsu(17, b'\x00\xff\x00', maximum=maximum + 4, progress=callback)

    def read_file(self, path, *, maximum=128 * 1024 * 1024, progress=None):
        if path not in READ_PATHS:
            raise ValueError('File is outside the M4 read allowlist')
        self._select('/tmp/jiritsu/../..' + path)
        return self._read_selected(maximum, progress)

    def read_backup(self, progress=None):
        return self._adjust(1539, 5, b'\x01', maximum=64 * 1024 * 1024, progress=progress)

    def read_ap(self, key):
        if key not in AP_KEYS:
            raise ValueError('Unknown AP binding')
        data = self._adjust(1539, 1, struct.pack('<I', key), maximum=1)
        if len(data) != 1:
            raise ValueError('AP binding length differs')
        return data

    def read_cp(self, key):
        if key not in CP_KEYS:
            raise ValueError('Unknown CP unit')
        data = self._adjust(1539, 64, struct.pack('<II', key, 1), maximum=CP_KEYS[key])
        if len(data) != CP_KEYS[key]:
            raise ValueError('CP unit length differs')
        return data

    def probe_file_roundtrip(self):
        if not self.file_probe:
            raise RuntimeError('This session is read-only')
        data = secrets.token_bytes(32)
        path = '/tmp/jiritsu/a7m4.usb.' + secrets.token_hex(12)
        self._select(path)
        self._jiritsu(16, b'\x00\xff\x00' + data)
        self._select(path)
        actual = self._read_selected(32)
        if actual != data:
            raise ValueError('Unique work-area file did not read back exactly')
        self._select(path)
        self._jiritsu(18, b'\x00\xff')
        return {'length': 32, 'sha256': hashlib.sha256(data).hexdigest(), 'readback_equal': True, 'delete_response': 0, 'native_execution': False, 'preload_modified': False, 'program_files_modified': False}
