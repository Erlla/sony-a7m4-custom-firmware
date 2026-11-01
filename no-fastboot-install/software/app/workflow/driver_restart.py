"""Classify Windows restart waits and confirm existing driver outcomes only."""
from pathlib import Path
import json
import os
import subprocess

MESSAGE = 'Windows 驱动变更需要重启电脑才能生效。请保存工作并重启电脑，再打开工具；本步骤不需要再次写入补丁。'


class WindowsRestartRequired(RuntimeError):
    pass


def check(*, confirm=False):
    ps = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    environment = os.environ.copy(); environment.pop('PSModulePath', None)
    result = subprocess.run([str(ps), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', str(Path(__file__).with_suffix('.ps1')), '-Mode', 'Confirm' if confirm else 'Inspect'],
        capture_output=True, encoding='utf-8-sig', errors='replace', timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
    if result.returncode:
        raise RuntimeError('Windows 驱动状态核对未完成：' + result.stderr.strip())
    return json.loads(result.stdout.lstrip('\ufeff'))


def require_ready():
    result = check(confirm=True)
    if result['phase'] == 'WINDOWS_RESTART_REQUIRED': raise WindowsRestartRequired(MESSAGE)
    if result['phase'] == 'RESTARTED_CONNECTION_PENDING':
        raise RuntimeError('电脑已重启，请保持相机开机，重新插拔 USB 后先确认普通连接。')
    return result
