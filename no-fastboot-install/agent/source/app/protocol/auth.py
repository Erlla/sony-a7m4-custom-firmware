from product_integrity import pinned, state_path
import argparse
import hashlib
import importlib.util
import json
import site
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
site.addsitedir(str(ROOT / 'vendor/usb'))
import usb.core
import usb.util
import libusb_package
OUT = Path(__file__).resolve().parent
EVIDENCE = OUT / 'evidence'
SONY_VID = 1356
MSC_PID_M4 = 3493
SENSER_PIDS = (681, 822)
DEFAULT_SERVICE_PID = 822

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
_pmca_constants = _load_module('pmca_constants', ROOT / 'vendor/sony_pmca/pmca/usb/constants.py')
_pmca_crypto = _load_module('pmca_crypto', ROOT / 'vendor/sony_pmca/pmca/usb/crypto.py')
AUTH_PACKET_SIZE = 516
VENDOR_REQ_START_SENSER = (1, 14335, 55210)
VENDOR_REQ_STOP_SENSER = (1, 51200, 10325)
AUTH_CMD_CHALLENGE = 1
AUTH_CMD_RESPONSE = 3
AUTH_CMD_COMPLETE = 5
PFUNC_PRODUCT_INFO = 16
PFUNC_ADJUST_CONTROL = 64
PRODUCT_INFO_READ_HASP = (0, 31)
ADJUST_CMD_HEADER_SIZE = 4
SENSER_MIN_SIZE = 512
SENSER_CHUNK_SIZE = 32768
SENSER_MAX_SIZE = 1048576
JIRITSU_BLOCK = 4097
JIRITSU_TOP = {1: 'cmd_mode', 2: 'cmd_mount', 3: 'cmd_format', 4: 'cmd_start', 5: 'cmd_debug', 6: 'cmd_high_capacity_send_file', 7: 'cmd_high_capacity_send_file', 8: 'cmd_high_capacity_get_file', 9: 'cmd_file_delete', 10: 'cmd_high_capacity_get_file', 11: 'cmd_high_capacity_get_file', 12: 'cmd_high_capacity_send_file', 13: 'cmd_jiritsu_get_version', 14: 'cmd_factory', 15: 'adj_cmd_set_file_path', 16: 'adj_cmd_set_file2', 17: 'adj_cmd_get_file2', 18: 'cmd_file_delete2', 19: 'error_stub', 20: 'cmd_high_capacity_get_file'}
JIRITSU_READONLY_ALLOW = {13, 8, 10, 11, 17, 20}
JIRITSU_HARDBLOCK = {2, 3, 4, 5, 6, 7, 9, 12, 14, 15, 16, 18}
DMM_HEADER_SIZE = 40
DMM_OFF_PHASE = 0
DMM_OFF_TOTAL_LEN = 4
DMM_OFF_STATUS = 28
DMM_OFF_DATA_LEN = 32
DMM_OFF_COMMAND = 38

class ProbeError(RuntimeError):
    pass

class Recorder(object):
    """记录一次运行的全部 USB 传输并落盘。"""

    def __init__(self, command, scope):
        self.data = {'tool': 'auth.py', 'command': command, 'scope': scope, 'started_at': datetime.now(timezone.utc).isoformat(), 'transfers': [], 'notes': []}

    def transfer(self, direction, kind, detail, data=None):
        row = {'t': round(time.time(), 6), 'dir': direction, 'kind': kind, 'detail': detail}
        if data is not None:
            row['length'] = len(data)
            row['sha256'] = hashlib.sha256(data).hexdigest()
            row['hex_head'] = data[:96].hex() + ('...' if len(data) > 96 else '')
        self.data['transfers'].append(row)

    def note(self, key, value):
        self.data['notes'].append({'t': round(time.time(), 6), 'key': key, 'value': value})

    def finish(self, status, error=None):
        self.data['finished_at'] = datetime.now(timezone.utc).isoformat()
        self.data['status'] = status
        if error:
            self.data['error'] = {'type': type(error).__name__, 'message': str(error)}
        EVIDENCE.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        path = EVIDENCE / ('%s_%s.json' % (stamp, self.data['command']))
        body = json.dumps(self.data, ensure_ascii=False, indent=2)
        path.write_text(body + '\n', encoding='utf8')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sidecar = path.with_suffix('.json.sha256')
        sidecar.write_text('%s  %s\n' % (digest, path.name), encoding='utf8')
        self.data['evidence_path'] = str(path)
        self.data['evidence_sha256'] = digest
        return path

