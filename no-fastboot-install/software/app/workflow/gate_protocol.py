from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import struct
import sys
import time
CASE = Path(__file__).resolve().parent
WINDOW = CASE.parent / 'menu_transport'
sys.path.insert(0, str(WINDOW))
import run_window as base
from integrity_backend import frozen
from version_labels import consistent
jobs = frozen.load_module('m4_userflow_jobs_stock', CASE.parent / 'menu_stock/dual_job.py')
RESULT, FIELDS, PATCHED_FLAGS, RESTORED_FLAGS, decode, validate = (getattr(jobs, name) for name in ('RESULT', 'FIELDS', 'PATCHED_FLAGS', 'RESTORED_FLAGS', 'decode', 'validate'))
from common import require
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app/provider'))
from local_json import atomic
IDENTITY_FIELDS = ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup')

def validate_job_integrity(job):
    """Integrity only; no per-job simulated execution or synthetic proof."""
    from integrity_backend import release_check
    release_check()
    meta = validate(job)
    return (meta, None, None)

def protocol_sources():
    return {name: hashlib.sha256((CASE / name).read_bytes()).hexdigest() for name in ('gate_protocol.py',)}

def safe_terminal(value):
    """Restoration can be safe even if the experiment itself failed."""
    if not isinstance(value, dict):
        return False
    row, ready = (value.get('native'), value.get('ready'))
    if not isinstance(row, dict) or not isinstance(ready, dict) or (not same_worker(row, ready)):
        return False
    if row.get('phase') not in (6, 90):
        return False
    if any((type(row.get(k)) is not int for k in FIELDS)):
        return False
    lib_safe = not row.get('flags', 0) & 512 and row.get('patched') == 0 or (row.get('restored') == 1 and row.get('restore_status') == 0 and (row.get('lib_identity_status') == 0))
    app_safe = row.get('app_write_attempted') == 0 and row.get('app_patched') == 0 or (row.get('app_restored') == 1 and row.get('app_restore_status') == 0 and (row.get('app_identity_status') == 0))
    return lib_safe and app_safe

def utc():
    return datetime.now(timezone.utc).isoformat()

def same_worker(row, ready):
    return isinstance(row, dict) and isinstance(ready, dict) and all((k in row and k in ready and (row[k] == ready[k]) for k in IDENTITY_FIELDS))

def restored(row, ready, meta):
    return same_worker(row, ready) and row['phase'] == 6 and (row['error'] == 0) and (row['patched'] == 1) and (row['restored'] == 1) and (row['flags'] == RESTORED_FLAGS) and (row['mem_status'] == 0) and (row['restore_status'] == 0) and (row['hold_seconds'] >= meta['hold_seconds']) and consistent(row['machine_version'], row['app_machine_version']) and (row['app_patched'] == 1) and (row['app_restored'] == 1) and (row['app_write_attempted'] == 1) and (row['app_mem_status'] == 0) and (row['app_restore_status'] == 0) and (row['lib_identity_status'] == 0) and (row['app_identity_status'] == 0)

class Channel:

    def __init__(self, session, meta, evidence):
        self.session, self.meta, self.evidence = (session, meta, Path(evidence))

    def select(self, path):
        return base.transport_call(self.session._select, path if path == '/tmp/jiritsu/libJit.so' else '/tmp/jiritsu/../..' + path)

    def read(self, name):
        require(name in ('ready', 'launch', 'patched', 'result', 'exec_failure'), 'Read outside window scope')
        maximum = base.LAUNCH.size if name == 'launch' else 8 if name == 'exec_failure' else RESULT.size
        self.select(self.meta['job_dir'] + '/' + name)
        try:
            raw = base.transport_call(self.session._read_selected, maximum)
        except Exception as error:
            if getattr(error, 'status', None) == base.MISSING_STATUS:
                return None
            raise
        require(len(raw) == maximum, 'Incomplete native ' + name + '; no retry')
        (self.evidence / (name + '.bin')).write_bytes(raw)
        return raw

    def write(self, name, value):
        require(name in ('libJit.so', 'start'), 'Write outside window scope')
        path = '/tmp/jiritsu/libJit.so' if name == 'libJit.so' else self.meta['job_dir'] + '/start'
        require(0 < len(value) <= 65520, 'Window upload exceeds bound')
        self.select(path)
        require(base.transport_call(self.session._jiritsu, 16, b'\x00\xff\x00' + value) == b'', 'Unexpected upload acknowledgement')

