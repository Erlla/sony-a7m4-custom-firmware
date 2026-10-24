from product_integrity import pinned, state_path
from contextlib import contextmanager
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import uuid
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CASE))
OLD_TOOL = ROOT / 'app/provider'
STATE_DELIVERY = CASE
DELIVERY = CASE
P1_BYTES = 25100288
CHUNKS = 766
_LOADED_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
FULL_READ_VERIFIER = ROOT / 'app/reader_verify/full_read.py'
FULL_READ_VERIFIER_SHA = pinned('app/reader_verify/full_read.py')
PHASES = {'PREPARING', 'PREFLIGHT', 'BINDING', 'BOUND', 'READ_STARTING', 'READ_VERIFIED', 'SESSION_ENDED', 'RECOVERY_DISPATCHING', 'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART', 'COMPLETE', 'STOPPED_BEFORE_DRIVER_CHANGE', 'REVIEW_REQUIRED', 'PATCH_PREPARING', 'WRITE_STARTING', 'WRITE_VERIFIED', 'READBACK_STARTING'}
TERMINAL = {'COMPLETE', 'STOPPED_BEFORE_DRIVER_CHANGE'}
RECOVERABLE = {'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART'}

def require(value, message):
    if not value:
        raise ValueError(message)

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)

def local_path(root, relative):
    root = Path(root).resolve()
    require(isinstance(relative, str) and relative and (':' not in relative) and ('\\' not in relative) and (not relative.startswith('/')) and all((p not in ('', '.', '..') for p in relative.split('/'))), 'Invalid local path')
    result = root / relative
    require(result.resolve().is_relative_to(root), 'Path escapes state root')
    for item in (result, *result.parents):
        if item.exists():
            require(not getattr(item.lstat(), 'st_file_attributes', 0) & 1024, 'State or dependency reparse point is not accepted')
        if item == root:
            break
    return result

class StateError(ValueError):
    pass