class LibusbCameraDriver(object):
    """pyusb/libusb_package 后端，实现 Senser 层所需的驱动接口。

    read(n)/write(data) 默认使用接口 0 的 bulk IN/OUT；ep=1 使用备用端点
    （服务身份的 terminal 端口，若存在）。
    """

    def __init__(self, dev, recorder, timeout_ms=5000):
        self.dev = dev
        self.rec = recorder
        self.timeout = timeout_ms
        cfg = dev.get_active_configuration()
        intf = cfg[0, 0]
        eps = {e.bEndpointAddress: e for e in intf}
        self.bulk_in = next((a for a in eps if a & 128), None)
        self.bulk_out = next((a for a in eps if not a & 128), None)
        if self.bulk_in is None or self.bulk_out is None:
            raise ProbeError('interface 0 missing bulk endpoints: in=%s out=%s' % (self.bulk_in, self.bulk_out))
        recorder.note('endpoints', {'bulk_in': hex(self.bulk_in), 'bulk_out': hex(self.bulk_out)})

    def getId(self):
        return (self.dev.idVendor, self.dev.idProduct)

    def read(self, n, ep=0, timeout=None):
        addr = self.bulk_in if ep == 0 else self.bulk_in + ep
        data = bytes(self.dev.read(addr, n, timeout or self.timeout))
        self.rec.transfer('IN', 'bulk', 'read %d from 0x%02x' % (n, addr), data)
        return data

    def write(self, data, ep=0):
        addr = self.bulk_out if ep == 0 else self.bulk_out + ep
        sent = self.dev.write(addr, data, self.timeout)
        self.rec.transfer('OUT', 'bulk', 'write %d to 0x%02x' % (len(data), addr), bytes(data))
        return sent

    def vendorRequestOut(self, request, value, index, data=b''):
        bmRequestType = 67
        self.dev.ctrl_transfer(bmRequestType, request, value, index, data, self.timeout)
        self.rec.transfer('OUT', 'control', 'req 0x%02x value 0x%04x index 0x%04x' % (request, value, index), bytes(data))

def list_sony_devices(vid=SONY_VID):
    backend = libusb_package.get_libusb1_backend()
    return list(libusb_package.find(find_all=True, idVendor=vid, backend=backend))

def describe_device(dev):
    row = {'idVendor': hex(dev.idVendor), 'idProduct': hex(dev.idProduct), 'bus': dev.bus, 'address': dev.address, 'bDeviceClass': hex(dev.bDeviceClass)}
    try:
        configs = []
        for config in dev:
            interfaces = []
            for interface in config:
                interfaces.append({'number': interface.bInterfaceNumber, 'class': interface.bInterfaceClass, 'subclass': interface.bInterfaceSubClass, 'protocol': interface.bInterfaceProtocol, 'endpoints': [{'address': hex(e.bEndpointAddress), 'type': e.bmAttributes & 3, 'max_packet': e.wMaxPacketSize} for e in interface]})
            configs.append({'value': config.bConfigurationValue, 'interfaces': interfaces})
        row['descriptors'] = configs
    except Exception as exc:
        row['descriptor_error'] = '%s: %s' % (type(exc).__name__, exc)
    try:
        row['strings'] = {'manufacturer': dev.manufacturer, 'product': dev.product, 'serial': 'omitted'}
    except Exception:
        pass
    return row

def open_device(pid, recorder):
    backend = libusb_package.get_libusb1_backend()
    dev = libusb_package.find(idVendor=SONY_VID, idProduct=pid, backend=backend)
    if dev is None:
        raise ProbeError('054c:%04x not visible to libusb backend (filters installed? camera connected?)' % pid)
    try:
        dev.set_configuration()
    except usb.core.USBError as exc:
        recorder.note('set_configuration', 'ignored: %s' % exc)
    return LibusbCameraDriver(dev, recorder)

