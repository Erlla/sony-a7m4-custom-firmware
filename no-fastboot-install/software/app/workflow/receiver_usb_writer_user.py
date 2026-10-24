from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ast
import importlib.util
import json
import struct
import sys
import time
from receiver_writer_job import CASE, ROOT, RAM, RESULT, MODE, decode, token, validate
from receiver_writer_job import file_sha, local_path, require, save_json
HARDWARE_TEST_REVIEWED = False
LAUNCH = struct.Struct('<8s16s10q')
MISSING_STATUS = 268435462

class ProtocolError(RuntimeError):
    pass

def poll_publication(name, size, directory, evidence, report, read, decode_result, *, sleep, clock, timeout):
    start = clock()
    while clock() - start < timeout:
        data = read(directory + '/' + name, size, missing=True)
        if data is not None:
            require(len(data) == size, 'Incomplete native publication; stop without retry')
            (evidence / (name + '.bin')).write_bytes(data)
            return data
        if name != 'result':
            result = read(directory + '/result', RESULT.size, missing=True)
            if result is not None:
                (evidence / 'result.bin').write_bytes(result)
                report['native'] = decode_result(result)
                raise ProtocolError('Native worker rejected before expected ' + name)
        failure = read(directory + '/exec_failure', 8, missing=True)
        if failure is not None:
            raise ProtocolError('Independent worker exec failed')
        sleep(0.1)
    raise TimeoutError('Native ' + name + ' deadline; do not repeat upload/COMMIT')

