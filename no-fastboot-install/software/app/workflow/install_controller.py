from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import importlib
import json
import math
import os
import struct
import sys
import time
import uuid
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'state/workflow'
WINDOW = CASE.parent / 'menu_stock'
REPAIR = CASE.parent / 'receiver_stock'
READER = CASE.parent / 'reader'
TOOL = ROOT / 'app/provider'
DAT = None
DAT_SHA = None
DAT_BYTES = None
P1_SHA = None
P1_BYTES, CHUNK_BYTES, CHUNKS = (25100288, 32768, 766)
SD_SHA = 'f6c68faca339cadff1c1bda5aca9971fb4fcf3af5ac5150ccb6e59f489b65c75'
CORE_SHA = 'cfe23b709f1a4feba16642729f39c9bb5f4516caa188fa67a6d31d3c1d833425'
PATCH_SET = 'sd-signature-version-bool1-and-core-gates/1'
HOLD_SECONDS = 600
PLAN_SCHEMA = 'm4-corrected-install-plan/1'
STATUS_SCHEMA = 'm4-corrected-install-status/1'
READ_FRAME = struct.Struct('<8s16s11q32s32s')
READ_FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'bytes', 'chunks', 'flags')
ACTIVE_PHASES = ('AWAITING_MENU_OBSERVATION', 'HANDOFF_NOT_READY', 'COLLECTION_PENDING', 'WAITING_FOR_USER_INSTALL_RESULT', 'INSTALL_FAILURE_REPORTED', 'REVIEW_REQUIRED')

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))
from local_json import atomic

def utc():
    return datetime.now(timezone.utc).isoformat()

def parse_utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, 'UTC timestamp required')
    return result

def stamp():
    return dict(monotonic=time.monotonic(), utc=utc())

def remaining(status, now=None):
    """Never restart the native hold at the first patched observation.

    The host budget begins before bootstrap upload, earlier than native START.
    Both clocks must advance consistently. A reset, backward jump, or > 5 s
    disagreement refuses installation. Only the smaller remaining budget wins.
    """
    now = stamp() if now is None else now
    start = status['window_start_bound']
    mono = now['monotonic'] - start['monotonic']
    wall = (parse_utc(now['utc']) - parse_utc(start['utc'])).total_seconds()
    require(all((math.isfinite(x) for x in (mono, wall))) and mono >= 0 and (wall >= 0) and (abs(mono - wall) <= 5), 'Host clock continuity unavailable; do not start installation')
    elapsed = max(mono, wall, status.get('window_elapsed_floor', 0))
    return (max(0, HOLD_SECONDS - elapsed), elapsed)

def under(path, parent):
    path, parent = (Path(path).resolve(), Path(parent).resolve())
    require(path.is_relative_to(parent), 'Path outside reviewed local evidence: ' + str(path))
    return path

def verify_hash_set(paths, recorded):
    expected = {str(Path(path)) for path in paths}
    require(isinstance(recorded, dict) and set(recorded) == expected, 'Required evidence hash keys are missing or unexpected')
    for path in expected:
        require(sha(path) == recorded[path], 'Bound evidence changed: ' + path)

def emit(phase, **values):
    print(json.dumps(dict(phase=phase, **values), ensure_ascii=False), flush=True)

def frozen_pins():
    from integrity_backend import release_check
    return release_check()['files']

