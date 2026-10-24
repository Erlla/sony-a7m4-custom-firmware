from product_integrity import pinned, state_path
from pathlib import Path
import integrity_backend as b
REJECTED_ERRORS = {'Unknown updater library', '当前完整更新器不属于已审查的官方或项目固件'}
PREVIOUS_RUNNER = '2676f72a3278eee1484fee7b7cefee2cf89d35ce745645b6178d3560c3d0e72d'
OUTCOME = 'READ_ONLY_REJECTION_NORMAL_RECOVERED'

def proof(record, private=None):
    private = b.STATE if private is None else Path(private)
    b.require(record and record.get('error') in REJECTED_ERRORS and (record.get('runner_sha256') in (b.LOADED_SHA, PREVIOUS_RUNNER)) and (record.get('read_verified') is True) and (record.get('firmware_write_attempted') is False) and (record.get('firmware_written') is False) and (not record.get('preparation')) and (not record.get('writer_result')) and (not record.get('target_sha256')), '不是已完成读取后的写前兼容性拒绝，请保留记录')
    run = b.frozen.local_path(private / 'runs', record['run'])
    source = run / 'execution/before/nflasha1.bin'
    reader, result = (record['reader'], record['reader_result'])
    b.require(Path(record['source']).resolve() == source.resolve() and result.get('verdict') == 'P1_READBACK_VERIFIED' and (result.get('nonce') == reader['nonce']) and (result.get('bytes') == 25100288) and (result.get('chunks') == 766) and (result.get('module_uploads') == result.get('start_attempts') == result.get('ack_attempts') == 1) and (result.get('block_writes') is False) and (result.get('firmware_written') is False) and (result.get('ram_chunks_cleaned') is True) and (not (run / 'execution/writer').exists()) and (not (Path(record['after_reader']['job']) / 'claim.json').exists()), '写前读取和清理证据不完整')
    b.require(b.sha(b.frozen.FULL_READ_VERIFIER) == b.frozen.FULL_READ_VERIFIER_SHA, '读取验证器发生变化')
    verifier = b.frozen.load_module('m4_rejected_read_verifier', b.frozen.FULL_READ_VERIFIER)
    evidence = verifier.verify_full_read(source.parent, reader, expected_sha=record['p1_sha256'])
    saved = b.read(run / 'before_full_read_verification.json')
    b.require(saved.get('passed') is True and saved.get('evidence') == evidence and (saved.get('nonce') == reader['nonce']) and (saved.get('p1_sha256') == record['p1_sha256']), '完整读取的独立验证记录不一致')
    return dict(run=record['run'], p1_sha256=record['p1_sha256'], reader_nonce=reader['nonce'], error=record['error'], evidence=evidence, firmware_write_attempted=False)

def pending(prior_run):
    try:
        record = b.frozen.Journal(b.STATE).load()
        if record and record['run'] != prior_run and (record['phase'] == 'REVIEW_REQUIRED'):
            return proof(record)
    except Exception:
        pass
    return None

def recover(run):
    b.release_check()
    journal = b.frozen.Journal(b.STATE)
    record = journal.load()
    b.require(record and record['run'] == run, '待恢复读取任务已改变')
    evidence = proof(record)
    b.require(record['phase'] in ('REVIEW_REQUIRED', 'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART', 'COMPLETE'), '恢复任务结果不明，禁止重复调度')
    if record['phase'] == 'COMPLETE':
        b.require(record.get('outcome') == OUTCOME and record.get('normal_recovery_verified') is True, '已完成任务不是本次拒绝后的恢复')
        return record
    if record['phase'] != 'REVIEW_REQUIRED':
        b.require(record.get('rejected_read_proof') == evidence, '恢复证据发生变化')
    else:
        b.require(record.get('outcome') == 'READ_OR_SESSION_OUTCOME_REQUIRES_REVIEW', '不明恢复状态')
    from user_provider import Provider
    provider = Provider()
    provider.check()
    _, snapshot = provider.snapshot(journal.folder)
    if snapshot['normal_count'] == 0 and snapshot['service_count'] in (0, 1):
        if record['phase'] != 'WAITING_FOR_RESTART':
            journal.update('WAITING_FOR_NORMAL', rejected_read_proof=evidence, outcome='READ_REJECTED_NO_WRITE_WAITING_FOR_REPLUG')
        return journal.value
    provider.same_body(snapshot)
    b.require(snapshot['normal_count'] == 1 and snapshot['service_count'] == 0, '请先重新插拔 USB，确认相机退出服务模式')
    confirmation = record['phase'] == 'WAITING_FOR_RESTART'
    if confirmation and (not provider.normal_ready(journal.folder)):
        return record
    journal.update('RECOVERY_DISPATCHING', rejected_read_proof=evidence, normal_mode_seen_after_rejection=True)
    result = provider.restore(journal.folder, confirmation=confirmation)
    b.require(result in ('VERIFIED', 'NORMAL_CONNECTION_PENDING', 'RESTART_REQUIRED'), '未知恢复结果')
    if result == 'VERIFIED':
        journal.update('COMPLETE', session_ended=True, normal_recovery_verified=True, outcome=OUTCOME, recovery_runner_sha256=b.LOADED_SHA)
    else:
        journal.update('WAITING_FOR_RESTART' if result == 'RESTART_REQUIRED' else 'WAITING_FOR_NORMAL', normal_recovery=result, outcome='READ_REJECTED_NO_WRITE_WAITING_FOR_REPLUG')
    return journal.value
