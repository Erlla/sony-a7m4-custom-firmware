from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
import integrity_backend as backend
CASE, ROOT = (backend.CASE, backend.ROOT)
PRIVATE = ROOT / 'state/workflow'
POINTER = PRIVATE / 'flow.json'
TERMINAL = {'COMPLETE', 'CANCELLED_BEFORE_DEVICE', 'READ_REJECTED_COMPLETE', 'ABANDONED_BEFORE_MENU'}
sha, read, atomic, require = (backend.sha, backend.read, backend.atomic, backend.require)

def utc():
    return datetime.now(timezone.utc).isoformat()

def load():
    if not POINTER.exists():
        require(not (PRIVATE / 'flows').exists() or not any((PRIVATE / 'flows').iterdir()), '流程索引缺失，请保留记录并检查')
        return dict(phase='NO_FLOW')
    name = read(POINTER)['flow']
    require(re.fullmatch('[0-9a-f]{32}', name), '流程编号不正确')
    value = read(PRIVATE / 'flows' / name / 'flow.json')
    require(value['schema'] == 'm4-user-flow/1' and value['flow'] == name, '流程记录不一致')
    return value

def folder(value):
    require(re.fullmatch('[0-9a-f]{32}', value['flow']), '流程编号不正确')
    return PRIVATE / 'flows' / value['flow']

def save(value, phase, **fields):
    value.update(phase=phase, updated_utc=utc(), **fields)
    atomic(folder(value) / 'flow.json', value)
    return value

def trial(value):
    lineage = value.get('updater_lineage', 'stock')
    require(lineage in ('stock', 'user'), '未确认更新器类型，不能准备菜单')
    if lineage == 'user':
        import install_controller_custom as controller
    else:
        import install_controller as controller
    return controller.Trial(folder(value))

def sync_patch(value, result):
    lineage = (result.get('preparation') or {}).get('lineage')
    if lineage is not None:
        require(lineage in ('stock', 'user'), '补丁结果的更新器类型无效')
        value.update(updater_lineage=lineage, menu_profile='content_' + lineage, expected_menu_version=None, version_policy='consistent_runtime_encodings')
    if result['phase'] == 'COMPLETE':
        return save(value, 'PATCH_READY', patch_run=result['run'])
    if result['phase'] in backend.frozen.RECOVERABLE:
        return save(value, 'PATCH_RECOVERY', patch_run=result['run'], recovery=result['phase'])
    return save(value, 'REVIEW_REQUIRED', patch_run=result['run'])

def observed(value, **fields):
    controller = trial(value)
    state = read(controller.status_path)
    report = dict(source='user_gui', quote=fields.pop('quote'), nonce=state['nonce'], observed_utc=utc(), **fields)
    path = folder(value) / ('observation_' + uuid.uuid4().hex + '.json')
    atomic(path, report)
    return path

def act(action, **unused):
    backend.release_check()
    sys.path.insert(0, str(backend.frozen.OLD_TOOL))
    from engine import single_instance
    with single_instance(state_path(backend.frozen.OLD_TOOL)):
        if action == 'setup':
            require(load()['phase'] in TERMINAL | {'NO_FLOW'}, '有未完成流程，不能重新初始化')
            from user_provider import enroll
            return dict(schema='m4-user-flow/1', phase='SETUP_COMPLETE', **enroll())
        if action == 'status':
            return load()
        raise ValueError('不支持的操作')
