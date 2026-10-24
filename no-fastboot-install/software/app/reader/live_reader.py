from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
import argparse, hashlib, importlib.util, json, struct, time
from reader_job import CASE, ROOT, RESULT, CHUNK, COUNT, P1_BYTES, validate, decode
from common import require, save_json
LAUNCH = struct.Struct('<8s16s10q')

def run_protocol(session, folder, out, *, sleep=time.sleep, clock=time.monotonic):
    meta = validate(folder)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    save_json(Path(folder) / 'claim.json', dict(utc=datetime.now(timezone.utc).isoformat(), automatic_retry=False))
    directory = meta['job_dir']
    report = dict(module_uploads=0, start_attempts=0, ack_attempts=0, chunks=0, block_writes=False, firmware_written=False, verdict='STOPPED', nonce=meta['nonce'])

    def read(name, size, missing=False):
        require(name in ('launch', 'ready', 'result', 'cleaned', 'digests', 'loader_maps', 'loader_fds', 'mountinfo', 'exec_failure') or (len(name) == 5 and name[0] == 'c' and name[1:].isdigit() and (int(name[1:]) < COUNT)), 'Out-of-scope read')
        session._select('/tmp/jiritsu/../..' + directory + '/' + name)
        try:
            return session._read_selected(size)
        except Exception as error:
            if missing and getattr(error, 'status', None) == 268435462:
                return None
            raise

    def write(name, data):
        require(name in ('module', 'start', 'ack'), 'Out-of-scope upload')
        path = '/tmp/jiritsu/libJit.so' if name == 'module' else '/tmp/jiritsu/../..' + directory + '/' + name
        session._select(path)
        require(session._jiritsu(16, b'\x00\xff\x00' + data) == b'', 'Unexpected write acknowledgement')

    def poll(name, size, timeout=120):
        begin = clock()
        while clock() - begin < timeout:
            raw = read(name, size, True)
            if raw is not None:
                require(len(raw) == size, 'Partial publication; stop without retry')
                (out / (name + '.bin')).write_bytes(raw)
                return raw
            failure = read('exec_failure', 8, True)
            require(failure is None, 'Independent exec failed')
            if name not in ('result', 'cleaned'):
                result = read('result', RESULT.size, True)
                if result is not None:
                    (out / 'result.bin').write_bytes(result)
                    report['native'] = decode(result, meta)
                    raise RuntimeError('Reader rejected before ' + name)
            sleep(0.2)
        raise TimeoutError('Reader ' + name + ' timeout; do not upload again')
    try:
        report['module_uploads'] = 1
        write('module', (Path(folder) / 'libJit.so').read_bytes())
        launch = LAUNCH.unpack(poll('launch', LAUNCH.size))
        ready = decode(poll('ready', RESULT.size), meta)
        require(launch[:3] == (b'M4BOOT01', bytes.fromhex(meta['nonce']), 1) and launch[3:6] == (3, 0, 0) and (launch[7] == 0) and (launch[8] > 0) and (launch[8] == launch[9]) and (launch[10] == 0), 'Launch failed')
        require(ready['phase'] == 1 and ready['error'] == 0 and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['flags'] == 3) and (ready['loader_pid'] == launch[6]) and (ready['pid'] != launch[6]), 'Ready failed')
        report['start_attempts'] = 1
        write('start', b'M4START1' + bytes.fromhex(meta['nonce']) + struct.pack('<Q', 1))
        native = decode(poll('result', RESULT.size), meta)
        report['native'] = native
        require(native['phase'] == 4 and native['error'] == 0 and (native['flags'] == 127) and (native['bytes'] == P1_BYTES) and (native['chunks'] == COUNT) and (native['first_sha256'] == native['second_sha256']) and all((native[k] == ready[k] for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))), 'Native p1 read rejected: ' + str(native))
        digests = read('digests', COUNT * 32 + 1)
        require(len(digests) == COUNT * 32, 'Digest manifest size differs')
        (out / 'digests.bin').write_bytes(digests)
        for name, cap in [('loader_maps', 524289), ('loader_fds', 131073), ('mountinfo', 131073)]:
            value = read(name, cap)
            require(value and len(value) < cap, 'Incomplete proc audit')
            (out / (name + '.txt')).write_bytes(value)
        h = hashlib.sha256()
        with (out / 'nflasha1.bin').open('xb') as stream:
            for i in range(COUNT):
                size = min(CHUNK, P1_BYTES - i * CHUNK)
                data = read(f'c{i:04d}', size + 1)
                require(len(data) == size and hashlib.sha256(data).digest() == digests[i * 32:(i + 1) * 32], 'Chunk verification failed')
                stream.write(data)
                h.update(data)
                report['chunks'] = i + 1
                if i % 64 == 0:
                    print(json.dumps(dict(progress_chunks=i + 1, total_chunks=COUNT)), flush=True)
        require(h.hexdigest() == native['first_sha256'], 'Host full p1 digest differs')
        report.update(verdict='P1_READBACK_VERIFIED', sha256=h.hexdigest(), bytes=P1_BYTES)
        report['ack_attempts'] = 1
        write('ack', b'M4ACK001' + bytes.fromhex(meta['nonce']) + struct.pack('<Q', 1))
        cleaned = decode(poll('cleaned', RESULT.size), meta)
        require(cleaned['phase'] == 5 and cleaned['error'] == 0 and (cleaned['cleanup'] == 0), 'RAM cleanup not confirmed')
        report['ram_chunks_cleaned'] = True
        return report
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save_json(out / 'run.json', report)
