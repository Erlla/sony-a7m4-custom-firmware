from product_integrity import pinned, state_path
from pathlib import Path
import json
import uuid
import integrity_backend as backend
import wizard as flow
CASE, ROOT = backend.CASE, backend.ROOT
require, read, sha, atomic = (backend.require, backend.read, backend.sha, backend.atomic)

def terminal_native(record, worker, run):
    require(record.get('phase') == 'REVIEW_REQUIRED' and record.get('error') == 'Native worker rejected before expected result' and (record.get('firmware_write_attempted') is True) and (record.get('read_verified') is True), '写入结果尚未证明已结束，不能切换驱动')
    preparation = record['preparation']
    require(preparation['lineage'] in ('stock', 'user') and worker.lineage == preparation['lineage'], '更新器类型不一致')
    job = Path(preparation['writer_job'])
    meta = worker.jobs().validate(job)
    raw = (run / 'execution/writer/result.bin').read_bytes()
    native = worker.jobs().decode(raw, meta)
    saved = read(run / 'execution/writer/run.json')
    target = preparation['target_sha256']
    require(saved.get('native') == native and saved.get('outcome') == 'COMMIT_OUTCOME_UNKNOWN' and (native['phase'] == 6) and (native['error'] == 0) and (native['flags'] == 255) and (native['rollback'] == 0) and (native['io_status'] == 0) and (native['write_calls'] == len(meta['windows'])) and (native['before_sha256'] == record['p1_sha256']) and (native['after_sha256'] == target) and (sha(record['source']) == record['p1_sha256']) and (sha(job / 'image/p1_apply.bin') == target), '原生结果与保存的完整镜像不一致，不能恢复驱动')
    return target

def prior_read_proof(target, run):
    matches = []
    for path in (ROOT / 'state/workflow').glob('read_only_recovery_*/reconciliation.json'):
        try:
            proof = read(path)
            binding = read(path.parent / 'source_run.json')
            if proof.get('passed') is True and proof.get('actual_sha256') == target and (proof.get('expected_sha256') == target) and (binding.get('source_run') == run) and (binding.get('target_sha256') == target) and (binding.get('proof_sha256') == sha(path)) and (Path(proof['output']).resolve() == path.parent.resolve()) and (sha(path.parent / 'execution/before/nflasha1.bin') == target):
                matches.append(path.parent)
        except (OSError, ValueError, KeyError):
            continue
    require(len(matches) <= 1, '找到多个回读记录，需要人工核对')
    return matches[0] if matches else None