def runtime():
    frozen_pins()
    for folder in (TOOL, WINDOW, READER, REPAIR):
        sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location('m4_userflow_protocol', CASE / 'gate_protocol.py')
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    jobs = protocol.jobs
    provider = importlib.import_module('user_provider')
    engine = importlib.import_module('engine')
    reader_jobs = importlib.import_module('reader_job')
    live_reader = importlib.import_module('live_reader')
    from integrity_backend import frozen
    adapter = frozen.load_module('m4_userflow_receiver_stock', REPAIR / 'receiver.py')
    require(Path(protocol.__file__).resolve() == (CASE / 'gate_protocol.py').resolve() and Path(jobs.__file__).resolve() == (WINDOW / 'dual_job.py').resolve() and (Path(provider.__file__).resolve() == (CASE / 'user_provider.py').resolve()) and (Path(reader_jobs.__file__).resolve() == (READER / 'reader_job.py').resolve()) and (Path(live_reader.__file__).resolve() == (READER / 'live_reader.py').resolve()) and (Path(adapter.__file__).resolve() == (REPAIR / 'receiver.py').resolve()), 'Unexpected module reuse')
    return SimpleNamespace(protocol=protocol, jobs=jobs, Provider=provider.Provider, single_instance=engine.single_instance, reader_jobs=reader_jobs, live_reader=live_reader, adapter=adapter)

def source_pins():
    return frozen_pins()

def decode_reader(raw, nonce):
    require(len(raw) == READ_FRAME.size, 'Incomplete full-reader frame')
    magic, actual, *values = READ_FRAME.unpack(raw)
    require(magic == b'M4P1RD01' and actual.hex() == nonce, 'Wrong full-reader nonce')
    result = dict(zip(READ_FIELDS, values[:11]))
    result.update(first_sha256=values[11].hex(), second_sha256=values[12].hex())
    require(result['version'] == 1, 'Wrong full-reader ABI')
    return result

def verify_full_read(folder, reader, expected_sha=P1_SHA):
    """Check actual saved bytes and all 766 chunks against the native read."""
    folder = Path(folder)
    proof = read(folder / 'run.json')
    require(proof.get('verdict') == 'P1_READBACK_VERIFIED' and proof.get('nonce') == reader['nonce'] and (proof.get('sha256') == expected_sha) and (proof.get('bytes') == P1_BYTES) and (proof.get('chunks') == CHUNKS) and (proof.get('ram_chunks_cleaned') is True) and (proof.get('block_writes') is False) and (proof.get('module_uploads') == 1) and (proof.get('start_attempts') == 1) and (proof.get('ack_attempts') == 1), 'Actual independent full read is incomplete')
    rows = {name: decode_reader((folder / (name + '.bin')).read_bytes(), reader['nonce']) for name in ('ready', 'result', 'cleaned')}
    ready, final, cleaned = (rows[name] for name in ('ready', 'result', 'cleaned'))
    require(ready['phase'] == 1 and ready['error'] == 0 and (ready['flags'] == 3) and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['pid'] > 1) and (ready['loader_pid'] > 1) and (ready['pid'] != ready['loader_pid']), 'Reader ready identity differs')
    require(final == proof['native'] and final['phase'] == 4 and (final['error'] == 0) and (final['flags'] == 127) and (final['bytes'] == P1_BYTES) and (final['chunks'] == CHUNKS) and (final['first_sha256'] == final['second_sha256'] == expected_sha), 'Reader double-source digest differs')
    require(cleaned == dict(final, phase=5) and all((row[k] == ready[k] for row in (final, cleaned) for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))), 'Reader cleanup/identity differs')
    path = folder / 'nflasha1.bin'
    require(path.stat().st_size == P1_BYTES and sha(path) == expected_sha, 'Actual full p1 differs from expected digest')
    digests = (folder / 'digests.bin').read_bytes()
    require(len(digests) == CHUNKS * 32, 'Wrong chunk digest extent')
    with path.open('rb') as stream:
        for index in range(CHUNKS):
            chunk = stream.read(min(CHUNK_BYTES, P1_BYTES - index * CHUNK_BYTES))
            require(hashlib.sha256(chunk).digest() == digests[index * 32:(index + 1) * 32], 'Saved p1 chunk differs')
        require(stream.read(1) == b'', 'Extra p1 bytes')
    return {str(folder / name): sha(folder / name) for name in ('run.json', 'ready.bin', 'result.bin', 'cleaned.bin', 'digests.bin', 'nflasha1.bin')}

