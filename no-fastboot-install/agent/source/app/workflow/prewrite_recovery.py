"""Recover drivers only when the durable journal proves no p1 task started."""
import json
import os
from pathlib import Path
from state_io import io_path
from reader_cleanup import verify_saved_failure

BEFORE_READ = {'PREPARING', 'PREFLIGHT', 'BINDING', 'BOUND', 'REVIEW_REQUIRED', 'CONNECTION_STOPPED'}


def proof(journal):
    record = journal.load()
    if record is None or record['phase'] not in ('REVIEW_REQUIRED', 'CONNECTION_STOPPED'):
        return None
    if any(record.get(key) is not False for key in ('firmware_write_attempted', 'firmware_written', 'read_verified')):
        return None
    if any(record.get(key) is not None for key in ('preparation', 'writer_result', 'reader_result', 'after_reader_result')):
        return None
    try:
        with open(io_path(journal.folder / 'events.jsonl'), encoding='utf-8-sig') as stream:
            events = [json.loads(line) for line in stream if line.strip()]
        if not events or events[-1] != record:
            return None
        cleaned_reader = record.get('outcome') == 'READER_STOPPED_CLEANED'
        phases = BEFORE_READ | {'READ_STARTING'} if cleaned_reader else BEFORE_READ
        if any(row.get('run') != record['run'] or row.get('phase') not in phases or
               any(row.get(key) is not False for key in ('firmware_write_attempted', 'firmware_written', 'read_verified'))
               for row in events):
            return None
        for name in ('reader', 'after_reader'):
            job = record.get(name)
            claimed = job and os.path.exists(io_path(Path(job['job']) / 'claim.json'))
            if claimed and not (cleaned_reader and name == 'reader'):
                return None
        if cleaned_reader:
            if not record.get('reader'):
                return None
            verify_saved_failure(journal.folder / 'execution/before', record['reader']['nonce'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return dict(source_run=record['run'], reader_started=cleaned_reader, firmware_write_attempted=False)


def recover(value):
    import integrity_backend as backend
    import wizard as flow
    journal = backend.frozen.Journal(backend.STATE)
    evidence = proof(journal)
    if evidence is None:
        return None
    backend.require(journal.value['runner_sha256'] == backend.LOADED_SHA, '写前任务控制器不匹配，请保留记录')
    if journal.value['phase'] != 'CONNECTION_STOPPED':
        journal.update('CONNECTION_STOPPED', outcome='PREWRITE_CONNECTION_FAILED', session_ended=True)
    backend.atomic(flow.folder(value) / 'prewrite_stop.json', evidence)
    from standalone_usb_restore import recover as restore
    result = restore()
    phase = 'WINDOWS_RESTART_REQUIRED' if result['phase'] == 'USB_RESTORE_WINDOWS_RESTART' else 'CONNECTION_STOPPED'
    return flow.save(value, phase, prewrite_stop=True, patch_run=evidence['source_run'],
                     usb_recovery=result['phase'], message=result.get('message'),
                     recovery_folder=result.get('folder'), firmware_written=False)