def fresh_read(worker, target, value, run):
    pointer = flow.folder(value) / 'usb_recovery.json'
    require(not pointer.exists(), '回读或恢复已启动，请保留记录，不能重复发送任务')
    folder = ROOT / 'state/workflow' / ('usb_recovery_' + uuid.uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    atomic(pointer, dict(folder=str(folder), source_run=run, state='READ_STARTED', automatic_retry=False))
    reader = worker.prepare_reader(folder, 'before')
    print('正在独立完整回读 p1；不会再次写入补丁。', flush=True)
    with worker.provider.session(folder) as session:
        source, result = worker.run_reader(session, reader, folder)
    require(result['verdict'] == 'P1_READBACK_VERIFIED' and result['sha256'] == target and (sha(source) == target) and (result['bytes'] == 25100288) and (result['chunks'] == 766) and (result['firmware_written'] is False) and (result['ram_chunks_cleaned'] is True), '独立完整回读与目标不一致，保持当前驱动供人工核对')
    atomic(folder / 'reconciliation.json', dict(passed=True, source_run=run, actual_sha256=target, expected_sha256=target, output=str(folder), read_result=result))
    atomic(pointer, dict(folder=str(folder), source_run=run, state='READ_VERIFIED', automatic_retry=False))
    return folder

def read_folder(worker, target, value, run):
    pointer = flow.folder(value) / 'usb_recovery.json'
    if pointer.exists():
        saved = read(pointer)
        require(saved.get('source_run', run) == run, '恢复记录属于其他任务')
        require(saved['state'] in ('READ_VERIFIED', 'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART', 'RESTORE_DISPATCHED'), '上次回读结果未确认，不能重试')
        folder = Path(saved['folder']).resolve()
        require(folder.is_relative_to((ROOT / 'state/workflow').resolve()), '恢复记录路径无效')
    else:
        folder = prior_read_proof(target, run)
        if folder is None:
            folder = fresh_read(worker, target, value, run)
        else:
            atomic(pointer, dict(folder=str(folder), source_run=run, state='READ_VERIFIED', automatic_retry=False))
    proof = read(folder / 'reconciliation.json')
    require(proof.get('passed') is True and proof['actual_sha256'] == target and (proof['expected_sha256'] == target) and (sha(folder / 'execution/before/nflasha1.bin') == target), '独立回读记录不完整或文件已改变')
    if 'source_run' not in proof:
        binding = read(folder / 'source_run.json')
        require(binding['source_run'] == run and binding['target_sha256'] == target and (binding['proof_sha256'] == sha(folder / 'reconciliation.json')), '回读与本轮任务未绑定')
    else:
        require(proof['source_run'] == run, '回读属于其他任务')
    return (folder, pointer, proof)

def restore_driver(worker, folder, pointer):
    provider = worker.provider
    intent = folder / 'driver_restore_intent.json'
    if intent.exists():
        if not provider.normal_ready(folder):
            return 'WAITING_FOR_RESTART'
        result = provider.restore(folder, confirmation=True)
        require(result == 'VERIFIED', '普通 USB 确认未完成')
        return 'VERIFIED'
    _, snapshot = provider.snapshot(folder)
    if snapshot['normal_count'] == 0 and snapshot['service_count'] in (0, 1):
        atomic(pointer, dict(folder=str(folder), state='WAITING_FOR_NORMAL', automatic_retry=False))
        return 'WAITING_FOR_NORMAL'
    row = provider.same_body(snapshot)
    if row['service'] == 'USBSTOR' and provider.normal_ready(folder):
        return 'VERIFIED'
    require(row['service'] == 'WinUSB' and snapshot['service_count'] == 0, '当前不是已识别的待恢复 USB 驱动状态')
    atomic(intent, dict(scope='driver_only', automatic_retry=False))
    atomic(pointer, dict(folder=str(folder), state='RESTORE_DISPATCHED', automatic_retry=False))
    result = provider.restore(folder)
    require(result in ('VERIFIED', 'NORMAL_CONNECTION_PENDING', 'RESTART_REQUIRED'), '驱动恢复结果不明')
    return 'VERIFIED' if result == 'VERIFIED' else 'WAITING_FOR_NORMAL' if result == 'NORMAL_CONNECTION_PENDING' else 'WAITING_FOR_RESTART'

def recover_write_race(value):
    journal = backend.frozen.Journal(backend.STATE)
    record = journal.load()
    require(record is not None, '没有补丁任务记录')
    require(isinstance(record.get('preparation'), dict) and record['preparation'].get('lineage') in ('stock', 'user'), '没有可核对的写入材料，不能切换驱动')
    lineage = record['preparation']['lineage']
    worker = backend.Backend(lineage)
    worker.check()
    target = terminal_native(record, worker, journal.folder)
    if not (flow.folder(value) / 'usb_recovery.json').exists() and prior_read_proof(target, record['run']) is None:
        _, snapshot = worker.provider.snapshot(journal.folder)
        if snapshot['normal_count'] == 0 and snapshot['service_count'] in (0, 1):
            return flow.save(value, 'USB_RECOVERY_WAITING', usb_recovery='WAITING_FOR_NORMAL', patch_run=record['run'])
        worker.provider.same_body(snapshot)
        require(snapshot['service_count'] == 0, '相机仍在服务模式，暂不能启动独立回读')
    folder, pointer, proof = read_folder(worker, target, value, record['run'])
    result = restore_driver(worker, folder, pointer)
    if result != 'VERIFIED':
        atomic(pointer, dict(folder=str(folder), source_run=record['run'], state=result, automatic_retry=False))
        return flow.save(value, 'USB_RECOVERY_WAITING', usb_recovery=result, patch_run=record['run'], recovery_folder=str(folder))
    atomic(pointer, dict(folder=str(folder), source_run=record['run'], state='COMPLETE', automatic_retry=False))
    journal.update('COMPLETE', outcome='PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED_AFTER_RECOVERY', firmware_written=True, session_ended=True, normal_recovery_verified=True, target_sha256=target, p1_sha256=target, after_source=str(folder / 'execution/before/nflasha1.bin'), reconciliation=dict(native_terminal_verified=True, independent_full_read_sha256=target, recovery_folder=str(folder), writer_host_windows_completed=False))
    return flow.save(value, 'PATCH_READY', patch_run=record['run'], updater_lineage=lineage, menu_profile='content_' + lineage, usb_recovery='VERIFIED', recovery_folder=str(folder), error=None)

def recover(value, confirmed=False):
    if value['phase'] in ('POST_RESTART_NORMAL_CHECK', 'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL'):
        from simple_workflow import continue_flow
        return continue_flow(value)
    if value['phase'] in ('AWAITING_MENU_OBSERVATION', 'WAITING_FOR_USER_INSTALL_RESULT'):
        from simple_workflow import installed
        return installed(value, confirmed)
    if value['phase'] in flow.TERMINAL | {'NO_FLOW', 'PATCH_READY', 'PATCH_PREPARED', 'MENU_PREPARATION_RETRY'}:
        for base in (backend.STATE, ROOT / 'state/maintenance', ROOT / 'state/maintenance_custom',
                     state_path(backend.STOCK), state_path(backend.USER)):
            prior = backend.frozen.Journal(base).load()
            require(prior is None or prior['phase'] in backend.frozen.TERMINAL,
                    '存在未完成的相机读写，请保留记录并按原任务恢复，不能直接切换驱动')
        if value['phase'] in ('PATCH_READY', 'PATCH_PREPARED', 'MENU_PREPARATION_RETRY'):
            require(not (flow.folder(value) / 'status.json').exists(), '菜单任务已启动，请先确认更新结果')
        from standalone_usb_restore import recover as standalone
        return standalone()
    if value['phase'] == 'PATCH_REJECTED_RECOVERY':
        from rejected_read import recover as rejected_recover
        result = rejected_recover(value['patch_run'])
        return flow.save(value, 'READ_REJECTED_COMPLETE' if result['phase'] == 'COMPLETE' else 'PATCH_REJECTED_RECOVERY', recovery=result['phase'])
    if value['phase'] == 'PATCH_RECOVERY':
        result = backend.frozen.Engine(backend.Backend('auto'), backend.STATE).recover()
        return flow.sync_patch(value, result)
    require(value['phase'] in ('REVIEW_REQUIRED', 'USB_RECOVERY_WAITING'), '当前没有需要恢复的 USB 任务')
    return recover_write_race(value)
