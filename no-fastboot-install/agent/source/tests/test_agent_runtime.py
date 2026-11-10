"""Run the production managed child-launch block against an inert runtime check."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True)
    package=parser.parse_args().package.resolve()
    software=Path(__file__).resolve().parents[1]
    source=(software/'Launcher.cs').read_text('utf-8')
    begin=source.index('    var python=Path.Combine(root,')
    end=source.index('\n   }\n  }catch(Exception error)',begin)
    block=source[begin:end]
    manifest=json.loads((package/'app/release.json').read_text('utf-8'))
    with tempfile.TemporaryDirectory(prefix='m4-runtime-contract-') as directory:
        root=Path(directory)/'Unicode 路径 with spaces';root.mkdir()
        shutil.copytree(package/'runtime/python',root/'runtime/python')
        (root/'app').mkdir();(root/'state').mkdir()
        (root/'app/release.json').write_text(json.dumps({k:manifest[k] for k in ('python_sha256','gui_runtime_sha256')}),'utf-8')
        (root/'app/entry.py').write_text('''from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
agent=len(sys.argv)>1 and sys.argv[1]=='agent-worker'
manifest=json.loads((root/'app/release.json').read_text('utf-8'))
expected=manifest['python_sha256' if agent else 'gui_runtime_sha256']
actual=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
(root/'state/result.json').write_text(json.dumps(dict(agent=agent,executable=Path(sys.executable).name,correct=actual==expected)),'utf-8')
raise SystemExit(0 if actual==expected else 1)
''','utf-8')
        fixture='''using System;using System.Diagnostics;using System.IO;
class Fixture {const string ReleaseHash="inert fixture";
[STAThread] static void Main(string[] input){string root=input[0],source=root,common=Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);bool agent=input[1]=="agent";
string[] args=new[]{"--source",root,"--agent-worker",new string('0',32),new string('1',32)};
'''+block+'\n}}'
        code=Path(directory)/'Fixture.cs';exe=Path(directory)/'Fixture.exe';code.write_text(fixture,'utf-8')
        compiler=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        compiled=subprocess.run([str(compiler),'/nologo','/target:winexe','/codepage:65001','/out:'+str(exe),str(code)],
                                capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        if compiled.returncode: raise RuntimeError((compiled.stdout+compiled.stderr).decode('utf-8','replace'))
        rows=[]
        for mode in ('agent','gui'):
            run=subprocess.run([str(exe),str(root),mode],timeout=30)
            value=json.loads((root/'state/result.json').read_text('utf-8'))
            assert run.returncode==0 and value['correct'],value
            assert value['executable'].lower()==('python.exe' if mode=='agent' else 'pythonw.exe'),value
            rows.append(value)
    print(json.dumps(dict(passed=True,checks=rows,device_operations=0),ensure_ascii=False))


if __name__=='__main__':main()
