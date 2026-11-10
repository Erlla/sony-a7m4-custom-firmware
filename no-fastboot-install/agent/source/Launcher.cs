using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Reflection;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
[assembly: AssemblyVersion("@ASSEMBLY_VERSION@")]
[assembly: AssemblyFileVersion("@ASSEMBLY_VERSION@")]
[assembly: AssemblyInformationalVersion("@VERSION@")]
internal static class Launcher {
 [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError=true)]
 static extern bool IsProcessInJob(IntPtr process,IntPtr job,out bool result);
 const string ReleaseHash="@RELEASE@";
 static readonly SecurityIdentifier Admin=new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid,null);
 static readonly SecurityIdentifier SystemSid=new SecurityIdentifier(WellKnownSidType.LocalSystemSid,null);
 static readonly string[] Groups={"app","runtime","vendor","tools","licenses"};
 static string Digest(Stream input) {
  input.Position=0;
  using(var sha=SHA256.Create()) {
   string value=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();
   input.Position=0;return value;
  }
 }
 static void NoLink(string path) {
  if((File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new Exception("程序目录不能包含联接或符号链接。");
 }
 static string Relative(string root,string name) {
  if(name.Contains(":")||name.Contains("\\")||name.StartsWith("/")||Array.Exists(name.Split('/'),p=>p==".."||p=="."||p==""))
   throw new Exception("发布清单路径无效。");
  string path=Path.GetFullPath(Path.Combine(root,name.Replace('/',Path.DirectorySeparatorChar)));
  if(!path.StartsWith(Path.GetFullPath(root).TrimEnd('\\')+"\\",StringComparison.OrdinalIgnoreCase))throw new Exception("清单路径越界。");
  return path;
 }
 sealed class Checked:IDisposable {
  internal string Root;
  internal Dictionary<string,object> Files;
  internal Dictionary<string,FileStream> Streams=new Dictionary<string,FileStream>(StringComparer.OrdinalIgnoreCase);
  public void Dispose(){foreach(var stream in Streams.Values)stream.Dispose();Streams.Clear();}
  internal void Read(string name,string hash) {
   string path=Relative(Root,name);NoLink(path);
   var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);
   try {
    if(Digest(stream)!=hash)throw new Exception("软件文件已改变："+name);
    Streams.Add(name,stream);
   }catch{stream.Dispose();throw;}
  }
 }
 static Dictionary<string,object> Manifest(string root) {
  string path=Relative(root,"app/release.json");NoLink(path);
  using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read)) {
   if(Digest(stream)!=ReleaseHash)throw new Exception("发布清单已改变，请重新完整解压。");
   using(var reader=new StreamReader(stream,Encoding.UTF8))return new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd());
  }
 }
 static IEnumerable<string> Directories(string root) {
  var pending=new Stack<string>();pending.Push(root);
  while(pending.Count>0) {
   string directory=pending.Pop();NoLink(directory);yield return directory;
   foreach(string child in Directory.GetDirectories(directory)) {NoLink(child);pending.Push(child);}
  }
 }
 static Checked Verify(string root) {
  var result=new Checked();result.Root=root;
  try {
   NoLink(root);var manifest=Manifest(root);
   if((string)manifest["schema"]!="m4-clean-product-release/1"||(string)manifest["version"]!="@VERSION@")throw new Exception("软件清单不匹配。");
   result.Files=(Dictionary<string,object>)manifest["files"];result.Read("app/release.json",ReleaseHash);
   foreach(var pair in result.Files)result.Read(pair.Key,(string)pair.Value);
   foreach(string group in Groups) {
    string folder=Path.Combine(root,group);NoLink(folder);
    foreach(string directory in Directories(folder))
    foreach(string file in Directory.GetFiles(directory)) {
     NoLink(file);
     string name=file.Substring(root.TrimEnd('\\').Length+1).Replace('\\','/');
     if(name!="app/release.json"&&!result.Files.ContainsKey(name))throw new Exception("程序目录包含清单外文件："+name);
    }
   }
   foreach(string file in Directory.GetFiles(root)) {
    string extension=Path.GetExtension(file).ToLowerInvariant();
    if(extension==".dll"||extension==".pyd"||extension==".py"||extension==".pyw"||extension==".pth"||extension==".config")
     if(!result.Files.ContainsKey(Path.GetFileName(file)))throw new Exception("根目录包含未验证的执行配置。");
   }
   if(Digest(result.Streams["runtime/python/python.exe"])!="@PYTHON_EXE@"||
      Digest(result.Streams["runtime/python/pythonw.exe"])!="@PYTHON@"||
      Digest(result.Streams["app/entry.py"])!="@ENTRY@")throw new Exception("解释器或启动入口不匹配。");
   return result;
  }catch{result.Dispose();throw;}
 }
 static bool Trusted(IdentityReference owner){return owner.Value==Admin.Value||owner.Value==SystemSid.Value;}
 static void CheckAcl(string path,bool directory) {
  NoLink(path);
  FileSystemSecurity acl=directory?(FileSystemSecurity)Directory.GetAccessControl(path):File.GetAccessControl(path);
  if(!Trusted(acl.GetOwner(typeof(SecurityIdentifier))))throw new Exception("运行文件所有者不可信。");
  FileSystemRights write=FileSystemRights.Write|FileSystemRights.Delete|FileSystemRights.DeleteSubdirectoriesAndFiles|
   FileSystemRights.ChangePermissions|FileSystemRights.TakeOwnership;
  foreach(FileSystemAccessRule rule in acl.GetAccessRules(true,true,typeof(SecurityIdentifier)))
   if(rule.AccessControlType==AccessControlType.Allow&&(rule.FileSystemRights&write)!=0&&!Trusted(rule.IdentityReference))
    throw new Exception("运行文件允许普通用户写入。");
 }
 static void SecureDirectory(string path,SecurityIdentifier user) {
  if(Directory.Exists(path)){CheckAcl(path,true);return;}
  var acl=new DirectorySecurity();acl.SetAccessRuleProtection(true,false);acl.SetOwner(Admin);
  foreach(var sid in new[]{Admin,SystemSid})acl.AddAccessRule(new FileSystemAccessRule(sid,FileSystemRights.FullControl,
    InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
  acl.AddAccessRule(new FileSystemAccessRule(user,FileSystemRights.ReadAndExecute,
   InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
  Directory.CreateDirectory(path,acl);CheckAcl(path,true);
 }
 static FileSecurity FileAcl(SecurityIdentifier user) {
  var acl=new FileSecurity();acl.SetAccessRuleProtection(true,false);acl.SetOwner(Admin);
  foreach(var sid in new[]{Admin,SystemSid})acl.AddAccessRule(new FileSystemAccessRule(sid,FileSystemRights.FullControl,AccessControlType.Allow));
  acl.AddAccessRule(new FileSystemAccessRule(user,FileSystemRights.ReadAndExecute,AccessControlType.Allow));
  return acl;
 }
 static void CheckTree(string root) {
  CheckAcl(root,true);
  foreach(string directory in Directories(root)) {
   CheckAcl(directory,true);foreach(string path in Directory.GetFiles(directory))CheckAcl(path,false);
  }
 }
 static string Snapshot(string source,SecurityIdentifier user,string common) {
  string parent=Path.Combine(common,"M4CameraToolRuntime");SecureDirectory(parent,user);
  parent=Path.Combine(parent,user.Value);SecureDirectory(parent,user);
  string target=Path.Combine(parent,ReleaseHash);
  if(Directory.Exists(target)){CheckTree(target);return target;}
  string stage=target+".stage-"+Guid.NewGuid().ToString("N");
  using(var verified=Verify(source)) {
   SecureDirectory(stage,user);
   foreach(var item in verified.Streams) {
    string output=Relative(stage,item.Key);
    var missing=new Stack<string>();string directory=Path.GetDirectoryName(output);
    while(!Directory.Exists(directory)){missing.Push(directory);directory=Path.GetDirectoryName(directory);}
    CheckAcl(directory,true);while(missing.Count>0)SecureDirectory(missing.Pop(),user);
    using(var destination=new FileStream(output,FileMode.CreateNew,FileSystemRights.Write,FileShare.None,65536,FileOptions.None,FileAcl(user))) {
     item.Value.Position=0;item.Value.CopyTo(destination);destination.Flush(true);
    }
    CheckAcl(output,false);
   }
  }
  CheckTree(stage);
  try{Directory.Move(stage,target);}
  catch(IOException){if(!Directory.Exists(target))throw;CheckTree(target);}
  return target;
 }
 static void LaunchIndependent(string source,string job,string dispatch) {
  // Local WMI is a Windows process broker, not a persistent task. Its own
  // quota job must also be left; the child rechecks independence before USB.
  var values=new SortedDictionary<string,string>(StringComparer.OrdinalIgnoreCase);
  foreach(DictionaryEntry pair in Environment.GetEnvironmentVariables())values[(string)pair.Key]=(string)pair.Value;
  values["SystemRoot"]=Environment.GetFolderPath(Environment.SpecialFolder.Windows);
  values["WINDIR"]=values["SystemRoot"];
  values["ProgramData"]=Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
  var environment=new List<string>();foreach(var pair in values)environment.Add(pair.Key+"="+pair.Value);
  using(var startupClass=new ManagementClass("Win32_ProcessStartup"))
  using(var startup=startupClass.CreateInstance())
  using(var process=new ManagementClass("Win32_Process"))
  using(var input=process.GetMethodParameters("Create")) {
   startup["ShowWindow"]=(ushort)0;
   startup["CreateFlags"]=(uint)(0x01000000|0x08000000|0x00000400);
   startup["EnvironmentVariables"]=environment.ToArray();
   string self=Assembly.GetExecutingAssembly().Location;
   input["CommandLine"]="\""+self+"\" --source \""+source+"\" --agent-worker "+job+" "+dispatch+" --independent";
   input["CurrentDirectory"]=Path.GetDirectoryName(self);
   input["ProcessStartupInformation"]=startup;
   using(var result=process.InvokeMethod("Create",input,null)) {
    uint code=Convert.ToUInt32(result["ReturnValue"]);
    if(code!=0)throw new Exception("Windows 独立后台启动失败，WMI 返回 "+code+"；未开始相机操作。");
   }
  }
 }
 [STAThread] static void Main(string[] args) {
  Application.EnableVisualStyles();
  try {
   if(args.Length<2||args[0]!="--source")throw new Exception("请通过 M4相机工具.exe 启动。");
   string source=Path.GetFullPath(args[1]).TrimEnd('\\');
   bool agent=(args.Length==5||args.Length==6)&&args[2]=="--agent-worker";
   if(args.Length!=2&&!agent)throw new Exception("Invalid launcher arguments");
   if(args.Length==6&&args[5]!="--independent")throw new Exception("Invalid independent launcher arguments");
   if(agent&&(!System.Text.RegularExpressions.Regex.IsMatch(args[3],"\\A[0-9a-f]{32}\\z")||
              !System.Text.RegularExpressions.Regex.IsMatch(args[4],"\\A[0-9a-f]{32}\\z")))throw new Exception("Invalid agent identity");
   Manifest(source);
   var identity=WindowsIdentity.GetCurrent();
   if(!new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator))throw new Exception("启动器尚未获得管理员授权。");
   if(agent){bool attached;using(var self=Process.GetCurrentProcess()){
    if(!IsProcessInJob(self.Handle,IntPtr.Zero,out attached))throw new Win32Exception();
    if(attached){
     if(args.Length==6)throw new Exception("Windows 独立后台仍受进程作业约束，未开始相机操作。");
     LaunchIndependent(source,args[3],args[4]);return;
    }
   }}
   string common=Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
   string coordination=Path.Combine(common,"M4CameraToolRecovery");SecureDirectory(coordination,identity.User);
   coordination=Path.Combine(coordination,identity.User.Value);SecureDirectory(coordination,identity.User);
   SecureDirectory(Path.Combine(coordination,"operations"),identity.User);
   string root=Snapshot(source,identity.User,common);
   using(var verified=Verify(root)) {
    var python=Path.Combine(root,"runtime","python",agent?"python.exe":"pythonw.exe");var entry=Path.Combine(root,"app","entry.py");
    var start=new ProcessStartInfo(python,"-I -s -B -X utf8 \""+entry+"\""+(agent?" agent-worker "+args[3]+" "+args[4]:""));
    start.WorkingDirectory=root;start.UseShellExecute=false;start.CreateNoWindow=true;
    start.EnvironmentVariables.Remove("PYTHONPATH");start.EnvironmentVariables.Remove("PYTHONHOME");
    start.EnvironmentVariables["ProgramData"]=common;
    start.EnvironmentVariables["SystemRoot"]=Environment.GetFolderPath(Environment.SpecialFolder.Windows);
    start.EnvironmentVariables["WINDIR"]=Environment.GetFolderPath(Environment.SpecialFolder.Windows);
    start.EnvironmentVariables["M4_TOOL_DATA_ROOT"]=Path.Combine(source,"state");
    start.EnvironmentVariables["M4_TOOL_SOURCE_ROOT"]=source;
    start.EnvironmentVariables["M4_RUNTIME_MANIFEST_SHA256"]=ReleaseHash;
    using(var child=Process.Start(start)){child.WaitForExit();Environment.ExitCode=child.ExitCode;}
   }
  }catch(Exception error) {
   Environment.ExitCode=1;
   if((args.Length==5||args.Length==6)&&args[2]=="--agent-worker"&&
      System.Text.RegularExpressions.Regex.IsMatch(args[3],"\\A[0-9a-f]{32}\\z")&&
      System.Text.RegularExpressions.Regex.IsMatch(args[4],"\\A[0-9a-f]{32}\\z")) {
    // Fixed local report only; never accept an output path from command arguments.
    try {
     string path=Path.Combine(Path.GetFullPath(args[1]),"state","agent","jobs",args[3]);
     for(string p=path;p!=null;p=Path.GetDirectoryName(p))NoLink(p);
     File.WriteAllText(Path.Combine(path,"launch-error.json"),new JavaScriptSerializer().Serialize(
       new {schema="m4-agent-launch-error/1",dispatch=args[4],message=error.Message}),new UTF8Encoding(false));
    }catch{}
   }else MessageBox.Show(error.Message,"M4 相机工具",MessageBoxButtons.OK,MessageBoxIcon.Error);
  }
 }
}
