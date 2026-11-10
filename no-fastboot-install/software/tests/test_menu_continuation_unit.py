"""Real continuation/proof modules with inert files and replaced hardware boundaries."""
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest

APP=Path(__file__).resolve().parents[1]/'app'
sys.path.insert(0,str(APP))

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'flow';self.folder.mkdir()
        self.value=dict(flow='a'*32,phase='MENU_CONNECTION_STOPPED',patch_run='p1-run',p1_operation_complete=True)
        def require(ok,message):
            if not ok:raise ValueError(message)
        def read(path):return json.loads(Path(path).read_text('utf-8'))
        def atomic(path,value):
            Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(value),'utf-8')
        def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        def menu(value):return self.folder/'menu_attempts'/value['menu_attempt'] if value.get('menu_attempt') else self.folder
        def save(value,phase,**fields):value.update(phase=phase,**fields);atomic(self.folder/'flow.json',value);return value
        self.read,self.atomic,self.sha=read,atomic,sha
        module=ModuleType('inert_menu_controller');module.__file__=str(self.root/'controller.py')
        Path(module.__file__).write_text('# inert controller identity','utf-8')
        self.evidence=dict(accepted_run='p1-run',receiver_p1_sha256='1'*64)
        module.receiver_evidence=lambda:self.evidence.copy()
        controller=SimpleNamespace(__module__=module.__name__)
        self.patch_record=dict(run='p1-run',phase='P1_COMPLETE',driver_policy='retain',p1_operation_complete=True,read_verified=True,session_ended=True)
        backend=SimpleNamespace(ROOT=self.root,STATE=self.root/'patch',read=read,atomic=atomic,sha=sha,require=require,
            frozen=SimpleNamespace(Journal=lambda _:SimpleNamespace(load=lambda:self.patch_record)))
        flow=SimpleNamespace(folder=lambda value:self.folder,menu_folder=menu,save=save,trial=lambda value:controller)
        self.restores=[]
        restore=SimpleNamespace(recover=lambda:(self.restores.append('restore') or dict(phase='USB_RESTORE_COMPLETE',message='verified')))
        self.stack=patch.dict(sys.modules,{'integrity_backend':backend,'wizard':flow,
                                         'standalone_usb_restore':restore,module.__name__:module})
        self.stack.start();self.addCleanup(self.stack.stop)
        self.recovery=load('test_menu_recovery_real',APP/'workflow/menu_connection_recovery.py')
        sys.modules['menu_connection_recovery']=self.recovery
        self.addCleanup(sys.modules.pop,'menu_connection_recovery',None)
        self.continuation=load('test_menu_continuation_real',APP/'workflow/menu_continuation.py')
        self.plan=dict(nonce='old-nonce',patch_only=True,job=str(self.root/'window'),pre_window_reader=dict(job=str(self.root/'reader')),
                       sources={'controller.py':sha(module.__file__)},receiver=dict(receiver_p1_sha256='1'*64))
        atomic(self.folder/'plan.json',self.plan)
        self.status=dict(nonce='old-nonce',plan_sha256=sha(self.folder/'plan.json'),runner_sha256=sha(module.__file__),
                         stopped_before_session=True,safe_to_restore=True,window_started=False,preread_started=False,installation_may_be_running=False)
        atomic(self.folder/'status.json',self.status)
        self.old={n:(self.folder/n).read_bytes() for n in ('plan.json','status.json')}

    def test_recover_then_continue_preserves_original_evidence(self):
        result=self.recovery.recover(self.value)
        self.assertEqual(result['phase'],'MENU_CONTINUATION_READY');self.assertTrue(result['normal_usb_restored'])
        ready=self.continuation.prepare(result)
        self.assertEqual(ready['patch_run'],'p1-run');self.assertEqual(ready['phase'],'PATCH_READY')
        receipt=self.read(self.folder/'menu_attempts'/ready['menu_attempt']/'continuation.json')
        self.assertFalse(receipt['p1_write_authorized']);self.assertEqual(self.restores,['restore'])
        for name,data in self.old.items():self.assertEqual((self.folder/name).read_bytes(),data)
        with self.assertRaises(ValueError):self.continuation.prepare(ready)

    def test_active_or_unknown_session_never_restores(self):
        for key,wrong in [('stopped_before_session',False),('safe_to_restore',False),('window_started',True),('preread_started',True),('installation_may_be_running',True)]:
            with self.subTest(key=key):
                self.atomic(self.folder/'status.json',dict(self.status,**{key:wrong}))
                self.assertIsNone(self.recovery.recover(self.value))
        self.assertEqual(self.restores,[])

    def test_claimed_reader_or_window_rejects_continuation(self):
        for name in ('window','reader'):
            folder=self.root/name;folder.mkdir();(folder/'claim.json').write_text('{}','utf-8')
            with self.assertRaisesRegex(ValueError,'已有执行记录'):self.recovery.recover(self.value)
            (folder/'claim.json').unlink()
        self.assertEqual(self.restores,[])

    def test_changed_plan_is_not_trusted(self):
        self.atomic(self.folder/'plan.json',dict(self.plan,nonce='tampered'))
        with self.assertRaisesRegex(ValueError,'记录与计划不一致'):self.recovery.recover(self.value)
        self.assertEqual(self.restores,[])

    def test_patch_from_another_run_or_changed_target_is_rejected(self):
        for fields in (dict(accepted_run='other'),dict(receiver_p1_sha256='2'*64)):
            self.evidence.update(fields)
            with self.assertRaises(ValueError):self.recovery.recover(self.value)
            self.evidence.update(accepted_run='p1-run',receiver_p1_sha256='1'*64)
        self.assertEqual(self.restores,[])

    def test_unfinished_p1_is_rejected(self):
        self.patch_record['session_ended']=False
        with self.assertRaisesRegex(ValueError,'p1 检查尚未完成'):self.recovery.recover(self.value)
        self.assertEqual(self.restores,[])

    def test_storage_flag_alone_cannot_enable_continue(self):
        self.value.update(phase='MENU_CONTINUATION_READY',normal_usb_restored=False)
        with self.assertRaisesRegex(ValueError,'普通 USB'):self.continuation.prepare(self.value)

    def recheck(self, observed='WinUSB', failure=None):
        self.check_calls=[]
        owner=self
        class Provider:
            def check(self):owner.check_calls.append('assets')
            def wait_communication(self,folder,timeout):
                owner.check_calls.append(('observe',timeout))
                if failure:raise failure
                return None if observed is None else (owner.root,dict(driver=observed))
            def tasks_clear(self,snapshot):owner.check_calls.append('tasks')
            def same_body(self,state):owner.check_calls.append('same-body');return state
            def communication_driver(self,row):
                owner.check_calls.append('driver');return row['driver']
        with patch.dict(sys.modules,{'user_provider':SimpleNamespace(Provider=Provider),
                                    'driver_restart':SimpleNamespace(require_ready=lambda:owner.check_calls.append('restart'))}):
            return self.continuation.recheck(self.value)

    def test_available_retained_driver_continues_without_restore_or_p1_writer(self):
        result=self.recheck()
        self.assertEqual(result['phase'],'PATCH_READY')
        self.assertEqual(result['patch_run'],'p1-run')
        self.assertFalse(result.get('normal_usb_restored',False))
        self.assertFalse(result['p1_rewrite_required'])
        self.assertEqual(self.restores,[])
        self.assertEqual(self.check_calls,['restart','assets',('observe',30),'tasks','same-body','driver'])
        receipt=self.read(self.folder/'menu_attempts'/result['menu_attempt']/'continuation.json')
        self.assertEqual(receipt['connection'],'WinUSB');self.assertFalse(receipt['p1_write_authorized'])
        for name,data in self.old.items():self.assertEqual((self.folder/name).read_bytes(),data)

    def test_no_device_wait_does_not_create_attempt_or_claim_menu_ready(self):
        result=self.recheck(observed=None)
        self.assertEqual(result['phase'],'MENU_CONNECTION_STOPPED')
        self.assertEqual(result['diagnostic']['code'],'MENU_COMMUNICATION_PENDING')
        self.assertNotIn('menu_attempt',result);self.assertFalse(result['final_unplug_ready'])
        self.assertFalse((self.folder/'menu_attempts').exists())
        self.assertEqual(self.restores,[])

    def test_unknown_or_active_session_cannot_even_probe_connection(self):
        self.atomic(self.folder/'status.json',dict(self.status,preread_started=True))
        with self.assertRaisesRegex(ValueError,'证据不完整'):self.recheck()
        self.assertEqual(self.check_calls,[])

    def test_connection_failure_keeps_original_error_and_attempt(self):
        with self.assertRaisesRegex(RuntimeError,'wrong body'):self.recheck(failure=RuntimeError('wrong body'))
        self.assertEqual(self.value['phase'],'MENU_CONNECTION_STOPPED')
        self.assertIn('wrong body',self.value['diagnostic']['original_error'])
        self.assertNotIn('menu_attempt',self.value)

if __name__=='__main__':unittest.main()
