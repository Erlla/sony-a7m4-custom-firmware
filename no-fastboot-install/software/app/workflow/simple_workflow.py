from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import json
import sys
import uuid
import integrity_backend as backend
import wizard as state
from user_provider import Provider, binding_path, enroll
CASE, ROOT = (backend.CASE, backend.ROOT)
read, sha, atomic, require = (backend.read, backend.sha, backend.atomic, backend.require)

def patch_receiver(value):
    require(value['phase'] == 'PATCH_PREPARED', '当前不是补丁准备步骤')
    require(value.get('package_validation') == 'not_performed', '旧流程请保留记录后处理')
    worker = backend.Backend('auto')
    prior = backend.frozen.Journal(backend.STATE).load()
    prior_run = prior.get('run') if prior else None
    state.save(value, 'PATCH_RUNNING', device_started=True)
    try:
        result = backend.frozen.Engine(worker, backend.STATE).read('apply')
        return state.sync_patch(value, result)
    except BaseException as error:
        stopped = safe_predriver_stop(prior_run)
        if not stopped:
            from rejected_read import pending
            rejection = pending(prior_run)
            if rejection:
                return state.save(value, 'PATCH_REJECTED_RECOVERY', error=str(error), patch_run=rejection['run'], rejection=rejection)
        state.save(value, 'CANCELLED_BEFORE_DEVICE' if stopped else 'REVIEW_REQUIRED', error=str(error), **dict(patch_run=stopped['run'], device_started=False, stop_verified='STOPPED_BEFORE_DRIVER_CHANGE') if stopped else {})
        raise

def safe_predriver_stop(prior_run):
    """Only a new, durably recorded pre-driver failure can unlock a fresh try."""
    try:
        record = backend.frozen.Journal(backend.STATE).load()
        if record and record['run'] != prior_run and (record['phase'] == 'STOPPED_BEFORE_DRIVER_CHANGE') and (record['runner_sha256'] == backend.LOADED_SHA) and (record.get('outcome') == 'LOCAL_OR_PREFLIGHT_FAILED') and (record.get('firmware_write_attempted') is False) and (record.get('firmware_written') is False) and (record.get('read_verified') is False) and (record.get('session_ended') is False):
            return record
    except Exception:
        pass
    return None

def open_menu(value):
    require(value['phase'] == 'PATCH_READY', '请先完成补丁与连接恢复')
    require(backend.frozen.Journal(backend.STATE).load()['run'] == value['patch_run'], '补丁任务已变更')
    controller = state.trial(value)
    runtime = controller.rt()
    state.save(value, 'MENU_PREPARING')
    try:
        job, _ = runtime.jobs.prepare()
        reader = runtime.reader_jobs.prepare()
        controller.seal(job, reader, patch_only=True)
        state.save(value, 'MENU_RUNNING')
        result = controller.execute(stable_power=True, patch_only=True)
        return state.save(value, result['phase'], window_nonce=result['nonce'], automatic_menu_preparation=True, final_unplug_ready=result['phase'] == 'AWAITING_MENU_OBSERVATION')
    except BaseException as error:
        local_only = value['phase'] == 'MENU_PREPARING' and not any(
            (state.folder(value) / name).exists() for name in ('plan.json', 'status.json', 'start', 'execution'))
        state.save(value, 'MENU_PREPARATION_RETRY' if local_only else 'REVIEW_REQUIRED',
                   error=str(error), menu_preparation_device_started=not local_only)
        raise

def advance_after_patch(value):
    return open_menu(value) if value['phase'] == 'PATCH_READY' else value

