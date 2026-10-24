using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]
[assembly: AssemblyInformationalVersion("1.00")]

internal static class Launcher {
  static string Digest(string path) {
    using (var stream=File.OpenRead(path)) using (var sha=SHA256.Create())
      return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
  }
  [STAThread] static void Main(string[] args) {
    bool verify=args.Length==1 && args[0]=="--verify";
    Application.EnableVisualStyles();
    try {
      string root=AppDomain.CurrentDomain.BaseDirectory;
      string python=Path.Combine(root,"runtime","python","pythonw.exe");
      string entry=Path.Combine(root,"app","entry.py");
      string manifest=Path.Combine(root,"app","release.json");
      if (Digest(python)!="@PYTHON@" || Digest(entry)!="@ENTRY@" || Digest(manifest)!="@RELEASE@")
        throw new Exception("软件文件不完整或已改变，请重新完整解压。");
      if(verify) python=Path.Combine(root,"runtime","python","python.exe");
      var start=new ProcessStartInfo(python,"-I -s -B -X utf8 \""+entry+"\""+(verify?" --check":""));
      start.WorkingDirectory=root; start.UseShellExecute=false; start.CreateNoWindow=true;
      start.EnvironmentVariables.Remove("PYTHONPATH"); start.EnvironmentVariables.Remove("PYTHONHOME");
      if(verify) {
        start.RedirectStandardOutput=true;start.RedirectStandardError=true;
        using(var child=Process.Start(start)) {
          string result=child.StandardOutput.ReadToEnd();string error=child.StandardError.ReadToEnd();
          child.WaitForExit();if(child.ExitCode!=0)throw new Exception(error);
          string state=Path.Combine(root,"state");Directory.CreateDirectory(state);
          File.WriteAllText(Path.Combine(state,"launcher_verify.json"),result);
        }
      } else Process.Start(start);
    } catch(Exception error) {
      if(verify) {Environment.ExitCode=1;Console.Error.WriteLine(error.Message);}
      else MessageBox.Show(error.Message,"M4 相机工具",MessageBoxButtons.OK,MessageBoxIcon.Error);
    }
  }
}
