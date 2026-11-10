"""User guidance is state driven; it is never a hardware authorization receipt."""
from datetime import datetime, timezone
import math
import time

PREPARE = ('请自行将适用的 BODYDATA.DAT 放入卡槽 1 根目录，将相机以 USB 海量存储模式连接。'
           '保持电量充足和供电稳定。本工具将完整备份 p1、检查兼容性、按需写入补丁并独立回读，'
           '随后准备更新菜单；不会安装 DAT。开始后请手动确认 Windows 的管理员或驱动证书授权。是否确认开始？')


def remaining(bound, now=None):
    if not bound: return 0
    try:
        mono, wall = now or (time.monotonic(), datetime.now(timezone.utc))
        elapsed_mono = mono - bound['monotonic']
        elapsed_wall = (wall - datetime.fromisoformat(bound['utc'])).total_seconds()
        if not all(math.isfinite(v) and v >= 0 for v in (elapsed_mono, elapsed_wall)): return 0
        if abs(elapsed_mono - elapsed_wall) > 5: return 0
        return max(0, int(600 - max(elapsed_mono, elapsed_wall)))
    except (ValueError, TypeError, KeyError): return 0


def next_request(flow):
    """Return (kind, human instruction, allowed reply codes) for a stopped worker."""
    phase = flow.get('phase', 'REVIEW_REQUIRED')
    if phase == 'AWAITING_MENU_OBSERVATION' and flow.get('final_unplug_ready') is True:
        return ('menu', '可以拔下 USB。保持相机开机，回到拍摄界面，再进入版本／软件更新，先停在确认页。'
                '请回复当前版本、目标版本，以及是否能进入确认页；现在先不要执行安装。', ['menu-confirmed', 'menu-unavailable'])
    if phase in ('WINDOWS_RESTART_REQUIRED', 'USB_RESTORE_WINDOWS_RESTART') or flow.get('recovery') == 'WINDOWS_RESTART_REQUIRED':
        return ('windows-restart', '请保存电脑工作并真正重启 Windows，再用原工具目录查询此任务。'
                '重开软件、重启相机或插拔 USB 不能替代电脑重启。重启后回复已重启 Windows。', ['windows-restarted'])
    if phase == 'HANDOFF_NOT_READY':
        return ('camera-restart', '菜单尚未交接，请不要开始安装。若相机没有正在更新，正常关机，'
                '待存取灯熄灭再开机，并重新连接 USB；回复已重启、已回到拍摄界面且没有更新进行中。', ['camera-restarted'])
    if phase in ('PATCH_RECOVERY', 'PATCH_REJECTED_RECOVERY', 'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART',
                 'POST_RESTART_NORMAL_CHECK', 'USB_RECOVERY_WAITING', 'USB_RESTORE_WAITING', 'USB_RESTORE_REPLUG'):
        return ('replug', '本轮当前步骤已停止，请保持相机开机，重新插拔 USB 后回复已重新连接。'
                '只继续核对原任务，暂时不要安装固件。', ['usb-replugged'])
    if phase in ('PATCH_READY', 'MENU_PREPARATION_RETRY', 'MENU_CONTINUATION_READY'):
        return ('continue-menu', '补丁检查已完成，菜单尚未准备完成。请确认电量和 USB 稳定，回复继续准备菜单。', ['continue-menu'])
    if phase in ('MENU_CONNECTION_STOPPED', 'MENU_CONNECTION_RECOVERY'):
        return ('restore', 'p1 已完成，菜单尚未启动。请确认相机没有正在安装固件，连接 USB，回复恢复并继续菜单准备。'
                '先核对普通连接，再提供原任务的菜单继续待办；不会重新写入 p1。', ['restore-usb'])
    if phase in ('CONNECTION_STOPPED', 'CANCELLED_BEFORE_DEVICE',
                 'READ_REJECTED_COMPLETE', 'NO_FLOW', 'USB_RESTORE_CANCELLED', 'USB_RESTORE_RETRY'):
        return ('restore', '当前操作已停止。请确认相机没有正在安装固件，连接 USB，回复恢复普通 USB。'
                '此操作只走原任务的恢复核对，不重新写入补丁。', ['restore-usb'])
    return None


def request_action(request, answer, flow):
    kind = request['kind']
    if kind == 'write' and answer == 'approve-write': return ('start', False)
    if kind == 'restore' and answer == 'restore-usb': return ('recover-usb', False)
    if kind == 'windows-restart': return ('recover-usb', False)
    if kind == 'camera-restart': return ('recover-usb', True)
    if kind == 'replug':
        return ('continue', False) if flow.get('phase') in ('PATCH_RECOVERY', 'PATCH_REJECTED_RECOVERY') else ('recover-usb', False)
    if kind == 'continue-menu': return ('continue', False)
    if kind == 'install-result' and answer in ('installed-ok', 'cancelled-restarted'): return ('installed', True)
    if kind == 'menu' and answer == 'menu-confirmed': return ('menu-confirmed', False)
    if kind == 'menu' and answer == 'menu-unavailable': return ('menu-unavailable', False)
    if kind == 'install-result' and answer == 'install-failed': return ('install-failed', False)
    if kind == 'failed-install' and answer == 'ended-restarted': return ('recover-usb', True)
    if kind == 'expired-menu' and answer == 'ended-restarted': return ('recover-usb', True)
    if kind == 'expired-menu' and answer == 'installed-ok': return ('installed', True)
    raise ValueError('回复不适用于当前步骤')
