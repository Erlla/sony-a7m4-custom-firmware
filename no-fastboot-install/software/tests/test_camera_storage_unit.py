"""Run storage ancestry logic against substituted Windows cmdlets, not devices."""
from pathlib import Path
import json
import os
import subprocess
import unittest


@unittest.skipUnless(os.name=='nt','Windows PowerShell storage fixture')
class CameraStorageTests(unittest.TestCase):
    def test_unlabelled_camera_card_and_unrelated_pmhome_are_distinguished(self):
        source=Path(__file__).resolve().parents[1]/'app/driver_restore/camera_storage.ps1'
        script=Path(__file__).with_suffix('.ps1')
        shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        environment=dict(os.environ);environment.pop('PSModulePath',None)
        result=subprocess.run([str(shell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-Source',str(source)],
                              capture_output=True,encoding='utf-8-sig',errors='replace',env=environment,
                              timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertTrue(report['passed']);self.assertEqual(report['cases'],11)
        self.assertEqual(report['device_operations'],0)


if __name__=='__main__':unittest.main(verbosity=2)
