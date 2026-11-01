"""Run first-use setup against empty, isolated Windows state substitutes."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,required=True)
    root=parser.parse_args().package.resolve(strict=True)
    for name in ('app','app/provider','app/workflow'):
        sys.path.insert(0,str(root/name))
    with tempfile.TemporaryDirectory(prefix='m4-setup-input-') as temporary:
        prior=os.environ.get('M4_TOOL_DATA_ROOT')
        os.environ['M4_TOOL_DATA_ROOT']=temporary
        try:
            spec=importlib.util.spec_from_file_location('clean_setup_bundle',root/'app/driver/prepare_bundle.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            bundle=module.prepare()
            shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
            command=[str(shell),'-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',
                     str(Path(__file__).with_name('test_clean_setup.ps1')),'-Package',str(root),'-Bundle',bundle['bundle']]
            environment=os.environ.copy();environment.pop('PSModulePath',None)
            result=subprocess.run(command,capture_output=True,encoding='utf-8-sig',errors='replace',env=environment,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            report=json.loads(result.stdout.strip())
            assert report['passed'] and report['full_installer_exercised'] and report['full_enrollment_exercised']
            print(json.dumps(report))
        finally:
            if prior is None:os.environ.pop('M4_TOOL_DATA_ROOT',None)
            else:os.environ['M4_TOOL_DATA_ROOT']=prior


if __name__=='__main__':main()