class SenserAuth(object):

    def __init__(self, driver, recorder):
        self.driver = driver
        self.rec = recorder
        self.rounds = []

    def _sendAuthPacket(self, cmd, data=b''):
        self.driver.write(struct.pack('>HH', ~cmd & 65535, 0) + data.ljust(512, b'\x00'))
        resp = self.driver.read(AUTH_PACKET_SIZE)
        rcmd, salt = struct.unpack('>HH', resp[:4])
        ret = (~rcmd & 65535) - salt
        return (ret, resp[4:])

    def authenticate(self, digest_mode):
        """digest_mode: first4 | keyappend。返回每轮记录。

        first4 对应当前/海量存储身份（挑战前 4 字节参与摘要）；
        keyappend 对应 0336 服务身份（512 字节挑战 + 密钥表项）。
        """
        rounds = []
        for i in range(3):
            ret, data = self._sendAuthPacket(AUTH_CMD_CHALLENGE)
            if ret not in (2, 8):
                raise ProbeError('auth round %d: invalid challenge response %d' % (i + 1, ret))
            use_sha1 = ret == 2
            if digest_mode == 'keyappend':
                keys = _pmca_constants.senserKeysSha1 if use_sha1 else _pmca_constants.senserKeysSha256
                digest_input = data + keys[i]
            else:
                digest_input = data[:4]
            if use_sha1:
                digest = _pmca_crypto.sha1_faulty(digest_input)
            else:
                digest = hashlib.sha256(digest_input).digest()
            ret2, _ = self._sendAuthPacket(AUTH_CMD_RESPONSE, b'\x01' + digest)
            if ret2 != 4:
                raise ProbeError('auth round %d: response rejected (%d)' % (i + 1, ret2))
            rounds.append({'round': i + 1, 'branch': 'sha1_faulty' if use_sha1 else 'sha256', 'digest_mode': digest_mode})
        ret3, data = self._sendAuthPacket(AUTH_CMD_COMPLETE)
        if ret3 != 6:
            raise ProbeError('auth complete: ret=%d' % ret3)
        res = data[:1]
        if res != b'\x01':
            raise ProbeError('auth complete: senser error byte %s' % res.hex())
        self.rounds = rounds
        self.rec.note('auth', {'ok': True, 'digest_mode': digest_mode, 'rounds': rounds})
        return rounds

    def start(self):
        try:
            self.driver.vendorRequestOut(*VENDOR_REQ_START_SENSER)
            self.rec.note('senser', 'start request sent')
        except usb.core.USBError as exc:
            self.rec.note('senser', 'start request stalled (tolerated): %s' % exc)

    def stop(self):
        try:
            self.driver.vendorRequestOut(*VENDOR_REQ_STOP_SENSER)
            self.rec.note('senser', 'stop request sent')
        except usb.core.USBError as exc:
            self.rec.note('senser', 'stop request stalled (tolerated): %s' % exc)

def senser_packet_header(size, pfunc, sequence, response=0):
    return struct.pack('<IHH4B', size, pfunc, sequence, 0, 0, 0, response)

def parse_senser_header(data):
    size, pfunc, seq = struct.unpack('<IHH', data[:8])
    version, micon, offset_type, response = struct.unpack('4B', data[8:12])
    return {'size': size, 'pfunc': pfunc, 'sequence': seq, 'version': version, 'micon_type': micon, 'offset_type': offset_type, 'response': response}

class SenserChannel(object):

    def __init__(self, driver, recorder, min_read=None):
        self.driver = driver
        self.rec = recorder
        self.sequence = 1
        vid, pid = driver.getId()
        self.min_size = 0 if pid == 822 else SENSER_MIN_SIZE
        if min_read is not None:
            self.min_size = min_read

    def _readAll(self, n):
        data = b''
        while len(data) < n:
            data += self.driver.read(n - len(data))
        return data

    def send(self, pfunc, data):
        payload = bytes(data)
        while payload:
            header = senser_packet_header(len(payload), pfunc, self.sequence)
            self.driver.write(header + payload[:SENSER_MAX_SIZE])
            payload = payload[SENSER_MAX_SIZE:]
        out = b''
        while True:
            l = max(self.min_size - 12, 0)
            d = self.driver.read(12 + l)
            hdr = parse_senser_header(d)
            if hdr['sequence'] != self.sequence:
                raise ProbeError('wrong senser sequence: got %d want %d' % (hdr['sequence'], self.sequence))
            out += d[12:]
            done = l
            data_len = min(hdr['size'], SENSER_MAX_SIZE)
            chunk_len = SENSER_CHUNK_SIZE - self.min_size
            while done < data_len:
                l2 = min(data_len - done, chunk_len)
                out += self._readAll(l2)
                done += l2
                if not l2 & SENSER_MIN_SIZE - 1:
                    self.driver.read(SENSER_MIN_SIZE)
                chunk_len = SENSER_CHUNK_SIZE
            if hdr['size'] <= SENSER_MAX_SIZE:
                break
        self.sequence += 1
        return (hdr['response'], out)

    def adjust_control(self, block, code, data=b''):
        header = struct.pack('<HH', block, code)
        response, payload = self.send(PFUNC_ADJUST_CONTROL, header + bytes(data))
        return (response, payload)

    def product_info(self, category, command, data=b''):
        header = struct.pack('<HH', category, command)
        response, payload = self.send(PFUNC_PRODUCT_INFO, header + bytes(data))
        return (response, payload)

