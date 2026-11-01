"""Cross-session recovery coordination; completed UI history remains session-local."""
from contextlib import contextmanager
from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import threading

_held=threading.local()


def user_sid():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    security=ctypes.WinDLL('advapi32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    security.OpenProcessToken.argtypes=(wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(wintypes.HANDLE))
    security.GetTokenInformation.argtypes=(wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD))
    security.ConvertSidToStringSidW.argtypes=(ctypes.c_void_p,ctypes.POINTER(wintypes.LPWSTR))
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    kernel.LocalFree.argtypes=(ctypes.c_void_p,)
    token=wintypes.HANDLE();size=wintypes.DWORD()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        security.GetTokenInformation(token,1,None,0,ctypes.byref(size))
        data=ctypes.create_string_buffer(size.value)
        if not security.GetTokenInformation(token,1,data,len(data),ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid=ctypes.cast(data,ctypes.POINTER(ctypes.c_void_p))[0]
        text=wintypes.LPWSTR()
        if not security.ConvertSidToStringSidW(sid,ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:return text.value
        finally:kernel.LocalFree(ctypes.cast(text,ctypes.c_void_p))
    finally:kernel.CloseHandle(token)


def recovery_root():
    return Path(os.environ['ProgramData'])/'M4CameraToolRecovery'/user_sid()/'operations'


@contextmanager
def request_guard(folder=None):
    import msvcrt
    folder=Path(folder) if folder is not None else recovery_root()
    key=str(folder.resolve())
    active=getattr(_held,'active',None)
    if active and active[0]==key:
        yield
        return
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'request.lock'
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as error:raise RuntimeError('另一个相机请求仍在处理，请稍候再核对。') from error
        _held.active=(key,handle)
        try:yield
        finally:
            _held.active=active
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
