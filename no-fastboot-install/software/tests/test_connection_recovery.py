"""Exercise real journals and UI routing with all device/driver boundaries replaced."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
import importlib.util
import json
import os
import sys
import tempfile
import uuid


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True)
    root=parser.parse_args().package.resolve(strict=True)
    for name in ('app','app/provider','app/workflow','app/ui'):
        sys.path.insert(0,str(root/name))
    from product_integrity import verify_release
    verify_release()
    with tempfile.TemporaryDirectory(prefix='m4-prewrite-package-') as temporary:
        os.environ['M4_TOOL_DATA_ROOT']=temporary
        import integrity_backend as backend
        import simple_workflow as workflow
        import wizard as flow
        import usb_recovery
        import standalone_usb_restore
        import simple_app
        from connection_stop import UnsupportedFirmwareError
        from driver_restart import WindowsRestartRequired
        from normal_identity import DescriptorReadError
        spec=importlib.util.spec_from_file_location('package_library_check',root/'app/protocol/identity.py')
        identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)
        tests=[];device_calls=[]
        def forbidden(*args,**kwargs):
            device_calls.append('forbidden');raise AssertionError('Unexpected reader/writer/driver operation')
        class Backend:
            check=lambda self:None
            runner_sha=lambda self:backend.LOADED_SHA
            preflight=lambda self,folder:None
            def prepare_reader(self,folder,role='before'):
                job=folder/role;job.mkdir();return dict(job=str(job),nonce=uuid.uuid4().hex)
            def bind(self,folder):
                if self.kind=='restart':raise WindowsRestartRequired()
                if self.kind=='descriptor':raise DescriptorReadError(dict(camera_commands=0))
                if self.kind=='legacy':raise RuntimeError('legacy bind refusal')
            @contextmanager
            def session(self,folder):
                out=folder/'execution';out.mkdir()
                try:
                    identity.libraries(SimpleNamespace(_select=lambda path:None,_read_selected=lambda maximum:b'inert alternate library'),out)
                    yield None
                finally:self.closed=True
            run_reader=run_writer=verify_ready=hold_session=forbidden
        for kind in ('restart','descriptor','library','legacy'):
            backend.STATE=Path(temporary)/kind/'patch'
            value=dict(schema='m4-user-flow/1',flow=uuid.uuid4().hex,phase='PATCH_PREPARED',
                       purpose='patch_and_menu_only',package_validation='not_performed')
            flow.folder(value).mkdir(parents=True)
            worker=Backend();worker.kind=kind
            with patch.object(backend,'Backend',return_value=worker):
                try:workflow.patch_receiver(value)
                except (RuntimeError,ValueError):pass
                else:raise AssertionError('Expected a prewrite stop')
            record=backend.frozen.Journal(backend.STATE).load()
            assert not record['firmware_write_attempted'] and not record['firmware_written']
            if kind=='library':
                assert value['error']=='当前相机固件非6.02版本' and worker.closed
            if kind=='restart':
                assert value['phase']=='WINDOWS_RESTART_REQUIRED'
                assert simple_app.presentation(value)[0]=='请重启电脑'
            reply=dict(phase='USB_RESTORE_COMPLETE',message='普通 USB 连接已恢复。')
            with patch.object(standalone_usb_restore,'recover',return_value=reply) as restore,\
                 patch.object(usb_recovery,'recover_write_race',side_effect=forbidden):
                result=usb_recovery.recover(value)
            assert restore.call_count==1 and result['phase']=='CONNECTION_STOPPED'
            assert result['usb_recovery']=='USB_RESTORE_COMPLETE'
            assert backend.frozen.Journal(backend.STATE).load()['phase']=='CONNECTION_STOPPED'
            assert simple_app.presentation(result)[0]=='补丁未写入'
            tests.append(kind+'_failure_uses_driver_only_recovery')
        # Once a reader or writer may have started, the existing evidence route
        # must remain in control; never reinterpret it as an initial connection stop.
        for started in ('READ_STARTING','WRITE_STARTING'):
            backend.STATE=Path(temporary)/started/'patch'
            journal=backend.frozen.Journal(backend.STATE);journal.create(backend.LOADED_SHA)
            journal.update(started,firmware_write_attempted=started=='WRITE_STARTING')
            journal.update('REVIEW_REQUIRED',error='unknown worker result')
            value=dict(schema='m4-user-flow/1',flow=uuid.uuid4().hex,phase='REVIEW_REQUIRED')
            flow.folder(value).mkdir(parents=True)
            with patch.object(standalone_usb_restore,'recover',side_effect=forbidden),\
                 patch.object(usb_recovery,'recover_write_race',return_value={'phase':'EXISTING_PROOF_ROUTE'}) as original:
                assert usb_recovery.recover(value)['phase']=='EXISTING_PROOF_ROUTE'
            assert original.call_count==1
            tests.append(started.lower()+'_keeps_existing_recovery')
        assert not device_calls
        # A menu pre-read that has been classified after verified cleanup uses
        # the existing terminal/driver-only route, never the writer route.
        backend.STATE=Path(temporary)/'menu-cleaned'/'patch'
        journal=backend.frozen.Journal(backend.STATE);journal.create(backend.LOADED_SHA)
        journal.update('P1_COMPLETE',p1_operation_complete=True)
        value=dict(schema='m4-user-flow/1',flow=uuid.uuid4().hex,phase='MENU_CONNECTION_STOPPED',
                   preread_failure_cleaned=True,driver_retained=True)
        reply=dict(phase='USB_RESTORE_COMPLETE',message='普通 USB 连接已恢复。')
        with patch.object(standalone_usb_restore,'recover',return_value=reply) as restore,\
             patch.object(usb_recovery,'recover_write_race',side_effect=forbidden):
            assert usb_recovery.recover(value)['phase']=='USB_RESTORE_COMPLETE'
        assert restore.call_count==1
        tests.append('cleaned_menu_read_failure_uses_existing_driver_only_recovery')
        # Handoff failure cannot authorize a new window or firmware write. Only
        # the user's actual restart confirmation enables the existing driver route.
        value=dict(schema='m4-user-flow/1',flow=uuid.uuid4().hex,phase='HANDOFF_NOT_READY')
        flow.folder(value).mkdir(parents=True)
        controller=SimpleNamespace(status=lambda:(None,None,dict(phase='HANDOFF_NOT_READY',window_started=True)),
                                   record_session_end=lambda observation:None)
        with patch.object(flow,'trial',return_value=controller),\
             patch.object(flow,'observed',return_value=Path(temporary)/'inert-observation.json'),\
             patch.object(standalone_usb_restore,'recover',return_value=reply) as restore,\
             patch.object(usb_recovery,'recover_write_race',side_effect=forbidden):
            try:usb_recovery.recover(value)
            except ValueError:pass
            else:raise AssertionError('Handoff recovery accepted without actual restart confirmation')
            assert restore.call_count==0
            assert usb_recovery.recover(value,confirmed=True)['phase']=='USB_RESTORE_COMPLETE'
            assert restore.call_count==1 and value['final_unplug_ready'] is False
        tests.append('failed_handoff_requires_restart_confirmation_and_only_restores_driver')
        print(json.dumps(dict(passed=True,tests=tests,cases=len(tests),device_operations=0,
                              driver_tasks_dispatched=0,firmware_writes=0)))


if __name__=='__main__':main()
