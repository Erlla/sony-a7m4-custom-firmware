"""Content verified while Windows denies writes and replacement of the open file."""
import ctypes
import hashlib
import os
from ctypes import wintypes


class ReadLease:
    def __init__(self, path):
        self.handle = None
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.ReadFile.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
        kernel.ReadFile.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.kernel, self.handle = kernel, handle
        try:
            self.identity = self._identity(handle)
            value=hashlib.sha256(); block=ctypes.create_string_buffer(64*1024)
            view=memoryview(block).cast('B')
            count=wintypes.DWORD()
            while True:
                if not kernel.ReadFile(handle, block, len(block), ctypes.byref(count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not count.value: break
                value.update(view[:count.value])
            self.sha256=value.hexdigest()
        except BaseException:
            self.close()
            raise

    def _identity(self, handle):
        class Info(ctypes.Structure):
            _fields_=[('attributes',wintypes.DWORD),('created',wintypes.FILETIME),
                ('accessed',wintypes.FILETIME),('written',wintypes.FILETIME),
                ('volume',wintypes.DWORD),('size_high',wintypes.DWORD),('size_low',wintypes.DWORD),
                ('links',wintypes.DWORD),('index_high',wintypes.DWORD),('index_low',wintypes.DWORD)]
        self.kernel.GetFileInformationByHandle.argtypes=(wintypes.HANDLE,ctypes.POINTER(Info))
        self.kernel.GetFileInformationByHandle.restype=wintypes.BOOL
        value=Info()
        if not self.kernel.GetFileInformationByHandle(handle,ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.volume,value.index_high,value.index_low

    def same_path(self, path):
        handle=self.kernel.CreateFileW(str(path),0x80000000,1,None,3,0x80,None)
        if handle==ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:return self._identity(handle)==self.identity
        finally:self.kernel.CloseHandle(handle)

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle=None

    def __del__(self):
        self.close()


def acquire(path):
    if os.name == 'nt': return ReadLease(path)
    return None
