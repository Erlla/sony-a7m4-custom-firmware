"""Host polling and desktop routing tests with no device or privileged boundary."""
import ast
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]

def require(ok,message):
    if not ok:raise ValueError(message)

class WaitTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'app/workflow/user_provider.py'
        tree=ast.parse(path.read_text('utf-8-sig'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Provider')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='wait_communication')
        env=dict(require=require)
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),env)
        self.wait=env['wait_communication'];self.calls=[]

    def execute(self,normal,service):
        state=dict(normal_count=normal,service_count=service)
        def snapshot(folder,**kwargs):self.calls.append(('snapshot',kwargs));return 'receipt',state
        def same_body(value):self.calls.append(('same-body',value))
        return self.wait(SimpleNamespace(snapshot=snapshot,same_body=same_body),'folder',timeout=30)

    def test_one_host_wait_then_one_body_check(self):
        result=self.execute(1,0)
        self.assertEqual(result[0],'receipt')
        self.assertEqual(self.calls[0],('snapshot',dict(connection_only=True,wait_seconds=30)))
        self.assertEqual(len(self.calls),2)

    def test_service_or_absent_never_claim_ready_or_reinstall(self):
        for service in (0,1):
            self.calls=[]
            self.assertIsNone(self.execute(0,service));self.assertEqual(len(self.calls),1)

    def test_ambiguous_identity_rejected(self):
        for normal,service in ((2,0),(1,1),(0,2)):
            with self.subTest(normal=normal,service=service),self.assertRaises(ValueError):self.execute(normal,service)

    @unittest.skipUnless(sys.platform=='win32','Windows PowerShell fixture')
    def test_real_powershell_wait_uses_inert_enumeration_and_no_storage(self):
        result=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive',
            '-ExecutionPolicy','Bypass','-File',str(ROOT/'tests/test_communication_snapshot.ps1'),
            '-Package',str(ROOT)],capture_output=True,encoding='utf-8',errors='replace',timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('"device_operations":0',result.stdout)

class DesktopTests(unittest.TestCase):
    def presentation(self,value):
        path=ROOT/'app/ui/simple_app.py';tree=ast.parse(path.read_text('utf-8-sig'))
        nodes=[n for n in tree.body if isinstance(n,ast.Assign)]
        nodes += [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='presentation']
        env=dict(diagnostic_summary=lambda d:(d or {}).get('message',''))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
        return env['presentation'](value)

    def test_menu_connection_failure_never_routes_to_patch_start(self):
        self.assertEqual(self.presentation(dict(phase='MENU_CONNECTION_STOPPED'))[3],'simple-continue')
        self.assertEqual(self.presentation(dict(phase='MENU_CONNECTION_STOPPED',preread_failure_cleaned=True))[3],'simple-recover-usb')

    def test_pending_and_unknown_do_not_offer_installation(self):
        for phase in ('REVIEW_REQUIRED','MENU_CONNECTION_STOPPED','MENU_CONNECTION_RECOVERY','HANDOFF_NOT_READY'):
            self.assertNotIn('可以拔下',self.presentation(dict(phase=phase))[0])

if __name__=='__main__':unittest.main()
