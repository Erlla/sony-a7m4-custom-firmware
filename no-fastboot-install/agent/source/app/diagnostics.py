"""Display/log diagnostics only. Never authorizes a retry or device operation."""
import errno
import json
import subprocess
import traceback

STAGES = {
    'PREPARING': '准备工具', 'PREFLIGHT': '检查连接', 'BINDING': '切换 USB 驱动',
    'BOUND': '建立相机服务会话', 'READ_STARTING': '备份 p1',
    'PATCH_PREPARING': '生成补丁', 'WRITE_STARTING': '写入 p1',
    'WRITE_VERIFIED': '写入后收尾', 'READBACK_STARTING': '独立回读 p1',
    'MENU_PREPARING': '准备菜单材料', 'MENU_RUNNING': '准备相机菜单',
    'PREREAD_STARTING': '菜单前读取 p1', 'STARTING_WINDOW': '启动菜单窗口',
    'HANDOFF_EXITING_SERVICE': '退出服务模式', 'HANDOFF_NOT_READY': '交接更新菜单',
    'READING_CURRENT_RECEIVER': '菜单前读取 p1', 'PATCH_RUNNING': '补丁检查',
    'RECOVERY_DISPATCHING': '恢复普通 USB', 'USB_RESTORE': '恢复普通 USB',
}


def describe(error, stage='UNKNOWN'):
    """Keep structured facts and exception chain, without guessing hardware faults."""
    known = getattr(error, 'diagnostic', None)
    if isinstance(known, dict):
        result = dict(known)
    else:
        code = getattr(error, 'reason', None) or 'OPERATION_FAILED'
        message = str(error) or type(error).__name__
        next_step = '查看运行记录中的具体错误；结果未确认前不要重复写入。'
        if isinstance(error, subprocess.TimeoutExpired):
            code, message = 'HOST_COMMAND_TIMEOUT', '电脑端命令等待超时（%s 秒），任务结果尚未确认。' % error.timeout
        elif isinstance(error, TimeoutError):
            code = 'WAIT_TIMEOUT'
        elif isinstance(error, json.JSONDecodeError):
            code, message = 'STATE_INVALID_JSON', '本地状态文件不完整或格式错误。'
        elif isinstance(error, OSError):
            win = getattr(error, 'winerror', None)
            if error.errno == errno.ENOSPC or win == 112:
                code, message = 'LOCAL_DISK_FULL', '电脑磁盘空间不足，无法保存本轮数据。'
                next_step = '释放磁盘空间，保留本轮记录；先核对相机任务结果。'
            elif win == 1223:
                code, message = 'ADMIN_CANCELLED', 'Windows 管理员授权已取消。'
                next_step = '重新打开工具并确认 Windows 管理员授权。'
            elif error.errno in (errno.EACCES, errno.EPERM) or win in (5, 32, 33):
                code, message = 'LOCAL_ACCESS_DENIED', '电脑拒绝访问文件，或文件被其他程序占用。'
            elif isinstance(error, FileNotFoundError):
                code, message = 'LOCAL_FILE_MISSING', '所需的本地文件不存在。'
        # USBError is deliberately duck typed: source tests need no USB runtime.
        if type(error).__name__ in ('USBError', 'USBTimeoutError'):
            code = 'USB_TIMEOUT' if getattr(error, 'errno', None) in (60, 110) or type(error).__name__ == 'USBTimeoutError' else 'USB_TRANSFER_FAILED'
            message = 'USB 通信超时。' if code == 'USB_TIMEOUT' else 'USB 通信失败，无法确认本次请求结果。'
        if code == 'WINDOWS_RESTART_REQUIRED':
            next_step = '保存电脑上的工作并重启 Windows；重开软件或插拔 USB 不能替代电脑重启。'
        elif code == 'UNSUPPORTED_FIRMWARE':
            next_step = '请使用受支持的 6.02 固件；先恢复普通 USB。'
        result = dict(code=code, stage=stage, message=message, next_step=next_step)
    result.setdefault('stage', stage)
    result['exception_type'] = type(error).__name__
    result['original_error'] = str(error)
    result['errno'] = getattr(error, 'errno', None)
    result['winerror'] = getattr(error, 'winerror', None)
    result['secondary_errors'] = list(getattr(error, 'secondary_errors', []))
    result['traceback'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    return result


def secondary(primary, error, stage):
    """Cleanup/logging errors must not replace the original device failure."""
    entries = list(getattr(primary, 'secondary_errors', []))
    entries.append(dict(stage=stage, type=type(error).__name__, message=str(error)))
    primary.secondary_errors = entries
    if hasattr(primary, 'add_note'):
        primary.add_note(stage + ': ' + str(error))


def summary(value):
    if not isinstance(value, dict):
        return ''
    stage = value.get('stage', 'UNKNOWN')
    prefix = STAGES.get(stage, stage if stage != 'UNKNOWN' else '操作')
    return prefix + '：' + str(value.get('message', '结果未确认')) + '\n' + str(value.get('next_step', '请保留运行记录。'))


def flow_result(value):
    """Success is explicit, never 'anything except REVIEW_REQUIRED'."""
    phase = value.get('phase')
    successful = phase in {'COMPLETE', 'SETUP_COMPLETE', 'USB_RESTORE_COMPLETE'} or (
        phase == 'AWAITING_MENU_OBSERVATION' and value.get('final_unplug_ready') is True)
    return dict(value, schema='m4-user-flow/1', passed=successful)


def save_failure(save, error, phase, **fields):
    """Best-effort error publication; successful operations still fail on save errors."""
    diagnostic = describe(error, fields.pop('failed_stage', phase))
    try:
        return save(phase, **dict(fields, error=str(error), diagnostic=diagnostic))
    except Exception as storage_error:
        secondary(error, storage_error, 'save_failure')
        return None


class OperationFailure(ValueError):
    def __init__(self, code, stage, message, next_step, **details):
        self.diagnostic = dict(code=code, stage=stage, message=message, next_step=next_step, **details)
        super().__init__(message)
