"""Start a fresh menu attempt after a proven pre-session stop; never a p1 writer."""
import uuid
import integrity_backend as backend
import wizard as flow
from menu_connection_recovery import proof


def prepare(value):
    backend.require(value.get('phase') == 'MENU_CONTINUATION_READY'
                    and value.get('normal_usb_restored') is True, '请先核对普通 USB 恢复结果')
    evidence = proof(value)
    backend.require(evidence is not None, '菜单会话结束证据不完整，不能重新准备')
    return fresh_attempt(value, evidence, 'normal_usb_restored')


def recheck(value):
    """Explicit user continuation: observe the same body, without driver changes."""
    backend.require(value.get('phase') == 'MENU_CONNECTION_STOPPED', '当前不是菜单连接检查')
    evidence = proof(value)
    backend.require(evidence is not None, '菜单会话结束证据不完整，请按原任务恢复，不重新写入')
    from user_provider import Provider
    from driver_restart import require_ready
    from diagnostics import describe
    provider = Provider()
    try:
        require_ready()
        provider.check()
        current = provider.wait_communication(flow.menu_folder(value), timeout=30)
        if current is None:
            return flow.save(value, 'MENU_CONNECTION_STOPPED', error=None,
                message='普通通信身份尚未返回。请保持相机开机，按提示重新连接；仍异常时使用恢复普通 USB。',
                diagnostic=dict(code='MENU_COMMUNICATION_PENDING', stage='PREFLIGHT',
                    message='等待 30 秒后，仍未检测到唯一的普通 USB 相机身份。',
                    next_step='检查连接后继续菜单准备，或使用恢复普通 USB；本次未发送相机命令。'),
                final_unplug_ready=False)
        snapshot, state = current
        provider.tasks_clear(snapshot)
        driver = provider.communication_driver(provider.same_body(state))
    except Exception as error:
        flow.save(value, 'WINDOWS_RESTART_REQUIRED' if getattr(error, 'reason', None) == 'WINDOWS_RESTART_REQUIRED' else 'MENU_CONNECTION_STOPPED',
                  error=str(error), diagnostic=describe(error, 'PREFLIGHT'), final_unplug_ready=False)
        raise
    return fresh_attempt(value, evidence, driver)


def fresh_attempt(value, evidence, connection):
    prior = flow.menu_folder(value)
    attempt = uuid.uuid4().hex
    destination = flow.folder(value) / 'menu_attempts' / attempt
    destination.mkdir(parents=True, exist_ok=False)
    backend.atomic(destination / 'continuation.json', dict(schema='m4-menu-continuation/1',
        previous_attempt=str(prior), patch_run=value['patch_run'], proof=evidence,
        p1_write_authorized=False, automatic_retry=False, connection=connection))
    return flow.save(value, 'PATCH_READY', menu_attempt=attempt,
                     previous_menu_error=value.get('error'), error=None, diagnostic=None,
                     final_unplug_ready=False, p1_rewrite_required=False)
