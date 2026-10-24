"""Atomic JSON state I/O with Windows delete-sharing and bounded rename retries.

Retries apply to publishing one already-written local JSON file only. They must
never wrap USB requests, driver dispatch, native START or COMMIT operations.
"""
from pathlib import Path
import json
import os
import time
import uuid


def io_path(path):
    value = os.path.abspath(os.fspath(path))
    if os.name != 'nt' or value.startswith('\\\\?\\'):
        return value
    return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value


def read_json(path):
    if os.name != 'nt':
        with open(io_path(path), 'r', encoding='utf-8-sig') as stream:
            return json.load(stream)
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    # FILE_SHARE_DELETE lets atomic replacement proceed while a GUI reader holds
    # the old file. Its handle continues to see that complete old JSON document.
    handle = kernel.CreateFileW(io_path(path), 0x80000000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = os.fspath(path)
        raise error
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, 'r', encoding='utf-8-sig') as stream:
        return json.load(stream)


def _replace_once(source, target):
    if os.name != 'nt':
        os.replace(io_path(source), io_path(target))
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.ReplaceFileW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)
    kernel.ReplaceFileW.restype = wintypes.BOOL
    if kernel.ReplaceFileW(io_path(target), io_path(source), None, 0, None, None):
        return
    code = ctypes.get_last_error()
    if code == 2 and not os.path.exists(io_path(target)):
        # First publication has no existing document to replace.
        os.replace(io_path(source), io_path(target))
        return
    error = ctypes.WinError(code)
    error.filename, error.filename2 = os.fspath(source), os.fspath(target)
    raise error


def replace_state(source, target, *, timeout=2.0, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    delay = 0.01
    while True:
        try:
            _replace_once(source, target)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or clock() >= deadline:
                raise
            sleep(min(delay, max(0, deadline - clock())))
            delay = min(delay * 1.6, 0.15)


def atomic_json(path, value):
    path = Path(path)
    os.makedirs(io_path(path.parent), exist_ok=True)
    temporary = path.parent / ('j' + uuid.uuid4().hex + '.tmp')
    created = False
    try:
        with open(io_path(temporary), 'x', encoding='utf-8', newline='\n') as stream:
            created = True
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        replace_state(temporary, path)
    finally:
        if created:
            try:
                os.unlink(io_path(temporary))
            except FileNotFoundError:
                pass
            except PermissionError:
                # Keep a temporarily locked leftover for inspection; never mask
                # the publication exception or overwrite the prior valid JSON.
                pass