def build_dmm_packet(phase, code, payload=b''):
    """按 2026-10-08 回放证据构造 DMM 请求包。总长字段的确切语义尚未
    在实机闭合（packet_set_process_req_raw_data 使用 len-4），本函数取
    包全长，探测阶段以实际响应修正。"""
    pkt = bytearray(DMM_HEADER_SIZE + len(payload))
    pkt[DMM_OFF_PHASE] = phase
    struct.pack_into('<I', pkt, DMM_OFF_TOTAL_LEN, len(pkt))
    struct.pack_into('<I', pkt, DMM_OFF_DATA_LEN, len(payload))
    struct.pack_into('<H', pkt, DMM_OFF_COMMAND, code)
    pkt[DMM_HEADER_SIZE:] = payload
    return bytes(pkt)

def jiritsu_readonly_probe(channel, recorder, candidates, dry_run=False):
    """只读 Jiritsu 探测序列。

    步骤：get_version（0x0d，最温和）→ get 会话 phase1（0x08，DMM 协商）
    → get_file2（0x11）逐路径读取候选。全部只读；任何非允许码直接拒绝。
    """
    results = []
    plan = [('version', 13, 1, b'')]
    for path in candidates:
        plan.append(('get_file2', 8, 1, b''))
        plan.append(('get_file2', 17, 4, b'\x00' + path.encode('ascii')))
    for label, code, phase, payload in plan:
        name = guard_jiritsu_code(code)
        pkt = build_dmm_packet(phase, code, payload)
        if dry_run:
            results.append({'label': label, 'code': '0x%02x' % code, 'name': name, 'phase': phase, 'packet_hex': pkt.hex()})
            continue
        response, out = channel.adjust_control(JIRITSU_BLOCK, code, pkt)
        results.append({'label': label, 'code': '0x%02x' % code, 'name': name, 'phase': phase, 'response': response, 'out_length': len(out), 'out_hex_head': out[:128].hex()})
        recorder.note('jiritsu', {'label': label, 'code': '0x%02x' % code, 'phase': phase, 'response': response})
    return results

def guard_jiritsu_code(code):
    name = JIRITSU_TOP.get(code, 'unknown')
    if code in JIRITSU_HARDBLOCK:
        raise ProbeError('refused hard-blocked command 0x%02x (%s): write/execute/format side effects' % (code, name))
    if code not in JIRITSU_READONLY_ALLOW:
        raise ProbeError('refused non-allowlisted command 0x%02x (%s): stage-1 tool is read-only' % (code, name))
    return name

