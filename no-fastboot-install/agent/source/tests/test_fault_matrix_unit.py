"""Offline fault injection into actual host functions. Never contacts hardware."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import patch
import ast
import copy
import errno
import hashlib
import importlib.util
import json
import queue
import struct
import subprocess
import threading
import sys
import tempfile
import unittest

SOFTWARE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(SOFTWARE/'app'),str(SOFTWARE/'app/ui'),str(SOFTWARE/'app/usb'),str(SOFTWARE/'app/workflow'),str(Path(__file__).parent)]
import diagnostics
import gui_model
import reader_diagnostics as rd
import usb_session
import backend_bridge
import simple_app
from state_io import claim_once
from reader_cleanup import verify_success_cleanup, verify_failure_cleanup
from test_reader_cleanup_unit import ReaderCleanupTests, frame, NONCE, protocol, FRAME
from test_connection_stop_unit import engine_class, require


class ReaderFaults(ReaderCleanupTests):
    # Inherit six proof tests as well as the real protocol fixture.
    def test_diagnostic_has_precise_operation_and_fd(self):
        self.frames['diagnostic']=rd.FRAME.pack(b'M4RDDG01',bytes.fromhex(NONCE),1,25,-2,101,50,37,3,3)
        error=self.run_failure()
        self.assertEqual(error.diagnostic['native_detail']['subject'],37)
        self.assertIn('ENOENT',str(error));self.assertIn('fd=37',str(error))
    def test_foreign_diagnostic_never_becomes_a_reason(self):
        self.frames['diagnostic']=rd.FRAME.pack(b'M4RDDG01',b'\0'*16,1,25,-2,101,50,37,3,3)
        error=self.run_failure()
        self.assertIsNone(error.diagnostic['native_detail'])
        self.assertIn('未取得具体失败对象',str(error))
    def test_short_ready_and_wrong_nonce_stop_before_start(self):
        for label,data in [('short',b'x'),('foreign',frame(1,nonce='22'*16))]:
            with self.subTest(label=label):
                self.output=self.root/label;self.calls=[];self.frames['ready']=data
                self.run_failure();self.assertNotIn('write:start',self.calls)
                self.assertEqual(self.calls.count('write:libJit.so'),1)
    def test_disk_full_during_failure_report_preserves_native_error(self):
        fn=protocol(self.meta);saved=fn.__globals__['save_json']
        def disk(path,data):
            if Path(path).name=='run.json':raise OSError(errno.ENOSPC,'disk full')
            saved(path,data)
        fn.__globals__['save_json']=disk
        with patch('test_reader_cleanup_unit.protocol',return_value=fn):error=self.run_failure()
        self.assertEqual(error.reason,'READER_STOPPED_CLEANED')
        self.assertEqual(error.secondary_errors[0]['stage'],'save_reader_report')
    def test_success_cleanup_cannot_belong_to_another_worker(self):
        ready=dict(version=1,euid=0,pid=101,ppid=1,loader_pid=50)
        native=dict(ready,phase=4,error=0,cleanup=0,bytes=25100288,chunks=766,flags=127)
        verify_success_cleanup(ready,native,dict(native,phase=5))
        for key,value in [('pid',102),('loader_pid',51),('bytes',0),('cleanup',-5),('flags',3)]:
            with self.subTest(field=key),self.assertRaises(ValueError):
                verify_success_cleanup(ready,native,dict(native,phase=5,**{key:value}))
    def test_capture_faults_do_not_report_complete_or_repeat_ack(self):
        for scenario in ('ok','short_chunk','wrong_digest','wrong_native_hash','wrong_native_pid','wrong_cleaned_pid','ack_lost'):
            with self.subTest(scenario=scenario):
                job=self.root/('capture_job_'+scenario);job.mkdir();(job/'libJit.so').write_bytes(b'inert')
                output=self.root/('capture_'+scenario);calls=[];selected=[''];ticks=[0]
                raw=b'abcdef';digest=hashlib.sha256(raw).digest()
                def published(phase,pid=101,second=digest):
                    return FRAME.pack(b'M4P1RD01',bytes.fromhex(NONCE),1,phase,0,0,pid,1,50,0,6,2,127,digest,second)
                frames=dict(self.frames,result=published(4),cleaned=published(5),
                            digests=hashlib.sha256(raw[:3]).digest()+hashlib.sha256(raw[3:]).digest(),
                            loader_maps=b'maps\n',loader_fds=b'1 /dev/null\n',mountinfo=b'mounts\n',c0000=b'abc',c0001=b'def')
                if scenario=='short_chunk':frames['c0001']=b'de'
                if scenario=='wrong_digest':frames['c0001']=b'deg'
                if scenario=='wrong_native_hash':frames['result']=published(4,second=b'\0'*32)
                if scenario=='wrong_native_pid':frames['result']=published(4,pid=102)
                if scenario=='wrong_cleaned_pid':frames['cleaned']=published(5,pid=102)
                class Session:
                    def _select(self,path):selected[0]=path.rsplit('/',1)[-1]
                    def _read_selected(self,size):return frames[selected[0]]
                    def _jiritsu(self,*a):
                        calls.append(selected[0])
                        if scenario=='ack_lost' and selected[0]=='ack':raise TimeoutError('ACK reply lost')
                        return b''
                run=protocol(self.meta);run.__globals__.update(P1_BYTES=6,COUNT=2,CHUNK=3)
                error=None
                try:run(Session(),job,output,sleep=lambda x:None,clock=lambda:0)
                except Exception as caught:error=caught
                report=json.loads((output/'run.json').read_text('utf-8'))
                if scenario=='ok':self.assertIsNone(error);self.assertEqual(report['verdict'],'P1_READBACK_VERIFIED')
                else:self.assertIsNotNone(error);self.assertNotEqual(report['verdict'],'P1_READBACK_VERIFIED')
                self.assertLessEqual(calls.count('libJit.so'),1);self.assertLessEqual(calls.count('start'),1);self.assertLessEqual(calls.count('ack'),1)


class ErrorDelivery(unittest.TestCase):
    def test_duplicate_and_concurrent_claim_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claim.json';barrier=threading.Barrier(2);results=[]
            def contender(i):
                barrier.wait()
                try:claim_once(path,dict(owner=i));results.append(i)
                except FileExistsError:results.append('rejected')
            threads=[threading.Thread(target=contender,args=(i,)) for i in (1,2)]
            for t in threads:t.start()
            for t in threads:t.join(5);self.assertFalse(t.is_alive())
            self.assertEqual(results.count('rejected'),1)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):claim_once(path,dict(owner=3))
            self.assertEqual(path.read_bytes(),original)
    def test_duplicate_click_and_failed_child_release_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            entered=threading.Event();release=threading.Event();calls=[]
            def executor(*a):
                calls.append(1);entered.set();release.wait(3);raise OSError('injected host failure')
            jobs=backend_bridge.Jobs(private=tmp,executor=executor,validate=False)
            jobs.start('simple-start');self.assertTrue(entered.wait(3))
            with self.assertRaises(RuntimeError):jobs.start('simple-start')
            release.set();jobs.thread.join(5)
            self.assertFalse(jobs.busy);self.assertEqual(len(calls),1)
            events=list(jobs.events.queue)
            self.assertEqual(events[-1][0],'idle');self.assertIn('injected host failure',str(events))
    def test_nonzero_child_without_json_is_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs=backend_bridge.Jobs(private=tmp,executor=lambda *a:(3221225477,''),validate=False)
            jobs.start('simple-start');jobs.thread.join(5)
            receipt=next(v for k,v in jobs.events.queue if k=='finished')
            self.assertNotEqual(receipt['phase'],'SUCCESS')
            self.assertIn('3221225477',receipt['summary']);self.assertFalse(jobs.busy)
    def test_ui_keeps_reason_for_failed_handoff_and_review(self):
        diagnostic=diagnostics.describe(RuntimeError('exact failing fd'),'HANDOFF_NOT_READY')
        for phase in ('HANDOFF_NOT_READY','REVIEW_REQUIRED','MENU_CONNECTION_STOPPED'):
            result=simple_app.presentation(dict(phase=phase,diagnostic=diagnostic))
            self.assertIn('exact failing fd',result[1])
        self.assertEqual(simple_app.presentation(dict(phase='HANDOFF_NOT_READY',diagnostic=diagnostic))[3],'simple-recover-usb')
    def test_common_errors_have_reason_and_action(self):
        cases=[(OSError(errno.ENOSPC,'full'),'LOCAL_DISK_FULL'),
               (PermissionError(errno.EACCES,'denied'),'LOCAL_ACCESS_DENIED'),
               (FileNotFoundError('missing'),'LOCAL_FILE_MISSING'),
               (json.JSONDecodeError('truncated','{',1),'STATE_INVALID_JSON'),
               (subprocess.TimeoutExpired(['inert'],150),'HOST_COMMAND_TIMEOUT'),
               (TimeoutError('reader deadline'),'WAIT_TIMEOUT')]
        for error,code in cases:
            with self.subTest(code=code):
                result=diagnostics.describe(error,'BINDING')
                self.assertEqual(result['code'],code);self.assertEqual(result['stage'],'BINDING')
                self.assertTrue(result['next_step']);self.assertEqual(result['original_error'],str(error))
    def test_menu_failure_never_becomes_passed_true(self):
        for phase in ('HANDOFF_NOT_READY','REVIEW_REQUIRED','MENU_CONNECTION_STOPPED','CONNECTION_STOPPED',
                      'CANCELLED_BEFORE_DEVICE','WINDOWS_RESTART_REQUIRED'):
            with self.subTest(phase=phase):
                row=diagnostics.flow_result(dict(phase=phase,passed=True))
                self.assertFalse(row['passed'])
                self.assertNotEqual(gui_model.classify('simple-start',0,row)[0],'success')
        self.assertFalse(diagnostics.flow_result(dict(phase='AWAITING_MENU_OBSERVATION'))['passed'])
        self.assertTrue(diagnostics.flow_result(dict(phase='AWAITING_MENU_OBSERVATION',final_unplug_ready=True))['passed'])
    def test_error_payload_survives_progress(self):
        d=diagnostics.describe(TimeoutError('capture timeout'),'READBACK_STARTING')
        payload=dict(schema='m4-operation-error/1',passed=False,diagnostic=d)
        parsed=gui_model.final_payload('{"progress_chunks":705,"total_chunks":766}\n'+json.dumps(payload))
        state,text=gui_model.classify('simple-start',1,parsed)
        self.assertEqual(state,'failed');self.assertIn('独立回读',text);self.assertIn('capture timeout',text)
    def test_failed_journal_does_not_mask_primary(self):
        primary=RuntimeError('USB disconnected during commit')
        def write(*a,**kw):raise OSError(errno.ENOSPC,'disk full')
        self.assertIsNone(diagnostics.save_failure(write,primary,'REVIEW_REQUIRED'))
        self.assertEqual(str(primary),'USB disconnected during commit')
        self.assertEqual(primary.secondary_errors[0]['stage'],'save_failure')
    def test_close_failures_keep_primary_and_dispose(self):
        primary=RuntimeError('original reader failure');calls=[]
        class S(usb_session.ResearchSession):
            pass
        s=S(Path('unused'));s.error=primary;s.wire=SimpleNamespace(healthy=True);s.driver=SimpleNamespace(dev='inert')
        def stop():calls.append('stop');raise TimeoutError('stop timeout')
        def dispose(*a):calls.append('dispose');raise OSError('dispose failure')
        s.probe=SimpleNamespace(SenserAuth=lambda *a:SimpleNamespace(stop=stop),usb=SimpleNamespace(util=SimpleNamespace(dispose_resources=dispose)))
        s.rec=SimpleNamespace(note=lambda *a:None,finish=lambda *a:calls.append('finish'))
        s._close()
        self.assertEqual(calls,['stop','dispose','finish']);self.assertEqual(str(primary),'original reader failure')
        self.assertIn('stop timeout',str(primary.secondary_errors));self.assertIsNone(s.driver);self.assertIsNone(s.rec)
        s.error=None;s.driver=SimpleNamespace(dev='inert')
        with self.assertRaises(TimeoutError):s._close()


class EngineFaults(unittest.TestCase):
    def test_fault_at_each_device_boundary_never_repeats_write(self):
        for fail_at in ('preflight','bind','session','verify_ready','before','prepare_write','verify_write_ready','writer','after','verify_written','exit'):
            with self.subTest(stage=fail_at),tempfile.TemporaryDirectory(prefix='m4-fault-') as tmp:
                root=Path(tmp);source=root/'p1';source.write_bytes(b'fixture')
                digest=hashlib.sha256(source.read_bytes()).hexdigest();calls=[]
                def point(stage):
                    calls.append(stage)
                    if stage==fail_at:raise TimeoutError('injected '+stage)
                class Backend:
                    driver_policy='retain'
                    def check(self):pass
                    def runner_sha(self):return 'test'
                    def prepare_reader(self,folder,role='before'):return dict(job=str(folder/role),nonce=role)
                    def preflight(self,*a):point('preflight')
                    def bind(self,*a):point('bind')
                    @contextmanager
                    def session(self,*a):
                        point('session');yield object();point('exit')
                    def verify_ready(self,*a):point('verify_ready')
                    def run_reader(self,session,job,folder):
                        point(job['nonce'])
                        return source,dict(verdict='P1_READBACK_VERIFIED',bytes=7,chunks=1,nonce=job['nonce'],
                            block_writes=False,firmware_written=False,ram_chunks_cleaned=True,sha256=digest)
                    def prepare_write(self,*a):
                        point('prepare_write');return dict(source_sha256=digest,target_sha256=digest,no_change=False)
                    def verify_write_ready(self,*a):point('verify_write_ready')
                    def run_writer(self,*a):point('writer');return dict(outcome='P1_TARGET_VERIFIED')
                    def verify_written(self,*a):point('verify_written');return {}
                    def hold_session(self,*a):calls.append('hold')
                cls=engine_class();env=cls.read.__globals__
                env.update(P1_BYTES=7,CHUNKS=1,sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest(),re=__import__('re'))
                obj=cls(Backend(),root/'journal',emit=lambda _:None)
                with self.assertRaisesRegex(TimeoutError,'injected '+fail_at):obj.read('apply')
                self.assertLessEqual(calls.count('writer'),1);self.assertLessEqual(calls.count('before'),1);self.assertLessEqual(calls.count('after'),1)
                self.assertEqual(obj.journal.value['diagnostic']['original_error'],'injected '+fail_at)
                self.assertNotIn(obj.journal.value['phase'],('P1_COMPLETE','COMPLETE'))
                attempted=fail_at in ('writer','after','verify_written','exit')
                self.assertEqual(obj.journal.value['firmware_write_attempted'],attempted)
                if attempted:self.assertEqual(obj.journal.value['phase'],'REVIEW_REQUIRED')


if __name__=='__main__':unittest.main(verbosity=2)
