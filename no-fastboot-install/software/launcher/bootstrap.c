/* Native trust root: no CLR, Python, CRT or application-directory DLL imports.
 * Only kernel32 is imported; other system DLLs load by absolute System32 path.
 * The managed launcher is embedded and runs only from a protected exact directory.
 */
typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef unsigned short W;
typedef void* H;
#define API __declspec(dllimport)
API u32 GetModuleFileNameW(H,W*,u32);API W*GetCommandLineW(void);
API H CreateFileW(const W*,u32,u32,void*,u32,u32,H);
API int ReadFile(H,void*,u32,u32*,void*);API int WriteFile(H,const void*,u32,u32*,void*);
API int CloseHandle(H);API void ExitProcess(u32);API u32 GetLastError(void);
API u32 GetFileAttributesW(const W*);API int CreateDirectoryW(const W*,void*);
API H GetProcessHeap(void);API void*HeapAlloc(H,u32,u64);API int HeapFree(H,u32,void*);
API H LoadLibraryExW(const W*,H,u32);API void*GetProcAddress(H,const char*);
API u32 GetSystemDirectoryW(W*,u32);API H LocalFree(H);
API H FindFirstFileW(const W*,void*);API int FindNextFileW(H,void*);API int FindClose(H);
API int CreateProcessW(const W*,W*,void*,void*,int,u32,void*,const W*,void*,void*);
API u32 WaitForSingleObject(H,u32);API int GetExitCodeProcess(H,u32*);
API H GetStdHandle(u32);
API W*GetEnvironmentStringsW(void);API int FreeEnvironmentStringsW(W*);
API int SetEnvironmentVariableW(const W*,const W*);
void*memset(void*p,int c,u64 n){u8*b=p;while(n--)*b++=(u8)c;return p;}
void*memcpy(void*p,const void*q,u64 n){u8*a=p;const u8*b=q;while(n--)*a++=*b++;return p;}
#include "sha256.h"
#include "bootstrap_payload.h"
static W root[32768],path[32768],scratch[32768],command[32768];
static H leases[FILE_COUNT+67];static u32 lease_count;
static u8 buffer[65536];static u32 failed;
typedef struct {u32 attrs;u32 times[6],sizehi,sizelo,reserved[2];W name[260],alternate[14];} FindData;
typedef struct {u32 size,mask;H window;const W*verb,*file,*args,*directory;int show;H instance,idlist;const W*class_name;H key;u32 hotkey;H icon,process;} ShellInfo;
typedef struct {u32 size;W*reserved,*desktop,*title;u32 x,y,cx,cy,xchars,ychars,fill,flags;unsigned short show,reserved_size;u8*reserved_data;H in,out,err;} Startup;
typedef struct {H process,thread;u32 pid,tid;} Process;
typedef struct {u32 size;void*descriptor;int inherit;} SecurityAttrs;
typedef int(*ConvertSD)(const W*,u32,void**,u32*);
typedef u32(*GetSecurity)(W*,int,u32,void**,void**,void**,void**,void**);
typedef int(*EqualSidFn)(void*,void*);
typedef int(*GetAceFn)(void*,u32,void**);
typedef int(*ConvertSidFn)(const W*,void**);
static ConvertSD convert_sd;static GetSecurity get_security;
static EqualSidFn equal_sid;static GetAceFn get_ace;
static void*admin_sid,*system_sid;
static u32 wlen(const W*s){u32 n=0;while(s[n])n++;return n;}
static void copy(W*d,const W*s){while((*d++=*s++));}
static void append(W*d,const W*s){copy(d+wlen(d),s);}
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return (u8)*a-(u8)*b;}
static int weq(const W*a,const W*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static W upper(W c){return c>='a'&&c<='z'?c-32:c;}
static int wi_eq(const W*a,const W*b){while(*a&&upper(*a)==upper(*b)){a++;b++;}return *a==*b;}
static int prefix(const W*a,const W*b){while(*b)if(upper(*a++)!=*b++)return 0;return 1;}
static int clean_environment(void){
 W*all=GetEnvironmentStringsW();if(!all)return 0;int ok=1;
 for(W*p=all;*p;){W*start=p;while(*p)p++;p++;W name[512];u32 n=0;
  while(start[n]&&start[n]!='='&&n<511){name[n]=start[n];n++;}name[n]=0;
  const W*blocked[]={(W*)L"COR_",(W*)L"CORECLR_",(W*)L"COMPLUS_",(W*)L"APPDOMAIN_MANAGER_",(W*)L"DOTNET_",(W*)L"PYTHON",(W*)L"TCL_",(W*)L"TK_"};
  int remove=wi_eq(name,(W*)L"DEVPATH");for(u32 i=0;i<8;i++)if(prefix(name,blocked[i]))remove=1;
  if(remove&&!SetEnvironmentVariableW(name,0))ok=0;
 }
 FreeEnvironmentStringsW(all);return ok;
}
static void ascii(W*d,const char*s){while(*s)*d++=(W)(u8)*s++;*d=0;}
static H system_dll(const W*name){W p[512];if(!GetSystemDirectoryW(p,480))return 0;append(p,(W*)L"\\");append(p,name);return LoadLibraryExW(p,0,0x800);}
static void error(void){
 H user=system_dll((W*)L"user32.dll");if(user){typedef int(*Message)(H,const W*,const W*,u32);
 Message show=(Message)GetProcAddress(user,"MessageBoxW");if(show)show(0,(W*)L"软件完整性或运行目录检查未通过。请完整解压可信安装包后重试。",(W*)L"M4 相机工具",0x10);}
 ExitProcess(1);
}
static void no_link(const W*p){u32 a=GetFileAttributesW(p);if(a==0xffffffff||(a&0x400))failed=1;}
static int hold_parents(const W*directory){
 W parent[32768];copy(parent,directory);
 for(u32 depth=0;depth<64;depth++){
  no_link(parent);if(failed)return 0;
  H handle=CreateFileW(parent,1,3,0,3,0x02000000,0);
  if(handle==(H)-1)return 0;leases[lease_count++]=handle;
  u32 length=wlen(parent);if(length<=3)return 1;
  while(length&&parent[length-1]!='\\')length--;
  if(length<3)return 0;parent[length==3?3:length-1]=0;
 }
 return 0;
}
static int same_hash(const u8*raw,const char*hex){
 for(u32 i=0;i<32;i++){u32 h=(hex[i*2]>='a'?hex[i*2]-'a'+10:hex[i*2]-'0');
 u32 l=(hex[i*2+1]>='a'?hex[i*2+1]-'a'+10:hex[i*2+1]-'0');
 if(raw[i]!=(h*16+l))return 0;}return 1;
}
static int check_file(const W*p,const char*hash){
 no_link(p);if(failed)return 0;
 H file=CreateFileW(p,0x80000000,1,0,3,0x80,0);if(file==(H)-1)return 0;
 struct Sha256 sha;sha_init(&sha);u32 count;u8 digest[32];
 for(;;){if(!ReadFile(file,buffer,sizeof(buffer),&count,0)){CloseHandle(file);return 0;}
 if(!count)break;sha_update(&sha,buffer,count);}
 sha_final(&sha,digest);if(!same_hash(digest,hash)){CloseHandle(file);return 0;}
 leases[lease_count++]=file;return 1;
}
typedef int(*ToWide)(u32,u32,const char*,int,W*,int);
typedef int(*ToUtf8)(u32,u32,const W*,int,char*,int,const char*,int*);
static ToWide to_wide;static ToUtf8 to_utf8;
static int known(const char*name){int lo=0,hi=FILE_COUNT-1;
 while(lo<=hi){int mid=(lo+hi)/2;int order=eq(name,files[mid].name);if(!order)return 1;if(order<0)hi=mid-1;else lo=mid+1;}return 0;}
static void join_relative(const W*relative,W*out){copy(out,root);append(out,(W*)L"\\");append(out,relative);}
static int scan(W*relative,u32 depth){
 if(depth>24)return 0;W full[2048];join_relative(relative,full);no_link(full);if(failed)return 0;
 append(full,(W*)L"\\*");FindData data;H finder=FindFirstFileW(full,&data);if(finder==(H)-1)return 0;
 int valid=1;u32 old=wlen(relative);
 do {
  if(weq(data.name,(W*)L".")||weq(data.name,(W*)L".."))continue;
  if(data.attrs&0x400){valid=0;break;}
  if(old+wlen(data.name)+2>=1900){valid=0;break;}
  append(relative,(W*)L"\\");append(relative,data.name);
  if(data.attrs&0x10){if(!scan(relative,depth+1)){valid=0;break;}}
  else {
   char utf8[8192];if(!to_utf8(65001,0,relative,-1,utf8,sizeof(utf8),0,0)){valid=0;break;}
   for(char*p=utf8;*p;p++)if(*p=='\\')*p='/';
   if(!known(utf8)){valid=0;break;}
  }
  relative[old]=0;
 }while(FindNextFileW(finder,&data));
 relative[old]=0;FindClose(finder);return valid;
}
static int verify_source(void){
 no_link(root);if(failed)return 0;
 for(u32 i=0;i<FILE_COUNT;i++){
  W relative[2048];if(!to_wide(65001,0,files[i].name,-1,relative,2048))return 0;
  for(W*p=relative;*p;p++)if(*p=='/')*p='\\';
  join_relative(relative,path);if(!check_file(path,files[i].hash))return 0;
 }
 const W*groups[]={(W*)L"app",(W*)L"runtime",(W*)L"vendor",(W*)L"tools",(W*)L"licenses"};
 for(u32 i=0;i<5;i++){W relative[2048];copy(relative,groups[i]);if(!scan(relative,0))return 0;}
 /* Reject root-level CLR configs and DLL shadowing before CLR is ever started. */
 join_relative((W*)L"*",path);FindData d;H f=FindFirstFileW(path,&d);if(f==(H)-1)return 0;
 int valid=1;do {if(d.attrs&0x10)continue;W*dot=0;for(W*p=d.name;*p;p++)if(*p=='.')dot=p;
 if(dot&&(wi_eq(dot,(W*)L".config")||wi_eq(dot,(W*)L".dll")||wi_eq(dot,(W*)L".pyd")||wi_eq(dot,(W*)L".py")||wi_eq(dot,(W*)L".pyw")||wi_eq(dot,(W*)L".pth"))){valid=0;break;}
 }while(FindNextFileW(f,&d));FindClose(f);return valid;
}
static int trusted_sid(void*sid){return equal_sid(sid,admin_sid)||equal_sid(sid,system_sid);}
static int secure_path(W*p){
 void*owner=0,*acl=0,*descriptor=0;
 if(get_security(p,1,5,&owner,0,&acl,0,&descriptor))return 0;
 int ok=owner&&acl&&trusted_sid(owner);
 if(ok){unsigned short count=((unsigned short*)acl)[2];
 for(u32 i=0;i<count;i++){u8*ace=0;if(!get_ace(acl,i,(void**)&ace)){ok=0;break;}
 if(ace[0]==0){u32 rights=*(u32*)(ace+4);u32 write=2|4|16|64|256|0x10000|0x40000|0x80000|0x40000000|0x10000000;
 if((rights&write)&&!trusted_sid(ace+8)){ok=0;break;}}
 else if(ace[0]!=1){ok=0;break;}
 }}
 if(descriptor)LocalFree(descriptor);return ok;
}
static int make_secure(W*p,SecurityAttrs*security){
 if(!CreateDirectoryW(p,security)&&GetLastError()!=183)return 0;
 no_link(p);return !failed&&secure_path(p);
}
static int bootstrap(H shell){
 typedef int(*Folder)(H,int,H,u32,W*);Folder folder=(Folder)GetProcAddress(shell,"SHGetFolderPathW");
 if(!folder||folder(0,35,0,0,scratch))return 0;
 H security=system_dll((W*)L"advapi32.dll");if(!security)return 0;
 convert_sd=(ConvertSD)GetProcAddress(security,"ConvertStringSecurityDescriptorToSecurityDescriptorW");
 get_security=(GetSecurity)GetProcAddress(security,"GetNamedSecurityInfoW");
 equal_sid=(EqualSidFn)GetProcAddress(security,"EqualSid");get_ace=(GetAceFn)GetProcAddress(security,"GetAce");
 ConvertSidFn sid=(ConvertSidFn)GetProcAddress(security,"ConvertStringSidToSidW");
 if(!convert_sd||!get_security||!equal_sid||!get_ace||!sid||!sid((W*)L"S-1-5-32-544",&admin_sid)||!sid((W*)L"S-1-5-18",&system_sid))return 0;
 void*descriptor=0;if(!convert_sd((W*)L"O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;BU)",1,&descriptor,0))return 0;
 SecurityAttrs attrs={sizeof(attrs),descriptor,0};
 append(scratch,(W*)L"\\M4CameraToolBootstrap");if(!make_secure(scratch,&attrs))return 0;
 append(scratch,(W*)L"\\");W key[80];ascii(key,MANAGED_SHA);append(scratch,key);
 if(!make_secure(scratch,&attrs))return 0;
 copy(path,scratch);append(path,(W*)L"\\Launcher.exe");
 if(GetFileAttributesW(path)==0xffffffff){
 H file=CreateFileW(path,0x40000000,0,&attrs,1,0x80,0);if(file==(H)-1)return 0;
 u32 done=0;int ok=WriteFile(file,managed_payload,sizeof(managed_payload),&done,0)&&done==sizeof(managed_payload);
 CloseHandle(file);if(!ok)return 0;
 }
 if(!secure_path(path)||!check_file(path,MANAGED_SHA))return 0;
 /* No .config, DLL or any companion input in the managed bootstrap directory. */
 W pattern[2048];copy(pattern,scratch);append(pattern,(W*)L"\\*");FindData d;H finder=FindFirstFileW(pattern,&d);if(finder==(H)-1)return 0;
 int exact=1;do {if(weq(d.name,(W*)L".")||weq(d.name,(W*)L".."))continue;if(!weq(d.name,(W*)L"Launcher.exe")){exact=0;break;}}
 while(FindNextFileW(finder,&d));FindClose(finder);if(!exact)return 0;
 copy(command,(W*)L"\"");append(command,path);append(command,(W*)L"\" --source \"");append(command,root);append(command,(W*)L"\"");
 Startup start={0};start.size=sizeof(start);Process process={0};
 if(!CreateProcessW(path,command,0,0,0,0,0,scratch,&start,&process))return 0;
 WaitForSingleObject(process.process,0xffffffff);u32 code=1;GetExitCodeProcess(process.process,&code);
 CloseHandle(process.thread);CloseHandle(process.process);LocalFree(descriptor);ExitProcess(code);return 1;
}
void WinMainCRTStartup(void){
 H kernel=system_dll((W*)L"kernel32.dll");if(!kernel)error();
 to_wide=(ToWide)GetProcAddress(kernel,"MultiByteToWideChar");to_utf8=(ToUtf8)GetProcAddress(kernel,"WideCharToMultiByte");
 H shell=system_dll((W*)L"shell32.dll");if(!shell)error();
 typedef W**(*Argv)(const W*,int*);int argc=0;Argv argvfn=(Argv)GetProcAddress(shell,"CommandLineToArgvW");
 W**argv=argvfn?argvfn(GetCommandLineW(),&argc):0;if(!argv||(argc!=1&&!(argc==2&&weq(argv[1],(W*)L"--verify"))))error();
 int verify=argc==2;
 if(!GetModuleFileNameW(0,root,32768))error();
 H self=CreateFileW(root,0x80000000,1,0,3,0x80,0);if(self==(H)-1)error();leases[lease_count++]=self;
 W*p=root;W*slash=0;while(*p){if(*p=='\\')slash=p;p++;}if(!slash)error();*slash=0;
 if(!hold_parents(root)||!verify_source()){if(verify)ExitProcess(1);error();}
 if(verify){const char json[]="{\"version\":\"" PRODUCT_VERSION "\",\"integrity\":true,\"native_verification\":true,\"device_operations\":0}\n";u32 written;WriteFile(GetStdHandle((u32)-11),json,sizeof(json)-1,&written,0);ExitProcess(0);}
 typedef int(*AdminCheck)(void);AdminCheck isadmin=(AdminCheck)GetProcAddress(shell,"IsUserAnAdmin");
 if(!isadmin)error();
 if(!isadmin()){
 typedef int(*Execute)(ShellInfo*);Execute execute=(Execute)GetProcAddress(shell,"ShellExecuteExW");
 W exe[32768];if(!GetModuleFileNameW(0,exe,32768))error();
 ShellInfo info={0};info.size=sizeof(info);info.mask=0x40;info.verb=(W*)L"runas";info.file=exe;info.directory=root;info.show=0;
 if(!execute||!execute(&info)){u32 e=GetLastError();ExitProcess(e==1223?1223:1);}
 WaitForSingleObject(info.process,0xffffffff);u32 result=1;GetExitCodeProcess(info.process,&result);CloseHandle(info.process);ExitProcess(result);
 }
 if(!clean_environment()||!bootstrap(shell))error();ExitProcess(0);
}