def receiver_evidence():
    from integrity_backend import STATE, LOADED_SHA, reader_integrity, frozen
    status = frozen.Journal(STATE).load()
    require(status is not None and status.get('phase') == 'COMPLETE' and (status.get('action') == 'apply') and (status.get('runner_sha256') == LOADED_SHA) and (status.get('read_verified') is True) and (status.get('session_ended') is True) and (status.get('normal_recovery_verified') is True), '需要本次完整补丁检查与普通连接恢复')
    digest = status['p1_sha256']
    require(digest == status['target_sha256'] and status['outcome'] == status['verified_outcome'], '本次补丁结果不一致')
    prep = status['preparation']
    require(prep['lineage'] == 'stock' and prep['target_sha256'] == digest, '当前更新器内容与本次补丁路线不匹配')
    if status['verified_outcome'] == 'ALREADY_AT_TARGET_FULL_READ_NO_WRITE':
        require(prep['no_change'] is True and status['firmware_write_attempted'] is False and (status['firmware_written'] is False) and (prep['source_sha256'] == digest), '无写入结果不一致')
        reader, source = (status['reader'], Path(status['source']))
    else:
        require(status['verified_outcome'] == 'PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED' and prep['no_change'] is False and (status['firmware_write_attempted'] is True) and (status['firmware_written'] is True) and (status['writer_result']['outcome'] == 'P1_TARGET_VERIFIED') and (status['writer_result']['target_sha256'] == digest), '独立回读证明不完整')
        reader, source = (status['after_reader'], Path(status['after_source']))
    job = Path(reader['job'])
    meta = reader_integrity(job, unused=False)
    require(meta['nonce'] == reader['nonce'] and sha(job / 'job.json') == reader['job_sha256'] and (sha(job / 'integrity.json') == reader['integrity_sha256']), '已保存读取材料变化')
    folder = under(source.parent, STATE / 'runs' / status['run'])
    hashes = verify_full_read(folder, reader, expected_sha=digest)
    adapter = runtime().adapter
    actual = adapter.inspect_bytes(source.read_bytes())[0]
    require(actual == status['patch_state'], '补丁语义记录不匹配')
    receiver_semantics(actual)
    for path in (STATE / 'control' / (status['run'] + '.json'), STATE / 'runs' / status['run'] / 'status.json', job / 'job.json', job / 'integrity.json'):
        hashes[str(path)] = sha(path)
    return dict(receiver_p1_sha256=digest, receiver_bytes=P1_BYTES, accepted_reader_nonce=reader['nonce'], accepted_run=status['run'], hashes=hashes)

def receiver_semantics(current):
    require(current['trust_state'] == 'stock_key_version_true' and current['bytes'] == P1_BYTES and (current['version_boolean_return'] == 1) and (current['signature_success_status'] == 0) and (current['key_sha256'] == '8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43') and all((not row['patched'] for row in current['libraries'].values())) and (current['libraries']['libsdfileinputupdaterapi.so']['sha256'] == SD_SHA) and (current['chkfirm_version_gate']['sha256'] == CORE_SHA) and (current['chkfirm_version_gate']['version_bypass'] is True), 'Current same-session receiver semantics differ')

def observation(path, status):
    value = read(path)
    require(value.get('source') in ('user_message', 'user_gui') and isinstance(value.get('quote'), str) and value['quote'].strip() and (value.get('nonce') == status['nonce']), 'User observation provenance/current nonce required')
    when = parse_utc(value['observed_utc'])
    floor = max(parse_utc(status['created_utc']), parse_utc(status.get('updated_utc', status['created_utc'])))
    require(floor <= when <= datetime.now(timezone.utc), 'Observation predates the current lifecycle state or is future')
    return value

def package_scope_valid(plan):
    return (plan.get('patch_only') is True and plan.get('package') is None
            and plan.get('current_version') is None and plan.get('target_version') is None
            and plan.get('package_validation') == 'not_performed')

