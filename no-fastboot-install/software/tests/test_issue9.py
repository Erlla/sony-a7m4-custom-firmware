"""Issue 9 boundary regressions. Synthetic files/Windows responses; no devices or UAC."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def rejected(call):
    try: call()
    except (ValueError, RuntimeError, OSError): return
    raise AssertionError('Expected rejection')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True)
    package=parser.parse_args().package.resolve(strict=True)
    source=Path(__file__).resolve().parents[1]
    for name in ('app','app/ui','app/workflow','app/provider','app/reader','app/container',
                 'vendor/python','vendor/usb','vendor/squashfs'):
        sys.path.insert(0,str(package/name))
    import product_integrity as integrity
    tests=[]
    with tempfile.TemporaryDirectory(prefix='m4-issue9-') as temp:
        folder=Path(temp);app=folder/'app';app.mkdir()
        file=app/'fixture.bin';file.write_bytes(b'AAAABBBB')
        manifest=app/'release.json'
        raw=json.dumps(dict(schema='m4-clean-product-release/1',version=integrity.VERSION,files={'app/fixture.bin':sha(file)})).encode()
        manifest.write_bytes(raw)
        with patch.object(integrity,'ROOT',folder),patch.object(integrity,'_loaded',{}), \
             patch.object(integrity,'_release_digest',None),patch.dict(os.environ,{},clear=False):
            os.environ.pop('M4_RUNTIME_MANIFEST_SHA256',None)
            integrity.verify_release();lease=integrity._loaded['app/fixture.bin'][0]
            assert integrity.verify_release()['version']==integrity.VERSION
            rejected(lambda:file.write_bytes(b'BBBBAAAA'))
            tests.append('A1_open_read_lease_blocks_same_size_write')
            lease.close();stamp=file.stat();file.write_bytes(b'BBBBAAAA')
            os.utime(file,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            rejected(integrity.verify_release)
            tests.append('A1_closed_lease_forces_hash_despite_restored_mtime')
            file.write_bytes(b'AAAABBBB');integrity.verify_release()
            stamp=manifest.stat();changed=raw.replace(integrity.VERSION.encode(),b'X'*len(integrity.VERSION));manifest.write_bytes(changed)
            os.utime(manifest,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            rejected(integrity.verify_release)
            tests.append('A1_manifest_rehashed_despite_restored_metadata')
            manifest.write_bytes(raw)
            old=folder/'original'
            try:
                app.rename(old);app.mkdir();(app/'fixture.bin').write_bytes(b'BBBBAAAA');(app/'release.json').write_bytes(raw)
            except PermissionError:
                pass # Some Windows filesystems also deny renaming the parent while leased.
            else: rejected(integrity.verify_release)
            tests.append('A1_parent_rebinding_cannot_reuse_cached_digest')
            for held,_ in integrity._loaded.values():held.close()

    # Native startup verifies inert synthetic runtimes. None of these files may execute.
    sys.path.insert(0,str(source));import build
    with tempfile.TemporaryDirectory(prefix='m4-native-') as temp:
        folder=Path(temp);files={}
        names=['app/entry.py','app/product_integrity.py','runtime/python/python.exe',
               'runtime/python/pythonw.exe','runtime/python/python312.dll','runtime/python/_ssl.pyd',
               'runtime/python/python312._pth','vendor/item.txt','tools/item.txt','licenses/item.txt']
        marker=folder/'executed.marker'
        for name in names:
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(('INERT:'+name+'\n').encode());files[name]=sha(path)
        value=dict(files=files,gui_runtime_sha256=files['runtime/python/pythonw.exe'],
                   python_sha256=files['runtime/python/python.exe'],schema='m4-clean-product-release/1',version=integrity.VERSION)
        (folder/'app/release.json').write_text(json.dumps(value),'utf8')
        original_run=subprocess.run
        def compile_run(command,**kwargs):
            if Path(command[0])==folder/'tools/zig/zig.exe':command=[str(package/'tools/zig/zig.exe'),*command[1:]]
            return original_run(command,**kwargs)
        with patch.object(build.subprocess,'run',side_effect=compile_run):build.compile_launcher(folder)
        def verify():
            return original_run([str(folder/'M4相机工具.exe'),'--verify'],capture_output=True,timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        result=verify();assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)['native_verification']
        binary=(folder/'M4相机工具.exe').read_bytes();pe=struct.unpack_from('<I',binary,60)[0];optional=pe+24
        assert struct.unpack_from('<II',binary,optional+112+14*8)==(0,0) # No CLR directory.
        assert struct.unpack_from('<Q',binary,optional+72)[0]==struct.unpack_from('<Q',binary,optional+80)[0]
        tests.append('A2_native_verify_accepts_intact_package_without_python_CLR_or_UAC')
        count=struct.unpack_from('<H',binary,pe+6)[0]
        sections=optional+struct.unpack_from('<H',binary,pe+20)[0]
        def raw_offset(rva):
            for index in range(count):
                at=sections+40*index;virtual,address,size,offset=struct.unpack_from('<IIII',binary,at+8)
                if address<=rva<address+max(virtual,size):return offset+rva-address
            raise AssertionError('Unmapped PE directory')
        imports=raw_offset(struct.unpack_from('<I',binary,optional+112+8)[0]);import_names=[]
        while any(binary[imports:imports+20]):
            at=raw_offset(struct.unpack_from('<I',binary,imports+12)[0])
            import_names.append(binary[at:binary.index(b'\0',at)].decode().lower());imports+=20
        assert import_names==['kernel32.dll'],import_names
        tests.append('A2_native_imports_only_KnownDLL_kernel32')
        for name in names[:7]:
            path=folder/name;raw=path.read_bytes();stamp=path.stat()
            path.write_bytes(bytes([raw[0]^1])+raw[1:]);os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            assert verify().returncode!=0,name
            path.write_bytes(raw)
            tests.append('A2_reject_tampered_'+name)
        for name in ('app/ui/hashlib.py','runtime/python/sitecustomize.py','M4相机工具.exe.CONFIG'):
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('raise RuntimeError("must not execute")','utf8')
            assert verify().returncode!=0,name
            path.unlink();tests.append('A2_reject_unlisted_'+name)
        assert not marker.exists() and verify().returncode==0

    import standalone_usb_restore as direct
    import recovery_registry as registry
    from operation_session import new_session
    with tempfile.TemporaryDirectory(prefix='m4-recovery-') as temp,patch.dict(os.environ,{'ProgramData':temp}):
        private=registry.recovery_root()
        bad=dict(normal_count=1,service_count=0,camera_pmhome_accessible=False,reviewed_package_absent=False,
                 normal=dict(body_sha256='a'*64,service='WinUSB',inf='oem99.inf',status='OK',reviewed_driver=True))
        class Windows:
            launches=0
            state=bad
            def restart_state(self):return dict(phase='CLEAR')
            def probe(self):return copy.deepcopy(self.state)
            def launch(self,folder,body,nonce):
                self.launches+=1;return dict(nonce=nonce,dispatched=True,process_id=123,process_start_utc='fixture')
        windows=Windows()
        with patch.object(direct,'PRIVATE',private),patch.object(direct,'POINTER',private/'current.json'), \
             patch.object(direct,'verify_release'):
            assert direct.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_WAITING'
            new_session()
            spec=importlib.util.spec_from_file_location('restore_next_session',direct.__file__)
            next_session=importlib.util.module_from_spec(spec);spec.loader.exec_module(next_session)
            with patch.object(next_session,'verify_release'):
                assert next_session.PRIVATE==private
                assert next_session.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_WAITING'
                rejected(next_session.require_clear)
                assert windows.launches==1
                tests.append('A3_reopened_session_reuses_pending_helper_without_redispatch')
                row=next_session.pending();next_session.save(row,'DISPATCH_UNKNOWN',process_id=999999)
                assert next_session.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_WAITING'
                assert windows.launches==1
                tests.append('A3_unknown_dead_or_reused_pid_never_unlocks_restore')
                good=copy.deepcopy(bad);good.update(camera_pmhome_accessible=True,reviewed_package_absent=True)
                good['normal'].update(service='USBSTOR',inf='usbstor.inf')
                windows.state=good
                next_session.atomic(private/row['recovery']/'worker_result.json',dict(nonce=row['recovery'],body_sha256='a'*64,status='HELPER_COMPLETE'))
                assert next_session.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_COMPLETE'
                next_session.require_clear();assert windows.launches==1
                tests.append('A3_result_and_fresh_connection_can_complete_without_new_task')
        child='import sys;sys.path.insert(0,sys.argv[1]);from recovery_registry import request_guard;\nwith request_guard(sys.argv[2]): pass'
        with registry.request_guard(private):
            result=subprocess.run([sys.executable,'-I','-B','-c',child,str(package/'app'),str(private)],capture_output=True)
            assert result.returncode!=0 and b'RuntimeError' in result.stderr
        assert subprocess.run([sys.executable,'-I','-B','-c',child,str(package/'app'),str(private)],capture_output=True).returncode==0
        tests.append('A3_real_process_lock_excludes_concurrent_request_and_releases_on_exit')

    import backend_bridge as bridge
    from state_io import atomic_json
    import operation_session
    with tempfile.TemporaryDirectory(prefix='m4-state-') as temp,patch.dict(os.environ,{'M4_TOOL_DATA_ROOT':temp}):
        operation_session.new_session()
        path=operation_session.operation_path('workflow/patch');name='20261030T000000_'+'a'*32
        atomic_json(path/'current.json',{'run':name})
        for phase in ('WRITE_STARTING','READBACK_STARTING','P1_COMPLETE','COMPLETE'):
            atomic_json(path/'control'/(name+'.json'),dict(phase=phase,run=name))
            assert bridge.state_snapshot()['phase']==phase
            tests.append('A4_current_session_'+phase)
        other=Path(temp)/'workflow/patch/current.json';atomic_json(other,{'run':'ignored'})
        assert bridge.state_snapshot()['phase']=='COMPLETE'
        (path/'current.json').write_text('{broken','utf8')
        assert bridge.state_snapshot()['phase']=='REVIEW_REQUIRED'
        tests.append('A4_other_session_ignored_and_corrupt_current_pointer_reported')
        assert integrity.state_path(package/'app/provider')==Path(temp)/'provider'
        tests.append('A2_writable_state_relocated_outside_immutable_runtime')
    report=dict(passed=True,cases=len(tests),tests=tests,device_operations=0,driver_tasks_dispatched=0,
                firmware_operations=0,uac_interaction_tested=False)
    output=package/'state/source_tests/issue9.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n','utf8');print(json.dumps(report))


if __name__=='__main__':main()
