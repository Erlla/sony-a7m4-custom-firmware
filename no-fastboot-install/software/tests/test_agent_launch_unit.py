"""Exercise the exact managed broker with an inert child, never camera code."""
from pathlib import Path
import os
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows local WMI broker fixture')
class IndependentLaunchTests(unittest.TestCase):
    def test_managed_broker_preserves_arguments_environment_and_survives_parent(self):
        software=Path(__file__).resolve().parents[1]
        source=(software/'Launcher.cs').read_text('utf-8')
        start=source.index(' static void LaunchIndependent(')
        end=source.index(' [STAThread] static void Main(',start)
        method=source[start:end]
        prefix='''using System;using System.Collections;using System.Collections.Generic;using System.Diagnostics;
using System.IO;using System.Management;using System.Reflection;using System.Runtime.InteropServices;using System.Text;
class Fixture {
[DllImport("kernel32.dll",SetLastError=true)]static extern bool IsProcessInJob(IntPtr p,IntPtr j,out bool b);
'''
        suffix='''
[STAThread]static void Main(string[] args){
 if(args.Length==1){LaunchIndependent(args[0],new string('0',32),new string('1',32));return;}
 if(args.Length!=6||args[0]!="--source"||args[2]!="--agent-worker"||args[3]!=new string('0',32)||args[4]!=new string('1',32)||args[5]!="--independent")throw new Exception("argument transport failed");
 bool attached;using(var p=Process.GetCurrentProcess())if(!IsProcessInJob(p.Handle,IntPtr.Zero,out attached))throw new Exception("job query failed");
 System.Threading.Thread.Sleep(400);
 File.WriteAllText(args[1],(attached?"attached":"independent")+"|"+Environment.GetEnvironmentVariable("M4_LAUNCH_FIXTURE"),new UTF8Encoding(false));
}}
'''
        with tempfile.TemporaryDirectory(prefix='m4-launch-fixture-') as directory:
            root=Path(directory); code=root/'Fixture.cs'; exe=root/'Fixture.exe'
            report=root/'Unicode 子目录'/'result with spaces.txt';report.parent.mkdir()
            code.write_text(prefix+method+suffix,'utf-8')
            compiler=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
            subprocess.run([str(compiler),'/nologo','/target:winexe','/codepage:65001',
                            '/reference:System.Management.dll','/out:'+str(exe),str(code)],
                           check=True,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
            env=os.environ.copy();env['M4_LAUNCH_FIXTURE']='中文 environment'
            parent=subprocess.run([str(exe),str(report)],env=env,timeout=15)
            self.assertEqual(parent.returncode,0)
            deadline=time.monotonic()+15
            actual=''
            while time.monotonic()<deadline:
                if report.is_file(): actual=report.read_text('utf-8')
                if actual: break
                time.sleep(0.05)
            self.assertEqual(actual,'independent|中文 environment')


if __name__=='__main__':unittest.main(verbosity=2)