def start_handoff(session, job, evidence, *, clock=time.monotonic, sleep=time.sleep):
    job, evidence = (Path(job), Path(evidence))
    meta, _, _ = validate_job_integrity(job)
    evidence.mkdir(parents=True, exist_ok=False)
    with (job / 'claim.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(dict(utc=utc(), purpose='dual_menu_gate_confirmation', automatic_retry=False), stream)
    channel = Channel(session, meta, evidence)
    report = dict(schema='m4-dual-menu-handoff/1', nonce=meta['nonce'], state='PREPARING', upload_attempts=0, start_attempts=0, start_acknowledged=False, patch_marker_observed=False, restoration_verified=False, installation_status='NOT_OBSERVED', automatic_retry=False)

    def save():
        atomic(evidence / 'run.json', report)

    def poll(name, seconds):
        deadline = clock() + seconds
        while clock() < deadline:
            terminal = channel.read('result')
            if terminal is not None:
                report['native'] = decode(terminal, meta)
                raise base.ProtocolError('Worker ended before handoff')
            raw = channel.read(name)
            if raw is not None:
                return raw
            if channel.read('exec_failure') is not None:
                raise base.ProtocolError('Worker exec failed')
            sleep(0.5)
        raise base.NativeDeadline('No ' + name + ' publication; no retry')
    try:
        report.update(state='BOOTSTRAP_OUTCOME_UNKNOWN', upload_attempts=1)
        save()
        channel.write('libJit.so', (job / 'libJit.so').read_bytes())
        ready = decode(poll('ready', 180), meta)
        launch = base.LAUNCH.unpack(poll('launch', 30))
        require(launch[:3] == (b'M4BOOT01', bytes.fromhex(meta['nonce']), 1) and launch[3] == 3 and (launch[4] == 0) and (launch[7] == 0) and (launch[8] > 0) and (launch[9] == launch[8]) and (launch[10] == 0), 'Bootstrap launch proof failed')
        require(ready['phase'] == 1 and ready['error'] == 0 and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['flags'] == 13) and (ready['loader_pid'] == launch[6]) and (ready['pid'] != ready['loader_pid']), 'Worker ready proof failed')
        report['ready'] = ready
        started = clock()
        report.update(state='START_OUTCOME_UNKNOWN', start_attempts=1, start_utc=utc())
        save()
        channel.write('start', b'M4DSTART' + bytes.fromhex(meta['nonce']) + struct.pack('<Q', 1))
        report.update(start_acknowledged=True, state='WAITING_FOR_PATCH')
        save()
        patched = decode(poll('patched', meta['maps_wait_seconds'] + 30), meta)
        require(same_worker(patched, ready) and patched['phase'] == 5 and (patched['error'] == 0) and (patched['patched'] == 1) and (patched['restored'] == 0) and (patched['flags'] == PATCHED_FLAGS) and (patched['target_addr'] == patched['base_addr'] + meta['patch_offset']) and (patched['app_target_addr'] == patched['app_base_addr'] + 40219336) and consistent(patched['machine_version'], patched['app_machine_version']) and (patched['app_patched'] == 1) and (patched['app_restored'] == 0) and (patched['app_write_attempted'] == 1) and (patched['app_pid'] > 1) and (patched['mem_status'] == 0) and (patched['app_mem_status'] == 0) and (patched['snapshot_before_status'] == 0) and (patched['proc_candidates'] == 1) and (patched['lib_identity_status'] == 0) and (patched['app_identity_status'] == 0), 'Current content-bound patch publication proof failed')
        report.update(patched=patched, patch_marker_observed=True, patch_observed_utc=utc())
        terminal = channel.read('result')
        if terminal is not None:
            report['native'] = decode(terminal, meta)
            report['restoration_verified'] = restored(report['native'], ready, meta)
            raise base.ProtocolError('Window ended before UI handoff')
        remaining = meta['hold_seconds'] - (clock() - started)
        require(remaining >= 120, 'Insufficient conservative time for menu test')
        report.update(state='HANDOFF_READY', conservative_seconds_remaining=remaining)
        return report
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error))
        report['state'] = 'REVIEW_REQUIRED'
        raise
    finally:
        report['recorded_utc'] = utc()
        save()

def collect_result(session, job, handoff, evidence, *, clock=time.monotonic, sleep=time.sleep, progress=None):
    """Read existing publications only: this function has no upload/START path."""
    meta, _, _ = validate_job_integrity(job)
    require(handoff['nonce'] == meta['nonce'] and handoff['state'] == 'HANDOFF_READY' and handoff['start_acknowledged'] and handoff['patch_marker_observed'], 'Invalid handoff receipt')
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    channel = Channel(session, meta, evidence)
    report = dict(schema='m4-dual-menu-collection/1', state='READING', nonce=meta['nonce'], module_uploads=0, start_attempts=0, restoration_verified=False, installation_status='NOT_OBSERVED')
    try:
        ready_raw, patched_raw = (channel.read('ready'), channel.read('patched'))
        require(ready_raw is not None and patched_raw is not None, 'Original tmpfs publications missing; reboot or cleanup not established')
        require(decode(ready_raw, meta) == handoff['ready'] and decode(patched_raw, meta) == handoff['patched'], 'Original worker publications differ')
        deadline, last_progress = (clock() + meta['hold_seconds'] + 120, clock())
        while clock() < deadline:
            raw = channel.read('result')
            if raw is not None:
                row = decode(raw, meta)
                report['native'] = row
                require(restored(row, handoff['ready'], meta) and all((row[k] == handoff['patched'][k] for k in ('app_pid', 'app_target_addr', 'app_base_addr', 'target_addr', 'base_addr'))), 'Both original instructions and target identities must be restored')
                report.update(state='WINDOW_COMPLETED_RESTORED', restoration_verified=True)
                return report
            if progress and clock() - last_progress >= 45:
                progress()
                last_progress = clock()
            sleep(1)
        raise base.NativeDeadline('No restoration result; elapsed host time is not restoration proof')
    except BaseException as error:
        report['state'] = 'REVIEW_REQUIRED'
        report['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        report['recorded_utc'] = utc()
        atomic(evidence / 'run.json', report)