def run_protocol(session, folder, evidence, *, sleep=time.sleep, clock=time.monotonic, timeout=120):
    """One bootstrap, one PREPARE, one COMMIT; no retry of any write trigger."""
    folder = local_path(folder)
    meta = validate(folder)
    evidence = local_path(evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    save_json(folder / 'claim.json', dict(utc=datetime.now(timezone.utc).isoformat(), automatic_retry=False))
    report = dict(schema='m4-reviewed-full-p1-run/1', patch_set=meta['patch_set'], job_nonce=meta['nonce'], direction=meta['direction'], goal=meta['goal'], target_gate_state=meta['target_gate_state'], origin_gate_state=meta['origin_gate_state'], target_version_gate_kind=meta['target_version_gate_kind'], source_sha256=meta['source_sha256'], target_sha256=meta['target_sha256'], state='CLAIMED', module_uploads=0, prepare_attempts=0, commit_attempts=0, readback_windows=0, outcome='NOT_STARTED', normal_usb_recovery_verified=False, automatic_retry=False, device_operations_recorded_by_session=True)
    directory = meta['job_dir']
    write_paths = {directory + '/table', directory + '/prepare', directory + '/commit'} | {directory + '/' + w['name'] for w in meta['windows']}
    read_paths = write_paths | {'/tmp/jiritsu/libJit.so', directory + '/ready', directory + '/prepared', directory + '/launch', directory + '/result', directory + '/exec_failure'} | {directory + f'/rb{i:04d}' for i in range(len(meta['windows']))}

    def select(path):
        session._select(path if path == '/tmp/jiritsu/libJit.so' else '/tmp/jiritsu/../..' + path)

    def read(path, maximum, missing=False):
        require(path in read_paths, 'Out-of-scope writer read')
        select(path)
        try:
            data = session._read_selected(maximum)
            require(len(data) <= maximum, 'Oversized writer response')
            return data
        except Exception as error:
            if missing and getattr(error, 'status', None) == MISSING_STATUS:
                return None
            raise

    def write(path, value):
        require(path in write_paths or path == '/tmp/jiritsu/libJit.so', 'Out-of-scope writer upload')
        require(0 < len(value) <= 65520, 'Out-of-scope writer upload length')
        select(path)
        require(session._jiritsu(16, b'\x00\xff\x00' + value) == b'', 'Unexpected Jiritsu write acknowledgement')

    def poll(name, size):
        return poll_publication(name, size, directory, evidence, report, read, lambda raw: decode(raw, meta), sleep=sleep, clock=clock, timeout=timeout)
    try:
        blob = (folder / 'libJit.so').read_bytes()
        report['state'] = 'BOOTSTRAP_OUTCOME_UNKNOWN'
        report['module_uploads'] = 1
        write('/tmp/jiritsu/libJit.so', blob)
        ready = decode(poll('ready', RESULT.size), meta)
        launch = LAUNCH.unpack(poll('launch', LAUNCH.size))
        require(launch[:3] == (b'M4BOOT01', bytes.fromhex(meta['nonce']), 1) and launch[3] == 3 and (launch[4] == 0) and (launch[5] == 0) and (launch[7] == 0) and (launch[8] > 0) and (launch[9] == launch[8]) and (launch[10] == 0), 'Independent bootstrap launch proof failed')
        require(ready['phase'] == 2 and ready['error'] == 0 and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['loader_pid'] == launch[6]) and (ready['pid'] != ready['loader_pid']) and (ready['flags'] == 3) and (ready['write_calls'] == 0), 'Native ready contract failed')
        report['state'] = 'STAGING'
        for name in ['table'] + [w['name'] for w in meta['windows']]:
            value = (folder / 'assets' / name).read_bytes()
            write(directory + '/' + name, value)
            require(read(directory + '/' + name, len(value) + 1) == value, 'RAM staged packet differs')
        report['state'] = 'PREPARE_OUTCOME_UNKNOWN'
        report['prepare_attempts'] = 1
        write(directory + '/prepare', token(meta))
        prepared = decode(poll('prepared', RESULT.size), meta)
        require(prepared['phase'] == 3 and prepared['error'] == 0 and (prepared['flags'] == 31) and (prepared['write_calls'] == 0) and (prepared['before_sha256'] == meta['source_sha256']) and all((prepared[k] == ready[k] for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))), 'Prepared body/source/staging contract failed')
        report['prepared'] = prepared
        report['state'] = 'COMMIT_OUTCOME_UNKNOWN'
        report['outcome'] = 'COMMIT_OUTCOME_UNKNOWN'
        report['commit_attempts'] = 1
        save_json(evidence / 'commit_intent.json', report)
        write(directory + '/commit', token(meta, True))
        final = decode(poll('result', RESULT.size), meta)
        report['native'] = final
        if final['phase'] != 6 or final['error'] != 0:
            report['outcome'] = 'ROLLED_BACK_VERIFIED' if final['rollback'] == 1 and final['after_sha256'] == meta['source_sha256'] else 'NATIVE_FAILURE_REQUIRES_REVIEW'
            raise ProtocolError('Native writer did not confirm target; outcome ' + report['outcome'])
        require(final['flags'] == 255 and final['rollback'] == 0 and (final['after_sha256'] == meta['target_sha256']) and (final['before_sha256'] == meta['source_sha256']) and (final['io_status'] == 0) and all((final[k] == ready[k] for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))), 'Final full-image verification failed')
        report['state'] = 'HOST_READBACK'
        for i, row in enumerate(meta['windows']):
            value = read(directory + f'/rb{i:04d}', row['length'] + 1)
            expected = (folder / 'assets' / row['name']).read_bytes()[row['length']:]
            require(value == expected, 'Host readback differs after native verification')
            (evidence / f'rb{i:04d}.bin').write_bytes(value)
            report['readback_windows'] += 1
        report['state'] = 'P1_TARGET_VERIFIED'
        report['outcome'] = 'P1_TARGET_VERIFIED'
        return report
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error))
        if report['commit_attempts'] and report['outcome'] not in ('ROLLED_BACK_VERIFIED', 'NATIVE_FAILURE_REQUIRES_REVIEW'):
            report['outcome'] = 'COMMIT_OUTCOME_UNKNOWN'
        elif not report['commit_attempts']:
            report['outcome'] = 'STOPPED_BEFORE_COMMIT'
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save_json(evidence / 'run.json', report)

def hardware_gate():
    raise ValueError('Standalone receiver execution disabled; no USB backend loaded')
