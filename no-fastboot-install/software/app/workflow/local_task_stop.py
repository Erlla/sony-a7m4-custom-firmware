"""Retire only an evidenced task-record failure before any device step."""
from datetime import datetime
from pathlib import Path
import integrity_backend as backend
import wizard as flow
from state_io import read_json, atomic_json


def _utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    backend.require(result.tzinfo is not None, '任务时间缺少时区')
    return result


def proof(value, journal):
    record = journal.load()
    if value.get('phase') != 'REVIEW_REQUIRED' or record is None:
        return None
    error = str(value.get('error', '')).replace('\\', '/')
    while '//' in error:
        error = error.replace('//', '/')
    signature = '/state/workflow/patch/control/' + record['run'] + '.json'
    if not (error.startswith(('[WinError 5]', '[WinError 32]', '[WinError 33]')) and signature in error):
        return None
    if record.get('phase') != 'PREPARING':
        return None
    require = backend.require
    require(value.get('patch_run') in (None, record['run']), '本地失败与补丁任务不匹配')
    require(value.get('purpose') == 'patch_and_menu_only' and value.get('package_validation') == 'not_performed', '流程范围不匹配')
    require(record['runner_sha256'] == backend.LOADED_SHA and record['outcome'] == 'NOT_STARTED', '任务来源或初始状态不匹配')
    require(record.get('firmware_written') is False and record.get('firmware_write_attempted') is False
            and record.get('read_verified') is False and record.get('session_ended') is False
            and record.get('normal_recovery_verified') is False, '记录含设备执行信息，不能按本地失败处理')
    require(not any(record.get(name) is not None for name in ('reader', 'after_reader', 'reader_result', 'source',
            'p1_sha256', 'preparation', 'writer_result', 'target_sha256', 'after_source')), '已有读取或写入材料，保持原恢复流程')
    require(_utc(value['created_utc']) <= _utc(record['created_utc']) <= _utc(value['updated_utc']), '任务不属于本轮失败时间范围')
    folder = journal.folder
    primary = folder / 'status.json'
    require(read_json(primary) == record, '任务记录副本不一致')
    events = [__import__('json').loads(line) for line in (folder / 'events.jsonl').read_text('utf-8-sig').splitlines() if line]
    require(events and events[-1] == record and all(row.get('run') == record['run'] and row.get('phase') == 'PREPARING'
            and row.get('firmware_written') is False and row.get('firmware_write_attempted') is False for row in events),
            '任务事件不能证明停在本地创建阶段')
    require(all(path.name in ('status.json', 'events.jsonl') or (path.is_file() and path.name.endswith('.tmp'))
                for path in folder.iterdir()), '任务目录已有其他执行材料')
    require(not any((flow.folder(value) / name).exists() for name in ('plan.json', 'status.json', 'start', 'execution')), '菜单已有执行记录')
    return dict(schema='m4-local-record-stop/1', run=record['run'], original=record,
                control_sha256=backend.sha(journal.private / 'control' / (record['run'] + '.json')),
                primary_sha256=backend.sha(primary), events_sha256=backend.sha(folder / 'events.jsonl'),
                device_operations=0, firmware_operations=0, driver_tasks_dispatched=0)


def reconcile(value):
    journal = backend.frozen.Journal(backend.STATE)
    evidence = proof(value, journal)
    if evidence is None:
        return None
    destination = flow.folder(value) / 'local_record_stop.json'
    backend.require(not destination.exists(), '本地失败已核对，请继续现有状态，不重复结案')
    atomic_json(destination, evidence)
    journal.update('STOPPED_BEFORE_DRIVER_CHANGE', outcome='LOCAL_JOURNAL_WRITE_FAILED',
                   error=value.get('error'), local_stop_proof=str(destination))
    return flow.save(value, 'CANCELLED_BEFORE_DEVICE', patch_run=evidence['run'], device_started=False,
                     stop_verified='STOPPED_BEFORE_DRIVER_CHANGE',
                     reconciliation=dict(kind='local_record_stop', proof=str(destination)),
                     previous_error=value.get('error'), error=None, firmware_written=False)