class Journal:
    """A compact control copy is durable before each potentially consumed step."""

    def __init__(self, private):
        self.private = Path(private)
        self.folder = None
        self.value = None

    def validate(self, value, name):
        require(isinstance(value, dict) and value.get('schema') == 'm4-toolchain-read/1' and (value.get('run') == name) and (value.get('phase') in PHASES) and (type(value.get('revision')) is int) and (value['revision'] > 0) and (type(value.get('firmware_written')) is bool) and (value.get('automatic_retry') is False), 'Invalid control record')
        return value

    def load(self):
        pointer = self.private / 'current.json'
        if not pointer.exists():
            require(not any(((self.private / name).exists() and any((self.private / name).iterdir()) for name in ('runs', 'control'))), 'Missing index with existing state; review first')
            return None
        try:
            name = read(pointer)['run']
            require(isinstance(name, str) and re.fullmatch('[0-9]{8}T[0-9]{6}_[0-9a-f]{32}', name), 'Invalid run identity')
            self.folder = local_path(self.private, 'runs/' + name)
            compact = local_path(self.private, 'control/' + name + '.json')
            saved = self.validate(read(compact), name)
            primary = self.folder / 'status.json'
            if primary.exists():
                old = self.validate(read(primary), name)
                require(old['revision'] <= saved['revision'] and (old['revision'] != saved['revision'] or old == saved), 'State copies conflict')
            elif saved['phase'] not in TERMINAL | RECOVERABLE:
                raise StateError('Run directory missing during an unresolved operation')
            self.value = saved
            return saved
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise StateError('State requires review; no camera operation: ' + str(error)) from error

    def create(self, runner_sha256):
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_') + uuid.uuid4().hex
        self.folder = local_path(self.private, 'runs/' + name)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.value = dict(schema='m4-toolchain-read/1', run=name, revision=0, created_utc=utc(), runner_sha256=runner_sha256, firmware_written=False, firmware_write_attempted=False, automatic_retry=False, read_verified=False, session_ended=False, normal_recovery_verified=False, outcome='NOT_STARTED')
        self.update('PREPARING')
        atomic(self.private / 'current.json', dict(run=name))

    def update(self, phase, **values):
        require(phase in PHASES, 'Unknown phase')
        self.value.update(values, phase=phase, updated_utc=utc(), revision=self.value['revision'] + 1)
        name = self.value['run']
        atomic(self.private / 'control' / (name + '.json'), self.value)
        self.folder.mkdir(parents=True, exist_ok=True)
        atomic(self.folder / 'status.json', self.value)
        with (self.folder / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(self.value, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

class Engine:
    """Injected backend makes failure boundaries testable without USB imports."""

    def __init__(self, backend, private, emit=print):
        self.backend = backend
        self.journal = Journal(private)
        self.emit = emit

    def state(self):
        return self.journal.load()

    def finish_recovery(self, result):
        require(result in ('VERIFIED', 'NORMAL_CONNECTION_PENDING', 'RESTART_REQUIRED'), 'Unknown recovery outcome')
        if result == 'VERIFIED':
            self.journal.update('COMPLETE', normal_recovery_verified=True, outcome=self.journal.value.get('verified_outcome', 'P1_FULL_READ_AND_NORMAL_USB_VERIFIED'))
        else:
            self.journal.update('WAITING_FOR_RESTART' if result == 'RESTART_REQUIRED' else 'WAITING_FOR_NORMAL', normal_recovery=result)

    def recover(self):
        self.backend.check()
        state = self.journal.load()
        require(state is not None and state['phase'] in RECOVERABLE, 'No known pending recovery')
        require(state['read_verified'] is True and state['session_ended'] is True and (state['runner_sha256'] == self.backend.runner_sha()), 'Recovery evidence or runner differs')
        if state.get('firmware_write_attempted'):
            after = state.get('after_reader_result') or {}
            require(state.get('firmware_written') is True and state.get('verified_outcome') == 'PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED' and ((state.get('writer_result') or {}).get('outcome') == 'P1_TARGET_VERIFIED') and (after.get('verdict') == 'P1_READBACK_VERIFIED') and (after.get('sha256') == state.get('target_sha256') == state.get('p1_sha256')) and (after.get('nonce') == (state.get('after_reader') or {}).get('nonce')) and (after.get('ram_chunks_cleaned') is True) and (after.get('bytes') == P1_BYTES) and (after.get('chunks') == CHUNKS), 'Complete independent write/readback evidence is missing')
        elif state.get('action') in ('apply', 'restore'):
            require(state.get('verified_outcome') == 'ALREADY_AT_TARGET_FULL_READ_NO_WRITE', 'No-change proof is missing')
        confirmation = state['phase'] == 'WAITING_FOR_RESTART'
        if confirmation and (not self.backend.normal_ready(self.journal.folder)):
            return state
        self.journal.update('RECOVERY_DISPATCHING')
        try:
            self.finish_recovery(self.backend.restore(self.journal.folder, confirmation=confirmation))
        except BaseException as error:
            self.journal.update('REVIEW_REQUIRED', outcome='RECOVERY_OUTCOME_UNKNOWN', error=str(error))
            raise
        return self.journal.value

    def read(self, action='read', bundle=None):
        require(action in ('read', 'apply', 'restore'), 'Unknown camera action')
        require(action != 'restore' or bundle is not None, 'Restore requires the original saved bundle')
        self.backend.check()
        prior = self.journal.load()
        require(prior is None or prior['phase'] in TERMINAL, 'Previous run unresolved; use recover only for a known recovery wait, otherwise review logs')
        self.journal.create(self.backend.runner_sha())
        self.journal.update('PREPARING', action=action, restore_bundle=str(bundle) if bundle is not None else None)
        folder = self.journal.folder
        self.emit('正在准备新的完整 p1 读取任务；本轮只读取，不写入固件。' if action == 'read' else '正在准备完整备份与独立回读；本轮会按当前 p1 状态决定是否写入，请保持供电和 USB 稳定。')
        try:
            job = self.backend.prepare_reader(folder)
            after_job = self.backend.prepare_reader(folder, role='after') if action != 'read' else None
            self.journal.update('PREFLIGHT', reader=job, after_reader=after_job)
            self.backend.preflight(folder)
        except BaseException as error:
            self.journal.update('STOPPED_BEFORE_DRIVER_CHANGE', outcome='LOCAL_OR_PREFLIGHT_FAILED', error=str(error))
            raise
        self.journal.update('BINDING')
        try:
            self.backend.bind(folder)
            self.journal.update('BOUND')
        except BaseException as error:
            self.journal.update('REVIEW_REQUIRED', outcome='DRIVER_BIND_OUTCOME_UNKNOWN', error=str(error))
            raise
        try:
            with self.backend.session(folder) as session:
                try:
                    self.backend.verify_ready(job, self.journal.value)
                    self.journal.update('READ_STARTING')
                    self.emit('正在读取 25,100,288 字节 p1，核对两次机内摘要、766 块及主机完整摘要。')
                    source, result = self.backend.run_reader(session, job, folder)
                    require(result.get('verdict') == 'P1_READBACK_VERIFIED' and result.get('bytes') == P1_BYTES and (result.get('chunks') == CHUNKS) and (result.get('nonce') == job['nonce']) and (result.get('block_writes') is False) and (result.get('firmware_written') is False) and (result.get('ram_chunks_cleaned') is True) and (Path(source).stat().st_size == P1_BYTES) and (sha(source) == result.get('sha256')), 'Full read/hash/nonce/cleanup contract not met')
                    self.journal.update('READ_VERIFIED', read_verified=True, source=str(source), p1_sha256=result['sha256'], p1_bytes=P1_BYTES, reader_result=result, outcome='P1_FULL_READ_VERIFIED')
                    if action != 'read':
                        self.journal.update('PATCH_PREPARING')
                        preparation = self.backend.prepare_write(source, folder, action, bundle)
                        require(preparation['source_sha256'] == result['sha256'] and re.fullmatch('[0-9a-f]{64}', preparation['target_sha256']) is not None, 'Prepared source/target differs from complete current read')
                        self.journal.update('PATCH_PREPARING', preparation=preparation)
                        if preparation['no_change']:
                            require(preparation['target_sha256'] == result['sha256'], 'No-change target differs')
                            self.journal.update('READ_VERIFIED', verified_outcome='ALREADY_AT_TARGET_FULL_READ_NO_WRITE', outcome='ALREADY_AT_TARGET_FULL_READ_NO_WRITE', target_sha256=result['sha256'], patch_state=preparation['final_state'])
                        else:
                            self.backend.verify_write_ready(preparation, after_job, self.journal.value)
                            self.journal.update('WRITE_STARTING', firmware_write_attempted=True, target_sha256=preparation['target_sha256'])
                            writer = self.backend.run_writer(session, preparation, folder)
                            require(writer.get('outcome') == 'P1_TARGET_VERIFIED', 'Writer target not verified')
                            self.journal.update('WRITE_VERIFIED', firmware_written=True, writer_result=writer)
                            self.journal.update('READBACK_STARTING')
                            after_source, after_result = self.backend.run_reader(session, after_job, folder)
                            require(after_result.get('verdict') == 'P1_READBACK_VERIFIED' and after_result.get('bytes') == P1_BYTES and (after_result.get('chunks') == CHUNKS) and (after_result.get('nonce') == after_job['nonce']) and (after_result.get('block_writes') is False) and (after_result.get('firmware_written') is False) and (after_result.get('ram_chunks_cleaned') is True) and (sha(after_source) == after_result.get('sha256') == preparation['target_sha256']), 'Independent complete readback contract failed')
                            final_state = self.backend.verify_written(source, after_source, preparation)
                            self.journal.update('READ_VERIFIED', after_source=str(after_source), after_reader_result=after_result, patch_state=final_state, p1_sha256=after_result['sha256'], verified_outcome='PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED', outcome='PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED')
                except BaseException:
                    self.backend.hold_session(session)
                    raise
            self.journal.update('SESSION_ENDED', session_ended=True)
        except BaseException as error:
            self.journal.update('REVIEW_REQUIRED', outcome='READ_OR_SESSION_OUTCOME_REQUIRES_REVIEW', error=str(error))
            raise
        self.journal.update('RECOVERY_DISPATCHING')
        try:
            self.finish_recovery(self.backend.restore(folder, confirmation=False))
        except BaseException as error:
            self.journal.update('REVIEW_REQUIRED', outcome='RECOVERY_OUTCOME_UNKNOWN', error=str(error))
            raise
        return self.journal.value

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def release_check():
    from product_integrity import verify_release
    return verify_release()

class WorkspaceBackend:
    """Restricted subset of the frozen provider; never calls inspect/build/write."""

    def __init__(self):
        self.provider = None
        self.legacy = None

    def preflight(self, folder):
        self.provider.preflight(folder)

    def bind(self, folder):
        self.provider.bind(folder)

    def session(self, folder):
        return self.provider.session(folder)

    def hold_session(self, session):
        self.provider.hold_session(session)

    def restore(self, folder, confirmation=False):
        return self.provider.restore(folder, confirmation=confirmation)

    def normal_ready(self, folder):
        return self.provider.normal_ready(folder)