def begin(ready):
    from standalone_usb_restore import require_clear
    require_clear()
    prior = state.load()
    require(prior['phase'] in state.TERMINAL | {'NO_FLOW', 'PATCH_READY'}, '已有操作未完成，请继续本轮操作')
    require(ready is True, '请先确认相机已开机、USB 已连接和电量充足')
    if prior['phase'] == 'PATCH_READY':
        old = backend.frozen.Journal(backend.STATE).load()
        require(old and old['run'] == prior.get('patch_run') and (old['phase'] == 'COMPLETE') and (old.get('normal_recovery_verified') is True) and (old.get('read_verified') is True) and (old.get('session_ended') is True) and (not (state.folder(prior) / 'status.json').exists()), '上次补丁或菜单结果未确认，不能开始新一轮')
    for base in (backend.STATE, ROOT / 'state/maintenance', state_path(backend.STOCK)):
        old = backend.frozen.Journal(base).load()
        require(old is None or old['phase'] in backend.frozen.TERMINAL, '有尚未完成的相机操作，请保留记录并先处理')
    if prior['phase'] == 'PATCH_READY':
        state.save(prior, 'ABANDONED_BEFORE_MENU', reason='new_user_run', menu_window_started=False)
    value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, route='project', phase='PREPARING', current_version=None, target_version=None, created_utc=state.utc(), device_started=False, card_writes=0, user_confirmed_stable_power=True, package_validation='not_performed', purpose='patch_and_menu_only', card_reads=0, installation_by_user_only=True, automatic_retry=False, ui_version='1.00')
    state.folder(value).mkdir(parents=True, exist_ok=False)
    state.save(value, 'PREPARING')
    atomic(state.POINTER, dict(flow=value['flow']))
    try:
        if not binding_path().exists():
            print('首次使用：请确认 Windows 管理员授权窗口。', flush=True)
            enroll()
        provider = Provider()
        provider.check()
        state.save(value, 'PATCH_PREPARED')
    except Exception as error:
        state.save(value, 'CANCELLED_BEFORE_DEVICE', error=str(error))
        raise
    return advance_after_patch(patch_receiver(value))

def continue_flow(value):
    if value['phase'] == 'MENU_PREPARATION_RETRY':
        from menu_preparation_retry import prepare_retry
        return open_menu(prepare_retry(value))
    if value['phase'] == 'PATCH_REJECTED_RECOVERY':
        from rejected_read import recover
        result = recover(value['patch_run'])
        return state.save(value, 'READ_REJECTED_COMPLETE' if result['phase'] == 'COMPLETE' else 'PATCH_REJECTED_RECOVERY', recovery=result['phase'], firmware_written=False)
    if value['phase'] == 'PATCH_RECOVERY':
        result = backend.frozen.Engine(backend.Backend('auto'), backend.STATE).recover()
        return advance_after_patch(state.sync_patch(value, result))
    if value['phase'] == 'PATCH_PREPARED':
        return advance_after_patch(patch_receiver(value))
    if value['phase'] == 'PATCH_READY':
        return open_menu(value)
    require(value['phase'] in ('POST_RESTART_NORMAL_CHECK', 'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL'), '当前不能再次发送设备任务')
    result = state.trial(value).recover()
    complete = result['phase'] in ('POST_RESTART_NORMAL_VERIFIED', 'INSTALL_USER_ACCEPTED_NORMAL_VERIFIED')
    return state.save(value, 'COMPLETE' if complete else result['phase'], recovery_action='user_usb_replug', installation_result='not_verified_by_tool')

def installed(value, confirmed):
    require(confirmed and value['phase'] in ('AWAITING_MENU_OBSERVATION', 'WAITING_FOR_USER_INSTALL_RESULT'), '请先确认更新已结束、相机已重启进入拍摄界面')
    observation = state.observed(value, restarted=True, returned_to_shooting=True, update_active=False, quote='相机已结束更新并自动重启，或取消更新后正常重启；现为拍摄界面，未在更新中')
    result = state.trial(value).record_session_end(observation)
    return state.save(value, result['phase'])

def act(action, ready=False, confirmed=False):
    backend.release_check()
    sys.path.insert(0, str(backend.frozen.OLD_TOOL))
    from engine import single_instance
    with single_instance(state_path(backend.frozen.OLD_TOOL)):
        if action == 'start':
            return begin(ready)
        value = state.load()
        if action == 'status':
            return value
        if action == 'continue':
            return continue_flow(value)
        if action == 'recover-usb':
            from usb_recovery import recover
            return recover(value, confirmed=confirmed)
        if action == 'installed':
            return installed(value, confirmed)
        if action == 'failure':
            require(value['phase'] not in state.TERMINAL | {'NO_FLOW'}, '没有活动操作')
            return state.save(value, 'REVIEW_REQUIRED', failure_reported_by_user=True)
        raise ValueError('不支持的操作')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'continue', 'installed', 'failure', 'status', 'recover-usb'))
    parser.add_argument('--ready', action='store_true')
    parser.add_argument('--confirmed', action='store_true')
    value = act(**vars(parser.parse_args()))
    print(json.dumps({**value, 'schema': 'm4-user-flow/1', 'passed': value.get('passed', value['phase'] != 'REVIEW_REQUIRED')}, ensure_ascii=False, indent=2), flush=True)
if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('操作已停止：' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
