"""Actual writer host protocol with inert camera replies and injected failures."""
from datetime import datetime, timezone
from pathlib import Path
import ast
import copy
import json
import struct
import sys
import tempfile
import time
import unittest

SOFTWARE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOFTWARE/'app'))
from diagnostics import describe, secondary
from state_io import claim_once

FORMAT=struct.Struct('<8s16s15q32s32s')
FIELDS=('version','phase','error','euid','pid','ppid','loader_pid','cleanup','mode','rows','write_calls','write_bytes','rollback','flags','io_status')
NONCE='11'*16
def require(value,message):
    if not value:raise ValueError(message)
def save_json(path,value):Path(path).write_text(json.dumps(value),'utf-8')
def publication(phase,**extra):
    values=dict(version=1,phase=phase,error=0,euid=0,pid=101,ppid=1,loader_pid=50,cleanup=0,mode=1,rows=1,
                write_calls=1 if phase==6 else 0,write_bytes=4 if phase==6 else 0,rollback=0,flags={2:3,3:31,6:255}[phase],io_status=0)
    values.update(extra);before=values.pop('before','aa'*32);after=values.pop('after','bb'*32)
    nonce=values.pop('nonce',NONCE)
    return FORMAT.pack(b'M4P1WR01',bytes.fromhex(nonce),*(values[k] for k in FIELDS),bytes.fromhex(before),bytes.fromhex(after))


def load_protocol(meta):
    env=dict(Path=Path,datetime=datetime,timezone=timezone,time=time,struct=struct,json=json,
             require=require,save_json=save_json,claim_once=claim_once,RESULT=FORMAT,FIELDS=FIELDS,
             MODE={'apply':1},LAUNCH=struct.Struct('<8s16s10q'),validate=lambda _:meta,local_path=Path,
             token=lambda meta,commit=False:b'COMMIT' if commit else b'PREPARE',MISSING_STATUS=268435462,
             describe=describe,secondary=secondary)
    for name,names in [('receiver_stock/receiver_writer_job.py',{'decode'}),
                       ('workflow/receiver_usb_writer_user.py',{'ProtocolError','poll_publication','run_protocol'})]:
        path=SOFTWARE/'app'/name;tree=ast.parse(path.read_text('utf-8'))
        selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),env)
    return env['run_protocol']


class WriterFaults(unittest.TestCase):
    def test_disconnect_short_reply_wrong_worker_rollback_and_disk_full(self):
        scenarios=('ok','module','table','w0000','prepare','commit','prepared_short','wrong_nonce',
                   'prepared_worker','final_worker','result_timeout','readback_mismatch','rollback_ok','rollback_failed','log_full')
        for scenario in scenarios:
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory(prefix='m4-writer-fault-') as tmp:
                root=Path(tmp);job=root/'job';job.mkdir();(job/'assets').mkdir()
                (job/'libJit.so').write_bytes(b'inert');(job/'assets/table').write_bytes(b'table');(job/'assets/w0000').write_bytes(b'OLD!NEW!')
                meta=dict(nonce=NONCE,direction='apply',job_dir='/fixture',source_sha256='aa'*32,target_sha256='bb'*32,
                          windows=[dict(name='w0000',length=4)],patch_set='fixture',goal='fixture',target_gate_state='fixture',
                          origin_gate_state='fixture',target_version_gate_kind='fixture')
                data=dict(ready=publication(2),prepared=publication(3),result=publication(6),rb0000=b'NEW!',
                    launch=struct.pack('<8s16s10q',b'M4BOOT01',bytes.fromhex(NONCE),1,3,0,0,50,0,101,101,0,0))
                if scenario=='prepared_short':data['prepared']=b'short'
                if scenario=='wrong_nonce':data['prepared']=publication(3,nonce='22'*16)
                if scenario=='prepared_worker':data['prepared']=publication(3,pid=102)
                if scenario=='final_worker':data['result']=publication(6,pid=102,error=-5,rollback=1,after='aa'*32)
                if scenario=='result_timeout':del data['result']
                if scenario=='readback_mismatch':data['rb0000']=b'BAD!'
                if scenario in ('rollback_ok','rollback_failed','log_full'):
                    data['result']=publication(6,error=-5,rollback=1 if scenario!='rollback_failed' else 2,
                                               after='aa'*32 if scenario!='rollback_failed' else 'cc'*32)
                calls=[];tick=[0]
                class Missing(Exception):status=268435462
                class Session:
                    def _select(self,path):self.name=path.rsplit('/',1)[-1]
                    def _read_selected(self,size):
                        if self.name not in data:raise Missing()
                        return data[self.name]
                    def _jiritsu(self,cmd,value):
                        name=self.name;calls.append(name)
                        if name==scenario or (name=='libJit.so' and scenario=='module'):raise TimeoutError('lost '+name+' reply')
                        if name in ('table','w0000'):data[name]=value[3:]
                        return b''
                def sleep(delta):tick[0]+=delta
                run=load_protocol(meta)
                if scenario=='log_full':
                    def full(path,value):
                        if Path(path).name=='run.json':raise OSError(28,'full')
                        save_json(path,value)
                    run.__globals__['save_json']=full
                error=None
                try:result=run(Session(),job,root/'out',sleep=sleep,clock=lambda:tick[0],timeout=1)
                except Exception as caught:error=caught
                self.assertLessEqual(calls.count('libJit.so'),1);self.assertLessEqual(calls.count('prepare'),1);self.assertLessEqual(calls.count('commit'),1)
                self.assertIsNotNone(error) if scenario!='ok' else self.assertEqual(result['outcome'],'P1_TARGET_VERIFIED')
                if scenario=='log_full':
                    self.assertIn('Native writer did not confirm target',str(error))
                    self.assertEqual(error.secondary_errors[0]['stage'],'save_writer_report')
                else:
                    record=json.loads((root/'out/run.json').read_text('utf-8'))
                    if scenario=='rollback_ok':self.assertEqual(record['outcome'],'ROLLED_BACK_VERIFIED')
                    elif scenario=='rollback_failed':self.assertEqual(record['outcome'],'NATIVE_FAILURE_REQUIRES_REVIEW')
                    elif scenario in ('commit','final_worker','result_timeout','readback_mismatch'):
                        self.assertEqual(record['outcome'],'COMMIT_OUTCOME_UNKNOWN')
                prior=list(calls)
                with self.assertRaises(FileExistsError):run(Session(),job,root/'again',sleep=sleep,clock=lambda:tick[0],timeout=1)
                self.assertEqual(prior,calls)


if __name__=='__main__':unittest.main(verbosity=2)