class Trial:

    def __init__(self, private=None, services=None):
        self.private = PRIVATE if private is None else Path(private)
        self.plan_path, self.status_path = (self.private / 'plan.json', self.private / 'status.json')
        self.services = services

    def rt(self):
        if self.services is None:
            self.services = runtime()
        return self.services

    def save(self, status, phase, **values):
        status.update(phase=phase, updated_utc=utc(), **values)
        atomic(self.status_path, status)

    def expected_sha(self):
        return read(self.plan_path)['receiver']['receiver_p1_sha256']

    def prove_preread(self, folder, *, unused=False):
        from integrity_backend import reader_integrity
        folder = under(folder, state_path(READER))
        meta = reader_integrity(folder, unused=unused)
        return dict(job=str(folder), nonce=meta['nonce'], job_sha256=sha(folder / 'job.json'), worker_sha256=meta['worker']['sha256'], bootstrap_sha256=meta['bootstrap']['sha256'])

    def prove_window(self, job, *, unused=False):
        job = under(job, state_path(WINDOW))
        require(not unused or not (job / 'claim.json').exists(), '菜单任务已使用')
        meta = self.rt().protocol.validate_job_integrity(job)[0]
        require(meta['hold_seconds'] == HOLD_SECONDS, '菜单窗口时长已改变')
        return meta

    def evidence_paths(self, plan):
        from user_provider import binding_path
        job = under(plan['job'], state_path(WINDOW))
        reader = under(plan['pre_window_reader']['job'], state_path(READER))
        return [job / name for name in ('job.json', 'worker.elf', 'libJit.so')] + [reader / name for name in ('job.json', 'worker.elf', 'libJit.so')] + [ROOT / 'app/release.json', binding_path()]

    def seal(self, job, pre_window_reader, *, card_file=None, patch_only=False):
        require(patch_only is True, '此软件只提供补丁与菜单准备')
        require(not self.plan_path.exists() and (not self.status_path.exists()), 'Preserve the existing plan and consumed task')
        job = under(job, state_path(WINDOW))
        rt = self.rt()
        meta = self.prove_window(job, unused=True)
        receiver = receiver_evidence()
        reader = self.prove_preread(pre_window_reader, unused=True)
        require(reader['nonce'] not in (receiver['accepted_reader_nonce'], meta['nonce']), 'Reader needs its own fresh nonce')
        require(type(patch_only) is bool and (not patch_only or card_file is None), 'Invalid patch-only scope')
        package = None if patch_only else verify_package(card_file, card=True) if card_file is not None else verify_package(DAT)
        provider = rt.Provider()
        provider.check()
        plan = dict(schema=PLAN_SCHEMA, created_utc=utc(), job=str(job), nonce=meta['nonce'], sources=source_pins(), receiver=receiver, pre_window_reader=reader, package=package, patch_only=patch_only, package_validation='not_performed' if patch_only else 'full_hash', hold_seconds=HOLD_SECONDS, current_version=None, target_version=None, p1_write_authorized=False, installation_by_user_only=True, automatic_retry=False)
        plan['hashes'] = {str(path): sha(path) for path in self.evidence_paths(plan)}
        atomic(self.plan_path, plan)
        return plan

    def validate(self, *, initial=False):
        plan = read(self.plan_path)
        require(plan['schema'] == PLAN_SCHEMA and plan['sources'] == source_pins() and package_scope_valid(plan) and (plan['receiver']['receiver_p1_sha256'] == self.expected_sha()) and (plan['hold_seconds'] == HOLD_SECONDS) and (plan['p1_write_authorized'] is False) and (plan['installation_by_user_only'] is True) and (plan['automatic_retry'] is False) and (plan['current_version'] is None), 'Corrected trial scope changed')
        verify_hash_set(self.evidence_paths(plan), plan['hashes'])
        require(receiver_evidence() == plan['receiver'], 'Historical receiver proof or required hash set changed')
        job = under(plan['job'], state_path(WINDOW))
        meta = self.prove_window(job, unused=initial)
        require(meta['nonce'] == plan['nonce'] and meta['hold_seconds'] == HOLD_SECONDS, 'Window identity changed')
        require(self.prove_preread(plan['pre_window_reader']['job'], unused=initial) == plan['pre_window_reader'], 'Same-session reader plan changed')
        if initial:
            require(not self.status_path.exists() and (not (job / 'claim.json').exists()), 'Trial already attempted; never resend START')
            if not plan.get('patch_only'):
                verify_package(plan['package']['path'], card=plan['package'].get('slot1_association') == 'user_confirmed')
        return (plan, meta)

    def read_current_receiver(self, session, plan, folder, status):
        """Read only, in the very session that will host the later RAM window."""
        reader = plan['pre_window_reader']
        require(self.prove_preread(reader['job'], unused=True) == reader, 'Fresh reader changed before upload')
        self.save(status, 'READING_CURRENT_RECEIVER', preread_started=True, preread_completed_safe=False)
        output = folder / 'execution/current_receiver'
        result = self.rt().live_reader.run_protocol(session, reader['job'], output)
        require(session.wire.healthy and result['verdict'] == 'P1_READBACK_VERIFIED', 'Current receiver read did not finish')
        hashes = verify_full_read(output, reader, expected_sha=result['sha256'])
        self.save(status, 'CURRENT_RECEIVER_READ_COMPLETE', preread_completed_safe=True, current_read_sha256=result['sha256'], current_read_evidence=hashes)
        require(result['sha256'] == self.expected_sha(), 'Receiver changed after restart; stop without a RAM window or p1 write')
        state = self.rt().adapter.inspect_bytes((output / 'nflasha1.bin').read_bytes())[0]
        receiver_semantics(state)
        atomic(folder / 'current_receiver_state.json', state)
        self.save(status, 'CURRENT_RECEIVER_VERIFIED', receiver_current_known=True, current_receiver_semantics=True)

    def status(self):
        plan, meta = self.validate()
        value = read(self.status_path)
        require(value['schema'] == STATUS_SCHEMA and value['nonce'] == plan['nonce'] and (value['plan_sha256'] == sha(self.plan_path)) and (value['runner_sha256'] == sha(__file__)), 'Consumed trial identity changed')
        return (plan, meta, value)

    def verified_terminal(self, evidence, meta, handoff=None):
        """A parsed summary alone is never a safe service-exit proof."""
        try:
            rt = self.rt()
            ready = rt.jobs.decode((Path(evidence) / 'ready.bin').read_bytes(), meta)
            row = rt.jobs.decode((Path(evidence) / 'result.bin').read_bytes(), meta)
            report = read(Path(evidence) / 'run.json')
            require(report['nonce'] == meta['nonce'] and report.get('native') == row, 'Terminal summary differs from native bytes')
            require(ready['phase'] == 1 and ready['error'] == 0 and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['flags'] == 13) and (ready['pid'] > 1) and (ready['loader_pid'] > 1) and (ready['pid'] != ready['loader_pid']), 'Terminal ready identity differs')
            require(rt.protocol.safe_terminal(dict(native=row, ready=ready)), 'Both targets are not safe')
            if row['flags'] & 512:
                require(row['target_addr'] == row['base_addr'] + meta['patch_offset'], 'Terminal updater address differs')
            if row['app_write_attempted']:
                require(row['app_target_addr'] == row['app_base_addr'] + meta['app_patch_offset'], 'Terminal app address differs')
            if handoff:
                require(ready == handoff['ready'] and all((row[k] == handoff['patched'][k] for k in ('app_pid', 'app_target_addr', 'app_base_addr', 'target_addr', 'base_addr'))), 'Terminal refers to another target process')
            return True
        except Exception:
            return False

    def execute(self, card_file=None, slot1_ready=False, stable_power=False, *, patch_only=False):
        require(patch_only is True, '此软件只提供补丁与菜单准备')
        require(type(patch_only) is bool and stable_power and (card_file is None if patch_only else slot1_ready and card_file is not None), 'Current power/scope readiness required before device actions')
        plan, meta = self.validate(initial=True)
        require(plan.get('patch_only', False) is patch_only, 'Sealed patch scope differs')
        card = None if patch_only else verify_package(card_file, card=True)
        require(patch_only or card['sha256'] == plan['package']['sha256'], 'Card package differs from sealed plan')
        folder = self.private / 'start'
        folder.mkdir(parents=True, exist_ok=False)
        if not patch_only:
            atomic(folder / 'card_receipt.json', card)
        status = dict(schema=STATUS_SCHEMA, nonce=meta['nonce'], created_utc=utc(), plan_sha256=sha(self.plan_path), runner_sha256=sha(__file__), phase='PREFLIGHT', restoration_verified=False, installation_may_be_running=False, installation_status='NOT_STARTED', firmware_written=False, DAT_installed=False, safe_to_restore=False, collection_allowed=False, camera_restarted=False, receiver_current_known=False, preread_started=False, preread_completed_safe=False, window_started=False, package_sha256=None if patch_only else DAT_SHA, package_validation='not_performed' if patch_only else 'full_hash', receiver_p1_sha256=self.expected_sha(), automatic_retry=False)
        self.save(status, 'PREFLIGHT')
        rt = self.rt()
        provider = rt.Provider()
        provider.check()
        provider.load_legacy()
        try:
            provider.preflight(folder)
            self.save(status, 'BINDING')
            provider.bind(folder)
        except BaseException as error:
            self.save(status, 'BINDING_UNCONFIRMED', error=str(error))
            raise
        handoff = None
        try:
            with provider.session(folder) as session:
                try:
                    session._select('/tmp/jiritsu/../../usr/lib/libupdaterufp.so')
                    library = session._read_selected(30000)
                    require(len(library) == meta['module_bytes'] and hashlib.sha256(library).hexdigest() == meta['module_sha256'], 'Current menu library differs')
                    (folder / 'execution/libupdaterufp.so').write_bytes(library)
                    for path in ('/tmp/jbusy', '/tmp/jiritsu/libJit.so'):
                        session._select('/tmp/jiritsu/../..' + path)
                        try:
                            session._read_selected(1)
                        except Exception as error:
                            require(getattr(error, 'status', None) == rt.protocol.base.MISSING_STATUS, 'Unknown prior-worker probe')
                        else:
                            raise ValueError('Previous module/busy state present; do not upload')
                    require(sha(self.plan_path) == status['plan_sha256'] and sha(__file__) == status['runner_sha256'], 'Controller/plan changed before upload')
                    current_plan, current_meta = self.validate()
                    require(current_plan == plan and current_meta == meta and session.wire.healthy, 'Live validated inputs differ')
                    require(not (Path(plan['job']) / 'claim.json').exists(), 'Window consumed before the current read')
                    self.read_current_receiver(session, plan, folder, status)
                    current_plan, current_meta = self.validate()
                    require(current_plan == plan and current_meta == meta and session.wire.healthy, 'Inputs changed during current read')
                    require(not (Path(plan['job']) / 'claim.json').exists(), 'Window consumed during the current read')
                    require(status.get('current_receiver_semantics') is True and status.get('current_read_sha256') == self.expected_sha(), 'No same-session full receiver proof')
                    self.save(status, 'STARTING_WINDOW', window_started=True, window_start_bound=stamp(), window_elapsed_floor=0)
                    handoff = rt.protocol.start_handoff(session, plan['job'], folder / 'execution/handoff')
                    self.save(status, 'HANDOFF_EXITING_SERVICE', handoff=handoff)
                except BaseException:
                    was_healthy = session.wire.healthy
                    provider.hold_session(session)
                    safe_reader_only = status.get('preread_completed_safe') is True and status.get('window_started') is False
                    if was_healthy and (safe_reader_only or self.verified_terminal(folder / 'execution/handoff', meta)):
                        session.wire.healthy = True
                        status['safe_to_restore'] = True
                    raise
        except BaseException as error:
            self.save(status, 'REVIEW_REQUIRED', session_error=str(error))
            if status['safe_to_restore']:
                self.restore(provider, folder, status)
            return status
        try:
            normal = provider.wait_for_normal(folder, timeout=30)
            seconds, elapsed = remaining(status)
        except Exception as error:
            normal, seconds, elapsed = (False, 0, HOLD_SECONDS)
            status['handoff_error'] = str(error)
        self.save(status, 'AWAITING_MENU_OBSERVATION' if normal and seconds >= 90 else 'HANDOFF_NOT_READY', normal_identity_seen=normal, window_elapsed_floor=elapsed, conservative_seconds_remaining=seconds, collection_allowed=False)
        emit(status['phase'], seconds_remaining=int(seconds), instruction='补丁与菜单准备完成；拔下USB后自行核对相机更新页和目标版本。' if status['phase'] == 'AWAITING_MENU_OBSERVATION' else '不要执行安装或重发任务；先记录本次菜单与是否重启。')
        return status





    def record_session_end(self, path):
        plan, _, status = self.status()
        require(plan.get('patch_only') is True and (status['phase'] in ACTIVE_PHASES or status['phase'] in ('WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL')), 'No patch-only session awaits restart confirmation')
        value = observation(path, status)
        require(value.get('restarted') is True and value.get('returned_to_shooting') is True and (value.get('update_active') is False), 'Confirm restart into an inactive shooting UI first')
        self.save(status, 'POST_RESTART_NORMAL_CHECK', restart_observation=value, camera_restarted=True, old_tmpfs_invalidated=True, collection_allowed=False, installation_may_be_running=False, receiver_current_known=False, installed_p1_state='NOT_READ_BACK_AFTER_RESTART', safe_to_restore=True, post_install_user_verified=False, installation_status='NOT_VERIFIED_BY_PATCH_TOOL', firmware_written=None, DAT_installed=None, ram_outcome='RESTART_REPORTED_NO_BYTEWISE_RESTORE_RECEIPT')
        return status


    def restore(self, provider, folder, status, confirmation=False):
        require(status.get('safe_to_restore') is True and status.get('installation_may_be_running') is False, 'No safe normal-recovery boundary')
        prior = status['phase']
        self.save(status, 'RESTORING_NORMAL_CONNECTION', recovery_folder=str(folder), recovery_from=prior)
        try:
            result = provider.restore(folder, confirmation=confirmation)
        except BaseException as error:
            self.save(status, 'RECOVERY_REVIEW_REQUIRED', recovery_error=str(error))
            raise
        require(result in ('VERIFIED', 'RESTART_REQUIRED', 'NORMAL_CONNECTION_PENDING'), 'Unknown restoration outcome')
        complete = 'INSTALL_USER_ACCEPTED_NORMAL_VERIFIED' if status.get('post_install_user_verified') else 'POST_RESTART_NORMAL_VERIFIED' if status.get('camera_restarted') else 'WINDOW_COMPLETE_NORMAL_VERIFIED'
        if status.get('window_started') is False and status.get('preread_completed_safe') is True:
            complete = 'PREREAD_REJECTED_NORMAL_VERIFIED'
        phase = {'VERIFIED': complete, 'RESTART_REQUIRED': 'WAITING_FOR_RESTART', 'NORMAL_CONNECTION_PENDING': 'WAITING_FOR_NORMAL'}[result]
        self.save(status, phase, normal_recovery=result, pending_restore_confirmation=result == 'RESTART_REQUIRED')
        return status

    def recover(self):
        _, _, status = self.status()
        require(status['phase'] in ('POST_RESTART_NORMAL_CHECK', 'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL') and status.get('safe_to_restore') is True and (status.get('installation_may_be_running') is False), 'No safe normal-recovery continuation')
        provider = self.rt().Provider()
        provider.check()
        confirmation = status['phase'] == 'WAITING_FOR_RESTART' or status.get('pending_restore_confirmation') is True
        folder = Path(status['recovery_folder']) if 'recovery_folder' in status else self.private / ('normal_' + uuid.uuid4().hex)
        folder.mkdir(exist_ok=True)
        return self.restore(provider, folder, status, confirmation)
