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
    prior = flow.menu_folder(value)
    attempt = uuid.uuid4().hex
    destination = flow.folder(value) / 'menu_attempts' / attempt
    destination.mkdir(parents=True, exist_ok=False)
    backend.atomic(destination / 'continuation.json', dict(schema='m4-menu-continuation/1',
        previous_attempt=str(prior), patch_run=value['patch_run'], proof=evidence,
        p1_write_authorized=False, automatic_retry=False))
    return flow.save(value, 'PATCH_READY', menu_attempt=attempt,
                     previous_menu_error=value.get('error'), error=None, diagnostic=None,
                     final_unplug_ready=False, p1_rewrite_required=False)
