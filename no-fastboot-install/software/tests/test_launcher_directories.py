"""Real native verifier: retain path bindings while allowing unrelated file updates."""
from pathlib import Path
from unittest.mock import patch
import argparse,ctypes,hashlib,json,os,subprocess,sys,tempfile,time


def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True)
    package=p.parse_args().package.resolve();source=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(source));import build
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=(ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p)
    kernel.CreateFileW.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=(ctypes.c_void_p,)
    with tempfile.TemporaryDirectory(prefix='m4-dirlease-') as temp:
        folder=Path(temp)/'product';folder.mkdir();files={}
        for name in ('app/entry.py','runtime/python/python.exe','runtime/python/pythonw.exe','vendor/item','licenses/item'):
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'INERT')
            files[name]=hashlib.sha256(b'INERT').hexdigest()
        large=folder/'tools/padding.bin';large.parent.mkdir();size=256*1024*1024
        with large.open('wb') as stream:stream.truncate(size)
        value=hashlib.sha256();zero=b'\0'*65536
        for _ in range(size//len(zero)):value.update(zero)
        files['tools/padding.bin']=value.hexdigest()
        manifest=dict(schema='m4-clean-product-release/1',version='1.0.0',files=files,
            python_sha256=files['runtime/python/python.exe'],gui_runtime_sha256=files['runtime/python/pythonw.exe'])
        (folder/'app/release.json').write_text(json.dumps(manifest),'utf8')
        original=subprocess.run
        def toolchain(command,**kwargs):
            if Path(command[0])==folder/'tools/zig/zig.exe':command=[str(package/'tools/zig/zig.exe'),*command[1:]]
            return original(command,**kwargs)
        with patch.object(build.subprocess,'run',side_effect=toolchain):build.compile_launcher(folder)
        old=folder/'archive.zip';staged=folder/'staged.zip';old.write_bytes(b'old');staged.write_bytes(b'new')
        process=subprocess.Popen([str(folder/'M4相机工具.exe'),'--verify'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+10
            while True:
                handle=kernel.CreateFileW(str(large),0x40000000,7,None,3,0x80,None)
                if handle==ctypes.c_void_p(-1).value:
                    assert ctypes.get_last_error()==32;break
                kernel.CloseHandle(handle)
                if process.poll() is not None or time.monotonic()>deadline:raise AssertionError('Verifier read lease not observed')
                time.sleep(.002)
            os.replace(staged,old);assert old.read_bytes()==b'new'
            try:folder.rename(folder.with_name('rebound'))
            except PermissionError:pass
            else:raise AssertionError('Running verifier directory was renamed')
            stdout,stderr=process.communicate(timeout=15)
            assert process.returncode==0,(stdout,stderr)
        finally:
            if process.poll() is None:process.terminate();process.wait()
    print(json.dumps(dict(passed=True,cases=2,tests=['native_parent_directory_binding_blocks_rename',
        'native_parent_lease_allows_unrelated_child_file_replacement'],device_operations=0,driver_tasks_dispatched=0,firmware_operations=0)))


if __name__=='__main__':main()
