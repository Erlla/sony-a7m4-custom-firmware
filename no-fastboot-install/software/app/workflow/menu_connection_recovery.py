"""A completed p1 check and an unstarted menu need driver recovery, not a writer replay."""
from pathlib import Path
import integrity_backend as backend
import wizard as flow


def proof(value):
    if not value.get('flow'): return None
    if value.get('phase') not in ('REVIEW_REQUIRED', 'MENU_CONNECTION_RECOVERY', 'WINDOWS_RESTART_REQUIRED'):
        return None
    folder = flow.folder(value)
    if not (folder / 'status.json').exists() or not (folder / 'plan.json').exists(): return None
    status, plan = backend.read(folder / 'status.json'), backend.read(folder / 'plan.json')
    if not (status.get('stopped_before_session') is True and status.get('safe_to_restore') is True
            and status.get('window_started') is False and status.get('preread_started') is False
            and status.get('installation_may_be_running') is False): return None
    require = backend.require
    require(status['plan_sha256'] == backend.sha(folder / 'plan.json') and status['nonce'] == plan['nonce'], '菜单恢复记录与计划不一致')
    require(plan.get('patch_only') is True and not (folder / 'start/execution').exists(), '菜单会话已开始，不能按连接失败处理')
    require(not any((Path(path) / 'claim.json').exists() for path in (plan['job'], plan['pre_window_reader']['job'])), '菜单任务已有执行记录')
    controller = flow.trial(value)
    module = __import__(controller.__module__)
    relative = Path(module.__file__).relative_to(backend.ROOT).as_posix()
    require(status['runner_sha256'] == plan['sources'].get(relative), '菜单控制器来源不一致')
    patch = backend.frozen.Journal(backend.STATE).load()
    from p1_completion import complete
    require(complete(patch) and patch['run'] == value.get('patch_run'), '本轮 p1 检查尚未完成')
    evidence = module.receiver_evidence()
    return dict(source_run=patch['run'], p1_sha256=evidence['receiver_p1_sha256'], p1_verified=True,
                menu_session_started=False, window_started=False, firmware_operations=0)


def recover(value):
    evidence = proof(value)
    if evidence is None: return None
    from standalone_usb_restore import recover as standalone
    backend.atomic(flow.folder(value) / 'menu_connection_recovery.json', evidence)
    result = standalone()
    phase = 'MENU_CONNECTION_STOPPED' if result['phase'] == 'USB_RESTORE_COMPLETE' else (
        'WINDOWS_RESTART_REQUIRED' if result['phase'] == 'USB_RESTORE_WINDOWS_RESTART' else 'MENU_CONNECTION_RECOVERY')
    return flow.save(value, phase, usb_recovery=result['phase'], message=result.get('message'),
                     menu_connection_proof=evidence, final_unplug_ready=False)