class FakeCameraDriver(object):
    """在内存中模拟认证帧与 Senser 包回环，用于离线验证协议状态机。"""

    def __init__(self, digest_mode, service=False, sha1_branch=False):
        self.digest_mode = digest_mode
        self.sha1_branch = sha1_branch
        self.pid = DEFAULT_SERVICE_PID if service else MSC_PID_M4
        self.round = 0
        self.outq = bytearray()
        self.pending = b''
        self.senser_tail = bytearray()

    def getId(self):
        return (SONY_VID, self.pid)

    def write(self, data, ep=0):
        self.pending += bytes(data)
        self._maybe_senser()

    def _maybe_senser(self):
        """区分认证帧（516B 对齐）与 Senser 数据包（12B 头 + 载荷）。

        认证帧的 cmd 是取反值，pFunc 位置不会是 0x0010/0x0040 的小端
        长度字段组合；按认证帧优先处理并按长度消费。
        """
        while len(self.pending) >= AUTH_PACKET_SIZE:
            frame, self.pending = (self.pending[:AUTH_PACKET_SIZE], self.pending[AUTH_PACKET_SIZE:])
            self._handle_auth_frame(frame)
        if len(self.pending) >= 12:
            hdr = parse_senser_header(self.pending[:12])
            total = 12 + hdr['size']
            if len(self.pending) >= total:
                pkt, self.pending = (self.pending[:total], self.pending[total:])
                self._handle_senser(pkt)

    def _challenge(self):
        return bytes((i * 7 + self.round & 255 for i in range(512)))

    def _handle_auth_frame(self, frame):
        cmd, _salt = struct.unpack('>HH', frame[:4])
        logical = ~cmd & 65535
        if logical == AUTH_CMD_CHALLENGE:
            self.round += 1
            self.outq += struct.pack('>HH', ~2 & 65535 if self.sha1_branch else ~8 & 65535, 0) + self._challenge()
        elif logical == AUTH_CMD_RESPONSE:
            self._verify_digest(frame[4:])
            self.outq += struct.pack('>HH', ~4 & 65535, 0) + b'\x00' * 512
        elif logical == AUTH_CMD_COMPLETE:
            self.outq += struct.pack('>HH', ~6 & 65535, 0) + b'\x01' + b'\x00' * 511

    def _verify_digest(self, body):
        flag, digest = (body[:1], body[1:])
        if self.digest_mode == 'keyappend':
            keys = _pmca_constants.senserKeysSha1 if self.sha1_branch else _pmca_constants.senserKeysSha256
            digest_input = self._challenge() + keys[self.round - 1]
        else:
            digest_input = self._challenge()[:4]
        if self.sha1_branch:
            expected = _pmca_crypto.sha1_faulty(digest_input)
        else:
            expected = hashlib.sha256(digest_input).digest()
        if flag != b'\x01' or digest[:len(expected)] != expected:
            raise AssertionError('fake camera: digest mismatch (host computed wrong hash)')

    def _handle_senser(self, pkt):
        hdr = parse_senser_header(pkt[:12])
        payload = pkt[12:]
        reply_payload = b'ECHO:' + payload
        min_size = 0 if self.pid == DEFAULT_SERVICE_PID else SENSER_MIN_SIZE
        first = max(min_size - 12, 0)
        head = senser_packet_header(len(reply_payload), hdr['pfunc'], hdr['sequence'], response=0)
        body = head + reply_payload
        self.outq += body[:12 + first].ljust(12 + first, b'\x00')
        self.senser_tail += body[12 + first:]

    def read(self, n, ep=0, timeout=None):
        if not self.outq and self.senser_tail:
            self.outq, self.senser_tail = (bytearray(self.senser_tail), bytearray())
        data = bytes(self.outq[:n])
        if len(data) < n:
            raise AssertionError('fake camera underflow: asked %d have %d' % (n, len(data)))
        del self.outq[:n]
        return data

def authenticate_with_fallback(driver, recorder, primary):
    """先按身份默认摘要模式认证，失败则清理会话后换另一种模式重试一次。"""
    alternate = 'keyappend' if primary == 'first4' else 'first4'
    auth = SenserAuth(driver, recorder)
    for mode in (primary, alternate):
        try:
            auth.start()
            rounds = auth.authenticate(mode)
            return (mode, rounds)
        except (ProbeError, usb.core.USBError) as exc:
            recorder.note('auth_attempt_failed', {'mode': mode, 'error': str(exc)})
            try:
                auth.stop()
            except Exception:
                pass
            if mode == alternate:
                raise
    raise ProbeError('unreachable')

