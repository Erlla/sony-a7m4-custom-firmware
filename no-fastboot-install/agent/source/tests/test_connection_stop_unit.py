"""Pre-reader stops, recovery evidence and firmware diagnostics without USB."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

SOFTWARE=Path(__file__).resolve().parents[1]
for path in ('app','app/workflow'):
    sys.path.insert(0,str(SOFTWARE/path))
from connection_stop import ConnectionStop, UnsupportedFirmwareError
from reader_cleanup import ReaderStopped
from driver_restart import WindowsRestartRequired
from normal_identity import DescriptorReadError
import prewrite_recovery


def require(value,message):
    if not value:raise ValueError(message)


class Journal:
    def __init__(self,folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.value=None;self.events=[]
    def load(self):return self.value
    def create(self,runner):
        self.value=dict(run='offline-run',runner_sha256=runner,firmware_write_attempted=False,
                        firmware_written=False,read_verified=False,session_ended=False)
        self.update('PREPARING')
    def update(self,phase,**fields):
        self.value.update(phase=phase,**fields)
        self.events.append(copy.deepcopy(self.value))
        (self.folder/'events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.events),'utf-8')


def engine_class():
    source=SOFTWARE/'app/receiver_stock/orchestrator.py'
    node=next(n for n in ast.parse(source.read_text('utf-8-sig')).body if isinstance(n,ast.ClassDef) and n.name=='Engine')
    env=dict(Journal=Journal,ConnectionStop=ConnectionStop,ReaderStopped=ReaderStopped,require=require,TERMINAL={'CONNECTION_STOPPED'},Path=Path)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
    return env['Engine']


class ConnectionStopTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='m4-prewrite-')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)

    def backend(self,stage,error):
        calls=[]
        class Backend:
            def check(self):pass
            def runner_sha(self):return 'source-runner'
            def prepare_reader(self,folder,role='before'):
                return dict(job=str(folder/role),nonce=role)
            def preflight(self,folder):
                if stage=='preflight':raise error
            def bind(self,folder):
                calls.append('bind')
                if stage=='bind':raise error
            @contextmanager
            def session(self,folder):
                calls.append('session')
                if stage=='session':raise error
                yield SimpleNamespace()
            def verify_ready(self,*args):pass
            def run_reader(self,*args):
                calls.append('reader');raise error
            def hold_session(self,session):pass
        return Backend(),calls

    def test_known_stops_before_reader_are_terminal_and_restoreable(self):
        for stage,error in [('preflight',WindowsRestartRequired()),('bind',WindowsRestartRequired()),
                            ('bind',DescriptorReadError(dict(camera_commands=0))),
                            ('session',UnsupportedFirmwareError(dict(path='/usr/lib/libJiritsu.so')))]:
            with self.subTest(stage=stage,error=type(error).__name__):
                backend,calls=self.backend(stage,error)
                engine=engine_class()(backend,self.root/(stage+type(error).__name__),emit=lambda _:None)
                with self.assertRaises(type(error)):engine.read('apply')
                self.assertEqual(engine.journal.value['phase'],'CONNECTION_STOPPED')
                self.assertEqual(engine.journal.value['outcome'],error.reason)
                self.assertNotIn('reader',calls)
                self.assertIsNotNone(prewrite_recovery.proof(engine.journal))

    def stopped(self):
        journal=Journal(self.root/'journal');journal.create('source-runner')
        journal.update('BINDING');journal.update('REVIEW_REQUIRED',outcome='DRIVER_BIND_OUTCOME_UNKNOWN')
        return journal

    def test_legacy_bind_failure_can_restore_without_writer_material(self):
        self.assertIsNotNone(prewrite_recovery.proof(self.stopped()))

    def test_any_reader_start_prevents_this_recovery(self):
        journal=self.stopped();journal.update('READ_STARTING');journal.update('REVIEW_REQUIRED')
        self.assertIsNone(prewrite_recovery.proof(journal))

    def test_claim_write_attempt_result_and_missing_events_prevent_reclassification(self):
        for name in ('claim','write','result','events'):
            with self.subTest(name=name):
                journal=self.stopped()
                if name=='claim':
                    job=self.root/'job';job.mkdir(exist_ok=True);(job/'claim.json').write_text('{}')
                    journal.update('REVIEW_REQUIRED',reader=dict(job=str(job)))
                elif name=='write':journal.update('REVIEW_REQUIRED',firmware_write_attempted=True)
                elif name=='result':journal.update('REVIEW_REQUIRED',reader_result={'started':True})
                else:(journal.folder/'events.jsonl').unlink()
                self.assertIsNone(prewrite_recovery.proof(journal))

    def test_connection_error_after_reader_start_stays_unresolved(self):
        backend,calls=self.backend('reader',DescriptorReadError({}))
        engine=engine_class()(backend,self.root/'after-read',emit=lambda _:None)
        with self.assertRaises(DescriptorReadError):engine.read('apply')
        self.assertEqual(engine.journal.value['phase'],'REVIEW_REQUIRED')

    def test_cleaned_reader_stop_is_distinct_from_unknown_read_outcome(self):
        error=ReaderStopped(dict(native=dict(error=-2)))
        backend,calls=self.backend('reader',error)
        engine=engine_class()(backend,self.root/'cleaned-read',emit=lambda _:None)
        with self.assertRaises(ReaderStopped):engine.read('apply')
        self.assertEqual(engine.journal.value['phase'],'CONNECTION_STOPPED')
        self.assertEqual(engine.journal.value['outcome'],'READER_STOPPED_CLEANED')
        self.assertTrue(engine.journal.value['session_ended'])

    def test_cleaned_readback_failure_after_writing_keeps_write_review(self):
        error=ReaderStopped(dict(native=dict(error=-2)))
        backend,calls=self.backend('reader',error)
        source=self.root/'source.bin';source.write_bytes(b'test');digest=hashlib.sha256(b'test').hexdigest()
        reads=[]
        def run_reader(session,job,folder):
            reads.append(job['nonce'])
            if len(reads)>1:raise error
            return source,dict(verdict='P1_READBACK_VERIFIED',bytes=4,chunks=1,nonce=job['nonce'],
                               block_writes=False,firmware_written=False,ram_chunks_cleaned=True,sha256=digest)
        backend.run_reader=run_reader
        backend.prepare_write=lambda *a:dict(source_sha256=digest,target_sha256='b'*64,no_change=False)
        backend.verify_write_ready=lambda *a:None
        backend.run_writer=lambda *a:dict(outcome='P1_TARGET_VERIFIED')
        backend.hold_session=lambda *a:calls.append('hold')
        cls=engine_class();cls.read.__globals__.update(P1_BYTES=4,CHUNKS=1,sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest(),re=__import__('re'))
        engine=cls(backend,self.root/'readback',emit=lambda _:None)
        with self.assertRaises(ReaderStopped):engine.read('apply')
        self.assertEqual(engine.journal.value['phase'],'REVIEW_REQUIRED')
        self.assertTrue(engine.journal.value['firmware_write_attempted'])
        self.assertIn('hold',calls)
        self.assertIsNone(prewrite_recovery.proof(engine.journal))
        self.assertIsNone(prewrite_recovery.proof(engine.journal))

    def test_stagebind_reboot_stops_before_loading_usb(self):
        source=SOFTWARE/'app/workflow/user_provider.py'
        cls=next(n for n in ast.parse(source.read_text('utf-8-sig')).body if isinstance(n,ast.ClassDef) and n.name=='Provider')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='bind')
        saved=[]
        env=dict(ENROLLMENT=SimpleNamespace(exists=lambda:True),require=require,
                 atomic=lambda path,value:saved.append((path.name,value)),ROOT=SOFTWARE)
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),env)
        calls=[]
        class Provider:
            def snapshot(self,*args,**kwargs):calls.append('snapshot');return self.root,{}
            def same_body(self,state):return {}
            def tasks_clear(self,state):pass
            def communication_driver(self,row):return 'storage'
            def host(self,*args):
                calls.append('StageBind');return 0,dict(status='WINUSB_BOUND',reboot_required=True)
        provider=Provider();provider.root=self.root
        with self.assertRaises(WindowsRestartRequired):env['bind'](provider,self.root)
        self.assertEqual(calls,['snapshot','StageBind'])
        self.assertEqual(saved[0][0],'stage_bind_restart.json')

    def test_firmware_message_keeps_actual_hash_and_saved_file(self):
        source=SOFTWARE/'app/protocol/identity.py'
        spec=importlib.util.spec_from_file_location('source_library_identity',source)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        data=b'inert alternate library bytes'
        session=SimpleNamespace(_select=lambda path:None,_read_selected=lambda maximum:data)
        with self.assertRaises(UnsupportedFirmwareError) as caught:
            helper.libraries(session,self.root)
        self.assertEqual(str(caught.exception),'当前相机固件非6.02版本')
        report=json.loads((self.root/'library_compatibility.json').read_text('utf-8'))
        self.assertEqual(report['actual_sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual((self.root/'libJiritsu.so').read_bytes(),data)

    def test_restart_preflight_uses_saved_wait_without_changing_windows(self):
        import driver_restart
        with patch.object(driver_restart,'check',return_value={'phase':'WINDOWS_RESTART_REQUIRED'}):
            with self.assertRaises(WindowsRestartRequired):driver_restart.require_ready()


if __name__=='__main__':unittest.main(verbosity=2)
