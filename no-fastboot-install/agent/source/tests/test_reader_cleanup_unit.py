"""Native reader failures: bounded cleanup, saved proof and no repeated upload."""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import ast
import copy
import hashlib
import json
import struct
import sys
import tempfile
import unittest

SOFTWARE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(SOFTWARE/'app'),str(SOFTWARE/'app/workflow')]
from reader_cleanup import ReaderStopped, FRAME, FIELDS, verify_saved_failure
import prewrite_recovery
NONCE='11'*16

def require(value,message):
    if not value:raise ValueError(message)
def save_json(path,value):Path(path).write_text(json.dumps(value),'utf-8')
def frame(phase,error=0,pid=101,cleanup=0,nonce=NONCE):
    return FRAME.pack(b'M4P1RD01',bytes.fromhex(nonce),1,phase,error,0,pid,1,50,cleanup,0,0,3,b'\0'*32,b'\0'*32)

def protocol(meta):
    env=dict(Path=Path,datetime=datetime,timezone=timezone,json=json,struct=struct,hashlib=hashlib,
             time=__import__('time'),require=require,save_json=save_json,validate=lambda folder:meta,
             RESULT=FRAME,FIELDS=FIELDS,LAUNCH=struct.Struct('<8s16s10q'),P1_BYTES=25100288,CHUNK=32768,COUNT=766,
             ReaderStopped=ReaderStopped)
    from reader_cleanup import verify_failure_cleanup
    env['verify_failure_cleanup']=verify_failure_cleanup
    from state_io import claim_once
    env['claim_once']=claim_once
    from reader_cleanup import verify_success_cleanup
    from reader_diagnostics import FRAME as diagnostic_frame, decode as decode_diagnostic, failure as reader_failure
    from diagnostics import describe, secondary
    env.update(verify_success_cleanup=verify_success_cleanup,DIAGNOSTIC_FRAME=diagnostic_frame,
               decode_diagnostic=decode_diagnostic,reader_failure=reader_failure,describe=describe,secondary=secondary)
    for file,name in [('reader_job.py','decode'),('live_reader.py','run_protocol')]:
        path=SOFTWARE/'app/reader'/file
        node=next(n for n in ast.parse(path.read_text('utf-8')).body if isinstance(n,ast.FunctionDef) and n.name==name)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
    return env['run_protocol']


class ReaderCleanupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='m4-reader-cleanup-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.job=self.root/'job';self.job.mkdir()
        (self.job/'libJit.so').write_bytes(b'inert; never executed')
        self.output=self.root/'execution/before'
        self.meta=dict(nonce=NONCE,job_dir='/fixture/reader_'+NONCE)
        self.frames=dict(launch=struct.pack('<8s16s10q',b'M4BOOT01',bytes.fromhex(NONCE),1,3,0,0,50,0,101,101,0,0),
                         ready=frame(1),result=frame(90,-2),cleaned=frame(5,-2))
        self.calls=[];self.tick=0
    def run_failure(self):
        test=self
        if (self.job/'claim.json').exists():
            self.job=self.root/('job_'+str(len(self.calls)));self.job.mkdir()
            (self.job/'libJit.so').write_bytes(b'inert')
        class Missing(Exception):status=268435462
        class Session:
            def _select(self,path):self.name=path.rsplit('/',1)[-1]
            def _read_selected(self,size):
                test.calls.append('read:'+self.name)
                if self.name not in test.frames:raise Missing()
                return test.frames[self.name]
            def _jiritsu(self,*args):test.calls.append('write:'+self.name);return b''
        def sleep(delay):test.tick+=delay
        try:protocol(self.meta)(Session(),self.job,self.output,sleep=sleep,clock=lambda:self.tick)
        except Exception as error:return error
        raise AssertionError('Expected failed reader')
    def test_cleaned_failure_keeps_original_error_and_never_reuploads(self):
        error=self.run_failure()
        self.assertIsInstance(error,ReaderStopped)
        result=verify_saved_failure(self.output,NONCE)
        self.assertEqual(result['native']['error'],-2)
        self.assertEqual(self.calls,['write:libJit.so','read:launch','read:ready','write:start','read:result','read:diagnostic','read:cleaned'])
        report=json.loads((self.output/'run.json').read_text('utf-8'))
        self.assertFalse(report['firmware_written']);self.assertEqual(report['ack_attempts'],0)
    def test_missing_cleanup_is_bounded_and_never_assumed_complete(self):
        del self.frames['cleaned']
        error=self.run_failure()
        self.assertNotIsInstance(error,ReaderStopped);self.assertLess(self.tick,16)
        self.assertEqual(self.calls.count('write:libJit.so'),1);self.assertEqual(self.calls.count('write:start'),1)
        report=json.loads((self.output/'run.json').read_text('utf-8'))
        self.assertEqual(report['native']['error'],-2);self.assertIn('cleanup_error',report)
        self.assertNotIn('ram_chunks_cleaned',report)
    def test_foreign_or_dirty_cleanup_remains_unresolved(self):
        for name,bad in [('pid',frame(5,-2,pid=102)),('nonce',frame(5,-2,nonce='22'*16)),
                         ('error',frame(5,-5)),('cleanup',frame(5,-2,cleanup=-5))]:
            with self.subTest(name=name):
                self.output=self.root/name;self.frames['cleaned']=bad
                self.assertNotIsInstance(self.run_failure(),ReaderStopped)
    def test_saved_proof_rejects_wrong_nonce_and_modified_summary(self):
        self.assertIsInstance(self.run_failure(),ReaderStopped)
        with self.assertRaises(ValueError):verify_saved_failure(self.output,'22'*16)
        path=self.output/'run.json';report=json.loads(path.read_text('utf-8'));report['firmware_written']=True
        save_json(path,report)
        with self.assertRaises(ValueError):verify_saved_failure(self.output,NONCE)
    def test_claimed_initial_reader_can_restore_only_with_cleanup_proof(self):
        self.assertIsInstance(self.run_failure(),ReaderStopped)
        record=dict(run='fixture-run',phase='CONNECTION_STOPPED',outcome='READER_STOPPED_CLEANED',
                    firmware_write_attempted=False,firmware_written=False,read_verified=False,
                    reader=dict(job=str(self.job),nonce=NONCE))
        events=[dict(record,phase=p) for p in ('PREPARING','PREFLIGHT','BINDING','BOUND','READ_STARTING','CONNECTION_STOPPED')]
        (self.root/'events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in events),'utf-8')
        journal=SimpleNamespace(folder=self.root,load=lambda:record)
        self.assertTrue(prewrite_recovery.proof(journal)['reader_started'])
        (self.output/'cleaned.bin').unlink()
        self.assertIsNone(prewrite_recovery.proof(journal))
    def test_write_attempt_cannot_use_cleaned_reader_recovery(self):
        record=dict(run='fixture-run',phase='CONNECTION_STOPPED',outcome='READER_STOPPED_CLEANED',
                    firmware_write_attempted=True,firmware_written=False,read_verified=False)
        self.assertIsNone(prewrite_recovery.proof(SimpleNamespace(folder=self.root,load=lambda:record)))


if __name__=='__main__':unittest.main(verbosity=2)