def cmd_selftest(args):
    rec = Recorder('selftest', 'offline, no USB access')
    checks = []

    def check(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    msg32 = bytes(range(40))
    check('sha1_matches_hashlib', _pmca_crypto.sha1(b'abc') == hashlib.sha1(b'abc').digest())
    check('sha1_faulty_is_len_masked', _pmca_crypto.sha1_faulty(msg32) == _pmca_crypto.sha1(msg32, len(msg32) & 31))
    frame = struct.pack('>HH', ~AUTH_CMD_CHALLENGE & 65535, 0) + b'\x00' * 512
    rcmd, salt = struct.unpack('>HH', frame[:4])
    check('auth_frame_roundtrip', (~rcmd & 65535) - salt == AUTH_CMD_CHALLENGE)
    fake = FakeCameraDriver('first4', service=False)
    SenserAuth(fake, Recorder('selftest', 'offline')).authenticate('first4')
    check('auth_first4_simulated', True)
    for branch in (False, True):
        fake = FakeCameraDriver('keyappend', service=True, sha1_branch=branch)
        SenserAuth(fake, Recorder('selftest', 'offline')).authenticate('keyappend')
    check('auth_keyappend_sha1_sha256_simulated', True)
    fake = FakeCameraDriver('first4', service=False)
    chan = SenserChannel(fake, Recorder('selftest', 'offline'))
    resp, out = chan.send(PFUNC_ADJUST_CONTROL, b'\x11"3D')
    expected = b'ECHO:\x11"3D'.ljust(SENSER_MIN_SIZE - 12, b'\x00')
    check('senser_echo_non_service', resp == 0 and out == expected and (chan.sequence == 2))
    fake = FakeCameraDriver('keyappend', service=True)
    chan = SenserChannel(fake, Recorder('selftest', 'offline'))
    resp, out = chan.adjust_control(JIRITSU_BLOCK, 13, b'\x00\x01\x02')
    check('senser_adjust_service', resp == 0 and out == b'ECHO:' + struct.pack('<HH', JIRITSU_BLOCK, 13) + b'\x00\x01\x02')
    pkt = build_dmm_packet(4, 17, b'\x00abc')
    check('dmm_packet_layout', pkt[0] == 4 and struct.unpack_from('<I', pkt, DMM_OFF_TOTAL_LEN)[0] == len(pkt) and (struct.unpack_from('<I', pkt, DMM_OFF_DATA_LEN)[0] == 4) and (struct.unpack_from('<H', pkt, DMM_OFF_COMMAND)[0] == 17) and (pkt[DMM_HEADER_SIZE:] == b'\x00abc'))
    refused = 0
    for code in sorted(JIRITSU_HARDBLOCK):
        try:
            guard_jiritsu_code(code)
        except ProbeError:
            refused += 1
    check('hardblock_refusal', refused == len(JIRITSU_HARDBLOCK), 'refused %d/%d' % (refused, len(JIRITSU_HARDBLOCK)))
    ok_allow = all((guard_jiritsu_code(c) for c in JIRITSU_READONLY_ALLOW))
    check('allowlist_accepts', ok_allow)
    rec.data['checks'] = checks
    passed = sum((1 for c in checks if c['ok']))
    path = rec.finish('ok' if passed == len(checks) else 'failed')
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print('selftest: %d/%d checks passed; evidence: %s' % (passed, len(checks), path))
    return 0 if passed == len(checks) else 1

def cmd_descriptors(args):
    rec = Recorder('descriptors', 'enumeration only, no transfers to camera')
    devices = [describe_device(d) for d in list_sony_devices(args.vid)]
    rec.data['devices'] = devices
    rec.note('summary', {'count': len(devices), 'pids': [d['idProduct'] for d in devices]})
    path = rec.finish('ok')
    print(json.dumps(rec.data['notes'], ensure_ascii=False, indent=2))
    print('%d Sony device(s); evidence: %s' % (len(devices), path))
    return 0

def _rescan(recorder):
    devices = [describe_device(d) for d in list_sony_devices()]
    recorder.note('rescan', [d['idProduct'] for d in devices])
    return devices

def cmd_auth_normal(args):
    rec = Recorder('auth-normal', 'senser authentication on current identity; no file or memory access')
    pid = args.pid or MSC_PID_M4
    try:
        driver = open_device(pid, rec)
        vid, rpid = driver.getId()
        rec.note('opened', '%04x:%04x' % (vid, rpid))
        before = [d['idProduct'] for d in _rescan(rec)]
        mode, rounds = authenticate_with_fallback(driver, rec, 'first4' if rpid != DEFAULT_SERVICE_PID else 'keyappend')
        rec.note('authenticated', {'mode': mode, 'rounds': rounds})
        time.sleep(3)
        after = [d['idProduct'] for d in _rescan(rec)]
        new = [p for p in after if p not in before]
        rec.note('reenumeration', {'before': before, 'after': after, 'new': new})
        path = rec.finish('ok')
        print(json.dumps({'mode': mode, 'rounds': rounds, 'new_pids': new}, ensure_ascii=False, indent=2))
        print('evidence: %s' % path)
        return 0
    except Exception as exc:
        rec.finish('failed', exc)
        raise

def _device_alive(pid, rec):
    """打开设备并做一次无害 GET_STATUS；失败视为不在线（陈旧 devnode/已断开）。"""
    try:
        dev = open_device(pid, rec).dev
        dev.ctrl_transfer(128, 0, 0, 0, 2, 2000)
        return True
    except Exception:
        return False

def _ensure_service_pid(pid, rec, timeout_s=90):
    """服务 PID 不在线时，通过普通身份认证触发切换并等待其出现。

    2026-10-17 实测：0DA5 上认证成功后相机会自行重枚举为 0336，
    切换完成时间超过早先的 3 秒窗口，故用长轮询；0336 会话超时后
    相机会回到 0DA5，陈旧 devnode 需用 GET_STATUS 过滤。
    """
    devices = [d['idProduct'] for d in _rescan(rec)]
    if hex(pid) in devices and _device_alive(pid, rec):
        return
    if hex(MSC_PID_M4) not in devices and hex(pid) not in devices:
        raise ProbeError('neither service pid %s nor normal identity %s is connected' % (hex(pid), hex(MSC_PID_M4)))
    if hex(pid) not in devices:
        rec.note('transition', 'authenticating on %s to trigger service reenumeration' % hex(MSC_PID_M4))
        normal = open_device(MSC_PID_M4, rec)
        authenticate_with_fallback(normal, rec, 'first4')
    for i in range(timeout_s // 2):
        time.sleep(2)
        pids = [d['idProduct'] for d in _rescan(rec)]
        if hex(pid) in pids and _device_alive(pid, rec):
            rec.note('transition', 'service pid alive after ~%ds' % ((i + 1) * 2))
            return
    raise ProbeError('service pid %s did not appear within %ds' % (hex(pid), timeout_s))

def _open_service_and_auth(args, rec):
    pid = args.service_pid
    _ensure_service_pid(pid, rec)
    driver = open_device(pid, rec)
    primary = 'keyappend' if pid == DEFAULT_SERVICE_PID else 'first4'
    mode, rounds = authenticate_with_fallback(driver, rec, primary)
    return (driver, SenserChannel(driver, rec, min_read=args.min_read), mode)

def cmd_service(args):
    rec = Recorder('service', 'service identity auth + ProductInfo HASP read; read-only')
    try:
        driver, channel, mode = _open_service_and_auth(args, rec)
        response, data = channel.product_info(*PRODUCT_INFO_READ_HASP, b'\x00')
        rec.note('product_info_hasp', {'response': response, 'length': len(data), 'hex_head': data[:96].hex()})
        SenserAuth(driver, rec).stop()
        time.sleep(2)
        _rescan(rec)
        path = rec.finish('ok' if response == 1 else 'unexpected_response')
        print(json.dumps({'auth_mode': mode, 'hasp_response': response, 'hasp_length': len(data)}, ensure_ascii=False, indent=2))
        print('evidence: %s' % path)
        return 0
    except Exception as exc:
        rec.finish('failed', exc)
        raise

def cmd_jiritsu(args):
    rec = Recorder('jiritsu', 'read-only Jiritsu block probes (version, GET_FILE2); writes hard-blocked')
    candidates = args.path or ['example.txt', '../../etc/ld.so.preload']
    try:
        if args.dry_run:
            results = jiritsu_readonly_probe(None, rec, candidates, dry_run=True)
            rec.data['results'] = results
            path = rec.finish('dry-run')
            print(json.dumps(results, ensure_ascii=False, indent=2))
            print('dry-run only, nothing sent; evidence: %s' % path)
            return 0
        driver, channel, mode = _open_service_and_auth(args, rec)
        results = jiritsu_readonly_probe(channel, rec, candidates)
        SenserAuth(driver, rec).stop()
        time.sleep(2)
        _rescan(rec)
        rec.data['results'] = results
        path = rec.finish('ok')
        print(json.dumps({'auth_mode': mode, 'results': results}, ensure_ascii=False, indent=2))
        print('evidence: %s' % path)
        return 0
    except Exception as exc:
        rec.finish('failed', exc)
        raise

def build_read_request(path):
    """构造 adj_cmd_get_file（子命令 0x08）状态 1 的内联路径读取请求（v2，2026-10-17 路由表解码后修正）。

    sencore 静态路由表（libsencore .rodata 0x177f8）证实：
      - Jiritsu 命令注册于 category 0x1001（子命令 0x01..0x14，sid 0x016f0480，
        名字 JIRITSU_*；0x01-0x12 带 0x4000 批量数据标志）。
      - senser 载荷 = [u16 category][u16 command][adj 处理器包体]；sencore 将包体
        拷贝到 OsalPacket+0x28，因此固件读的 state(pkt+0x28)/index(+0x29)/
        count(+0x2a) 即包体的前三个字节，路径自 +0x2b（=包体偏移 3）开始，
        data_len 由 sencore 自动填充为包体长度（固件按 data_len-3 取路径长）。
    """
    p = path.encode('ascii') + b'\x00'
    body = bytes([1, 0, 0]) + p
    return body

def build_session_close(code):
    """结束读取会话：hc_get_file 的 phase 由包体首字节承载——0x10 关闭。

    注意：包体首字节同时是 hc_get_file 的 phase 选择（1/4/0x10）与
    adj_cmd_get_file 的 state（0/1/0xff）——两级的同一字节双重语义。
    关闭用 0x10。
    """
    return bytes([16, 0, 0])

def read_response_frames(driver, channel, idle_s=2.5, max_frames=64):
    """多帧响应读取：Jiritsu 批量数据以追加 senser 帧回传（DoExecute 每条
    OSAL 应答消息产生一帧），读到静默为止。返回帧列表。"""
    frames = []
    last = time.time()
    while len(frames) < max_frames and time.time() - last < idle_s:
        try:
            d = driver.read(12, timeout=400)
        except usb.core.USBError:
            continue
        if len(d) < 12:
            continue
        hdr = parse_senser_header(d)
        body = b''
        remaining = hdr['size']
        while remaining > 0:
            try:
                chunk = driver.read(min(remaining, 65536), timeout=1500)
            except usb.core.USBError:
                break
            body += chunk
            remaining -= len(chunk)
        frames.append({'seq': hdr['sequence'], 'response': hdr['response'], 'size': hdr['size'], 'body': body})
        last = time.time()
    if frames:
        channel.sequence = frames[-1]['seq'] + 1
    return frames

def cmd_jiritsu_read(args):
    rec = Recorder('jiritsu-read', 'read-only: adj_cmd_get_file inline-path read incl. traversal candidates (v2 format)')
    try:
        driver, channel, mode = _open_service_and_auth(args, rec)
        results = []
        for path in args.path or ['../../version.txt']:
            rows = []
            req = build_read_request(path)
            payload = struct.pack('<HH', JIRITSU_BLOCK, 8) + req
            driver.write(senser_packet_header(len(payload), PFUNC_ADJUST_CONTROL, channel.sequence) + payload)
            channel.sequence += 1
            frames = read_response_frames(driver, channel)
            for i, f in enumerate(frames):
                row = {'step': 'read_frame_%d' % i, 'response': f['response'], 'out_length': len(f['body']), 'out_hex_head': f['body'][:200].hex()}
                if len(f['body']) >= 4:
                    err = struct.unpack_from('<I', f['body'], 0)[0]
                    row['error_code'] = '0x%08x' % err
                    if err == 0 and len(f['body']) > 4:
                        row['content_hex_head'] = f['body'][4:132].hex()
                        row['content_length'] = len(f['body']) - 4
                        row['content_ascii_head'] = f['body'][4:68].decode('ascii', 'replace')
                rows.append(row)
            if not frames:
                rows.append({'step': 'read', 'error': 'no response frames'})
            try:
                response, out = channel.adjust_control(JIRITSU_BLOCK, 8, build_session_close(8))
                rows.append({'step': 'close', 'response': response, 'out_hex': out.hex()})
            except Exception as exc:
                rows.append({'step': 'close_failed', 'error': str(exc)[:120]})
            results.append({'path': path, 'steps': rows})
            rec.note('jiritsu_read', {'path': path, 'rows': rows})
        SenserAuth(driver, rec).stop()
        time.sleep(2)
        _rescan(rec)
        rec.data['results'] = results
        path_json = rec.finish('ok')
        print(json.dumps({'auth_mode': mode, 'results': results}, ensure_ascii=False, indent=2))
        print('evidence: %s' % path_json)
        return 0
    except Exception as exc:
        rec.finish('failed', exc)
        raise
