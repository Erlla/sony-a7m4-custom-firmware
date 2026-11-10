"""Proof for a failed read-only worker whose RAM cleanup was published."""
from pathlib import Path
import struct
from connection_stop import ConnectionStop
from state_io import io_path, read_json

FRAME = struct.Struct('<8s16s11q32s32s')
FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'bytes', 'chunks', 'flags')
IDENTITY = ('version', 'euid', 'pid', 'ppid', 'loader_pid')


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_failure_cleanup(ready, native, cleaned):
    require(ready['phase'] == 1 and ready['error'] == ready['cleanup'] == ready['euid'] == 0
            and ready['ppid'] == 1 and ready['flags'] == 3
            and ready['pid'] > 1 and ready['loader_pid'] > 1 and ready['pid'] != ready['loader_pid'],
            'Reader ready identity differs')
    require(native['phase'] == 90 and native['error'] < 0 and native['cleanup'] == 0
            and all(native[key] == ready[key] for key in IDENTITY)
            and 0 <= native['bytes'] <= 25100288 and 0 <= native['chunks'] <= 766
            and native['flags'] & ~127 == 0, 'Reader failure identity differs')
    require(cleaned == dict(native, phase=5), 'Failed reader cleanup is incomplete or belongs to another worker')


def verify_success_cleanup(ready, native, cleaned):
    require(all(native[key] == ready[key] for key in IDENTITY), 'Reader result identity differs')
    require(native['phase'] == 4 and native['error'] == native['cleanup'] == 0
            and cleaned == dict(native, phase=5), 'Reader cleanup differs from the completed worker')


class ReaderStopped(ConnectionStop):
    def __init__(self, report):
        from reader_diagnostics import failure
        self.diagnostic = failure(report)
        super().__init__(self.diagnostic['message'] + '；临时数据已清理，可恢复普通 USB。',
                         'READER_STOPPED_CLEANED', report)


def verify_saved_failure(folder, nonce):
    folder = Path(folder)
    def decode(name):
        with open(io_path(folder / (name + '.bin')), 'rb') as stream:
            raw = stream.read()
        require(len(raw) == FRAME.size, 'Incomplete reader publication')
        magic, actual, *values = FRAME.unpack(raw)
        require(magic == b'M4P1RD01' and actual.hex() == nonce and values[0] == 1, 'Reader publication identity differs')
        row = dict(zip(FIELDS, values[:11]))
        return dict(row, first_sha256=values[11].hex(), second_sha256=values[12].hex())
    ready, native, cleaned = (decode(name) for name in ('ready', 'result', 'cleaned'))
    verify_failure_cleanup(ready, native, cleaned)
    report = read_json(folder / 'run.json')
    require(report.get('nonce') == nonce and report.get('native') == native and report.get('cleaned') == cleaned
            and report.get('verdict') == 'READER_STOPPED_CLEANED' and report.get('ram_chunks_cleaned') is True
            and report.get('module_uploads') == report.get('start_attempts') == 1 and report.get('ack_attempts') == 0
            and report.get('block_writes') is False and report.get('firmware_written') is False,
            'Reader failure summary differs from native cleanup')
    return dict(nonce=nonce, native=native, ram_chunks_cleaned=True, firmware_written=False)
