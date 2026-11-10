"""Offline recovery-path regression; no camera, driver helper or UAC calls."""
from pathlib import Path
from unittest.mock import patch
import argparse
import copy
import json
import queue
import sys
import tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True)
    root=p.parse_args().package.resolve()
    for name in ('app','app/ui','app/workflow','app/provider','app/reader','app/container','vendor/python','vendor/usb','vendor/squashfs'):
        sys.path.insert(0,str(root/name))
    import standalone_usb_restore as restore
    import gui_model, simple_app
    bad=dict(normal_count=1,service_count=0,camera_pmhome_accessible=False,reviewed_package_absent=False,
             normal=dict(body_sha256='a'*64,service='WinUSB',inf='oem99.inf',status='OK',reviewed_driver=True))
    class Windows:
        launches=0
        snapshot=bad
        def restart_state(self):return dict(phase='CLEAR')
        def probe(self):return copy.deepcopy(self.snapshot)
        def launch(self,folder,body,nonce):
            self.launches+=1;return dict(nonce=nonce,dispatched=True,process_id=123)
    tests=[]
    for mode in ('known_old','explicit_stop','unknown_hash','mutation_attempted','conflicting_receipt','wrong_body'):
        with tempfile.TemporaryDirectory() as temp,patch.object(restore,'PRIVATE',Path(temp)), \
             patch.object(restore,'POINTER',Path(temp)/'current.json'),patch.object(restore,'verify_release'):
            name='b'*32;folder=Path(temp)/name
            record=dict(schema='m4-driver-only-recovery/1',recovery=name,body_sha256='a'*64,phase='REVIEW_REQUIRED')
            worker=dict(nonce=name,body_sha256='a'*64,status='HELPER_NEEDS_CHECK',helper_exit_code=1)
            hashes=dict(restore.PATH_BUG_HASHES)
            if mode=='explicit_stop':worker.update(status='STOPPED_BEFORE_DRIVER_CHANGE',device_mutation_started=False)
            if mode=='unknown_hash':hashes['standalone_usb_restore.ps1']='0'*64
            if mode=='mutation_attempted':worker.update(status='STOPPED_BEFORE_DRIVER_CHANGE',device_mutation_started=True)
            if mode=='wrong_body':worker['body_sha256']='c'*64
            restore.atomic(folder/'recovery.json',record);restore.atomic(restore.POINTER,dict(recovery=name))
            restore.atomic(folder/'worker_result.json',worker);restore.atomic(folder/'helper_hashes.json',hashes)
            if mode=='conflicting_receipt':restore.atomic(folder/'state/results/auto_restore_result.private.json',{'status':'running'})
            before=(folder/'worker_result.json').read_bytes()
            stop=restore.prechange_stop(record)
            assert bool(stop)==(mode in ('known_old','explicit_stop')),mode
            windows=Windows()
            if stop:
                # First click without a device can retire the proven local stop,
                # while reporting the disconnected state and dispatching nothing.
                windows.snapshot=dict(normal_count=0,service_count=0)
                assert restore.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_REPLUG'
                assert restore.pending()['phase']=='CANCELLED_BEFORE_CHANGE' and windows.launches==0
                assert (folder/'worker_result.json').read_bytes()==before
                # A later explicit click on the same body may dispatch one new task.
                windows.snapshot=bad
                assert restore.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_WAITING'
                assert restore.recover(windows,wait_seconds=0)['phase']=='USB_RESTORE_WAITING'
                assert windows.launches==1
            else:
                assert restore.pending()['phase']=='REVIEW_REQUIRED'
                assert windows.launches==0
            tests.append(mode+'_proof_and_retry_boundary')
    with tempfile.TemporaryDirectory() as temp,patch.object(restore,'PRIVATE',Path(temp)), \
         patch.object(restore,'POINTER',Path(temp)/'current.json'),patch.object(restore,'verify_release'):
        class PreflightStop(Windows):
            def launch(self,folder,body,nonce):
                self.launches+=1
                restore.atomic(folder/'worker_result.json',dict(nonce=nonce,body_sha256=body,
                    status='STOPPED_BEFORE_DRIVER_CHANGE',device_mutation_started=False,error='fixture preflight'))
                return dict(nonce=nonce,dispatched=True,process_id=123)
        windows=PreflightStop()
        result=restore.recover(windows,wait_seconds=0)
        assert result['phase']=='USB_RESTORE_RETRY' and result['error']=='fixture preflight'
        assert windows.launches==1 and restore.pending()['phase']=='CANCELLED_BEFORE_CHANGE'
        tests.append('fresh_preflight_stop_reports_manual_retry_without_automatic_redispatch')
    for phase in ('USB_RESTORE_REPLUG','USB_RESTORE_WAITING','USB_RESTORE_RETRY','USB_RESTORE_CANCELLED'):
        assert gui_model.classify('simple-recover-usb',0,dict(phase=phase,passed=True,message='waiting'))[0]=='waiting'
    tests.append('disconnected_pending_or_retry_is_not_classified_as_restore_success')
    import tkinter as tk
    class Jobs:
        busy=False
        events=queue.Queue()
    top=tk.Tk();top.withdraw()
    app=simple_app.App(top,jobs=Jobs(),flow_reader=lambda:dict(phase='COMPLETE',usb_recovery='NOT_REQUESTED'))
    Jobs.events.put(('finished',dict(phase='WAITING',action='simple-recover-usb',result=dict(phase='USB_RESTORE_REPLUG',message='请连接相机。'))))
    app.poll();top.update_idletasks()
    assert app.restore.cget('state')=='normal' and app.result.get()=='请连接相机。'
    assert app.progress_text.get()=='等待连接或操作' and app.bar.cget('value')==0
    app.close();tests.append('disconnected_restore_keeps_button_available_and_progress_waiting')
    report=dict(passed=True,cases=len(tests),tests=tests,device_operations=0,driver_tasks_dispatched=0,firmware_operations=0)
    output=root/'state/source_tests/restore_retry.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n','utf8');print(json.dumps(report))


if __name__=='__main__':main()
