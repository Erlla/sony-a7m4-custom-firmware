"""Resume a proven local menu-preparation failure without another p1 write."""
from pathlib import Path
import json
import integrity_backend as backend
import wizard as flow
from local_json import atomic


def eligible(value):
    phase = value.get('phase')
    legacy = str(value.get('error', '')).replace('\\', '/')
    while '//' in legacy:
        legacy = legacy.replace('//', '/')
    known_legacy = (phase == 'REVIEW_REQUIRED' and legacy.startswith('[Errno 2]')
                    and '/app/provider/release.json' in legacy)
    backend.require(phase == 'MENU_PREPARATION_RETRY' or known_legacy,
                    '不是已确认的本地菜单准备失败，请保留原任务记录')
    folder = flow.folder(value)
    backend.require(not any((folder / name).exists() for name in ('plan.json', 'status.json', 'start', 'execution')),
                    '已有菜单计划或设备执行记录，不能重新准备')
    backend.require(value.get('package_validation') == 'not_performed'
                    and value.get('purpose') == 'patch_and_menu_only', '流程范围不匹配')
    lineage = value.get('updater_lineage')
    backend.require(lineage in ('stock', 'user'), '补丁路线尚未确认')
    if lineage == 'user':
        import install_controller_custom as controller
    else:
        import install_controller as controller
    proof = controller.receiver_evidence()
    backend.require(proof['accepted_run'] == value.get('patch_run'), '完整补丁证据属于其他任务')
    return proof


def mark_retry(value):
    """Migration for the old missing-manifest failure; local evidence only."""
    proof = eligible(value)
    path = flow.folder(value) / 'menu_retry_evidence.json'
    if not path.exists():
        atomic(path, dict(schema='m4-local-menu-retry/1', before=value.copy(), proof=proof,
                          firmware_operations=0, menu_started=False, automatic_retry=False))
    return flow.save(value, 'MENU_PREPARATION_RETRY', menu_preparation_device_started=False,
                     retry_evidence=str(path), previous_menu_error=value.get('error'))


def prepare_retry(value):
    proof = eligible(value)
    return flow.save(value, 'PATCH_READY', accepted_patch_run=proof['accepted_run'],
                     previous_menu_error=value.get('previous_menu_error', value.get('error')),
                     error=None, p1_rewrite_required=False)
