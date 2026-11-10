"""Host boundary for the agent entry. macOS has no device implementation yet."""
from contextlib import contextmanager
from pathlib import Path
import ctypes
import json
import os
import platform
import subprocess


def capability(system=None, machine=None):
    system, machine = system or platform.system(), machine or platform.machine()
    supported = system == 'Windows' and machine.lower() in ('amd64', 'x86_64')
    return dict(system=system, architecture=machine, supported=supported,
                code='SUPPORTED' if supported else 'PLATFORM_NOT_VALIDATED',
                message='Windows x64' if supported else '此平台尚未完成实机适配，不能操作相机。')


class WindowsHost:
    def probe(self):
        # Passive PnP enumeration only. No libusb/volume access or driver task.
        script = r"""$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$rows=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_054C&PID_(0DA5|0336)\\' })
$normal=@($rows | Where-Object {$_.InstanceId -match 'PID_0DA5'}).Count
$service=@($rows | Where-Object {$_.InstanceId -match 'PID_0336'}).Count
[pscustomobject]@{normal_count=$normal;service_count=$service;scope='passive_windows_pnp_only';device_operations=0} | ConvertTo-Json -Compress
"""
        ps = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run([str(ps), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, encoding='utf-8-sig', errors='replace', timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('Windows 相机枚举失败：' + result.stderr.strip())
        return json.loads(result.stdout)

    def launch(self, executable, job, dispatch):
        """Shell-managed elevated process: no inherited agent stdio or parent job."""
        from ctypes import wintypes as w
        class Info(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('mask', w.ULONG), ('window', w.HWND),
                        ('verb', w.LPCWSTR), ('file', w.LPCWSTR), ('parameters', w.LPCWSTR),
                        ('directory', w.LPCWSTR), ('show', ctypes.c_int), ('instance', w.HINSTANCE),
                        ('idlist', ctypes.c_void_p), ('class_name', w.LPCWSTR), ('key', w.HKEY),
                        ('hotkey', w.DWORD), ('icon', w.HANDLE), ('process', w.HANDLE)]
        call = ctypes.WinDLL('shell32', use_last_error=True).ShellExecuteExW
        call.argtypes = [ctypes.POINTER(Info)]; call.restype = w.BOOL
        info = Info(); info.size = ctypes.sizeof(info); info.mask = 0x40 | 0x400
        info.verb = 'runas'; info.file = str(executable)
        info.parameters = '--agent-worker ' + job + ' ' + dispatch
        info.directory = str(executable.parent); info.show = 0
        if not call(ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        close = ctypes.WinDLL('kernel32', use_last_error=True).CloseHandle
        close.argtypes = [w.HANDLE]; close(info.process)


@contextmanager
def file_lock(path):
    # Portable bookkeeping lock; Windows device coordination remains in the existing broker.
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if not handle.seek(0, 2): handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            handle.seek(0)
            if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(handle, fcntl.LOCK_UN)


def host():
    status = capability()
    if not status['supported']: raise RuntimeError(status['message'])
    return WindowsHost()
