"""Execute the production C loader audit against inert Windows syscall fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args();root=args.package.resolve()
    source=root/'app/native/lifecycle_worker.c';text=source.read_text('utf-8')
    audit=text[text.index('static i64 inspect_loader(void)'):text.index('void worker_main(u64*stack)')]
    compiler=root/'tools/zig/zig.exe'
    prefix=r'''
typedef unsigned char u8;typedef unsigned int u32;typedef unsigned long long u64;typedef long long i64;
__declspec(dllimport) void ExitProcess(u32);
static u64 len(const char*s){u64 n=0;while(s[n])n++;return n;}
static void copy(void*p,const void*q,u64 n){for(u64 i=0;i<n;i++)((u8*)p)[i]=((const u8*)q)[i];}
static int equal(const char*a,const char*b){u64 n=0;while(a[n]&&b[n]&&a[n]==b[n])n++;return a[n]==b[n];}
static void zero(void*p,u64 n){for(u64 i=0;i<n;i++)((u8*)p)[i]=0;}
static int contains(const u8*b,u64 n,const char*s,u64 m){for(u64 i=0;i+m<=n;i++){u64 j=0;while(j<m&&b[i+j]==(u8)s[j])j++;if(j==m)return 1;}return 0;}
#define A64_DIRECTORY 0
#define JOB_DIR "/fixture"
static struct {i64 loader_pid,maps_bytes,flags,fd_count,fd_audit_bytes;} result;
static u8 maps[524289],dirents[8192],target[4096],audit[131073];
static u32 loader_audit_attempts;
static i64 stage,subject;static int scenario,batches,map_reads,waits,dir_calls;
#define M4_READER_DIAG(a,b) (stage=(a),subject=(b))
static u32 proc_path(char*out,u64 pid,const char*suffix){copy(out,"/proc/514",9);copy(out+9,suffix,len(suffix)+1);return (u32)(9+len(suffix));}
static i64 pause_poll(void){waits++;return 0;}
static i64 read_all(const char*path,u8*out,u64 cap){
 map_reads++;
 if(scenario==2||(scenario==16&&map_reads>1))return -2;
 if(scenario==14)return 0;
 const char*v=scenario==6?"0000 libJit.so\n":"0000 /lib/libc.so\n";
 copy(out,v,len(v));return (i64)len(v);
}
static i64 save_new(const char*p,const void*d,u64 n,int m){
 if(scenario==11&&contains((const u8*)p,len(p),"loader_maps",11))return -28;
 if(scenario==12&&contains((const u8*)p,len(p),"loader_fds",10))return -28;
 return 0;
}
static i64 op(const char*p,int f,int m){batches=0;return scenario==7?-13:42;}
static i64 cl(i64 fd){return scenario==10?-5:0;}
static i64 sc(i64 no,i64 a,i64 b,i64 c,i64 d,i64 e,i64 f){
 if(no==61){
  dir_calls++;if(scenario==13||(scenario==9&&dir_calls==1))return -4;
  if(scenario==18)return 8193;if(scenario==20)return -5;
  if(batches++)return 0;
  u8*out=(u8*)b;zero(out,48);out[16]=24;out[40]=24;copy(out+19,"10",3);copy(out+43,"11",3);
  if(scenario==8)out[16]=0;
  if(scenario==17)copy(out+19,"x0",3);
  return 48;
 }
 if(no==78){
  const char*name=(const char*)b;
  if(equal(name,"11")){
   if(scenario==1||((scenario==3||scenario==16)&&map_reads==1))return -2;
   if(scenario==4)return -13;
   if(scenario==15)return 4096;
   if(scenario==19)return 0;
  }
  const char*v=scenario==5?"/tmp/jiritsu/libJit.so":"/dev/null";
  copy((void*)c,v,len(v));return (i64)len(v);
 }
 return -22;
}
'''
    suffix=r'''
void mainCRTStartup(void){
 for(scenario=0;scenario<=20;scenario++){
  zero(&result,sizeof(result));result.loader_pid=514;result.flags=12;
  batches=map_reads=waits=dir_calls=0;stage=subject=0;
  i64 actual=inspect_loader(),expected=0,expected_stage=29;
  int attempts=1;
  switch(scenario){
   case 1:expected=-2;expected_stage=25;attempts=M4_FD_AUDIT_ATTEMPTS;break;
   case 2:expected=-2;expected_stage=20;break;
   case 3:if(M4_FD_AUDIT_ATTEMPTS>1){attempts=2;}else{expected=-2;expected_stage=25;}break;
   case 4:expected=-13;expected_stage=25;break;
   case 5:expected=-16;expected_stage=26;break;
   case 6:expected=-16;expected_stage=21;break;
   case 7:expected=-13;expected_stage=22;break;
   case 8:case 17:expected=-22;expected_stage=24;break;
   case 10:expected=-5;expected_stage=27;break;
   case 11:expected=-28;expected_stage=28;break;
   case 12:expected=-28;expected_stage=29;break;
   case 13:expected=-75;expected_stage=27;break;
   case 14:expected=-75;expected_stage=20;break;
   case 15:case 19:expected=-75;expected_stage=25;break;
   case 16:expected=-2;expected_stage=M4_FD_AUDIT_ATTEMPTS>1?20:25;attempts=M4_FD_AUDIT_ATTEMPTS>1?2:1;break;
   case 18:expected=-75;expected_stage=23;break;
   case 20:expected=-5;expected_stage=23;break;
  }
  if(actual!=expected||stage!=expected_stage||loader_audit_attempts!=attempts||waits!=attempts-1)
   ExitProcess(100+(u32)scenario);
  if(!actual&&(result.fd_count!=2||result.flags!=15))ExitProcess(200+(u32)scenario);
  if(dir_calls>256*attempts)ExitProcess(300+(u32)scenario);
 }
 ExitProcess(0);
}
'''
    rows=[]
    with tempfile.TemporaryDirectory(prefix='m4-native-audit-') as directory:
        out=Path(directory);(out/'fixture.c').write_text(prefix+audit+suffix,'utf-8')
        (out/'kernel32.def').write_text('LIBRARY KERNEL32.dll\nEXPORTS\nExitProcess\n','utf-8')
        flags=dict(capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        subprocess.run([str(compiler),'dlltool','-m','i386:x86-64','-d',str(out/'kernel32.def'),'-l',str(out/'kernel32.lib')],check=True,**flags)
        for attempts in (1,3):
            exe=out/('fixture_'+str(attempts)+'.exe')
            compiled=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-O1','-nostdlib','-fno-builtin',
                '-fno-stack-protector','-mno-stack-arg-probe','-DM4_FD_AUDIT_ATTEMPTS='+str(attempts),str(out/'fixture.c'),str(out/'kernel32.lib'),
                '-Wl,--entry,mainCRTStartup','-Wl,--subsystem,console','-o',str(exe)],**flags)
            assert compiled.returncode==0,compiled.stderr.decode(errors='replace')
            result=subprocess.run([str(exe)],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode==0,dict(attempts=attempts,failed_fixture=result.returncode)
            rows.append(dict(audit_attempt_limit=attempts,passed_cases=21))
        writer=(root/'app/writer/writer.c').read_text('utf-8')
        write_exact=writer[writer.index('static i64 pwrite_exact('):writer.index('__attribute__((noinline')]
        rollback=writer[writer.index('static i64 rollback(void)'):writer.index('static i64 transact(void)')]
        io_prefix=r'''
typedef unsigned char u8;typedef unsigned int u32;typedef unsigned long long u64;typedef long long i64;
__declspec(dllimport) void ExitProcess(u32);
#define P1_BYTES 25100288UL
static struct {i64 write_calls,write_bytes,rollback;u8 after[32];} wr;
static struct {u64 offset,length;} rows[2]={{10,4},{20,4}};
static u32 packet_at[2]={0,8},attempted=2;static u8 packets[16],expected_before_digest[32];
static i64 device=1;static int scenario,calls;static i64 offsets[4097];
static int same(const u8*a,const u8*b,u64 n){for(u64 i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static i64 digest_fd(i64 fd,u64 n,u8*out){for(int i=0;i<32;i++)out[i]=scenario==14?1:0;return scenario==13?-5:0;}
static i64 sc(i64 no,i64 a,i64 b,i64 c,i64 d,i64 e,i64 f){
 if(no==82)return scenario==12?-5:0;
 if(no!=68)return -22;
 offsets[calls++]=d;
 if(scenario==1)return c>3?3:c;
 if(scenario==2&&calls==1)return -4;
 if(scenario==3)return 0;
 if(scenario==4)return calls==1?4:-5;
 if(scenario==5)return c+1;
 if(scenario==6)return -4;
 if(scenario==7)return -28;
 if(scenario==11&&calls==1)return -5;
 return c;
}
'''
        io_suffix=r'''
void mainCRTStartup(void){
 u8 bytes[16];for(int i=0;i<16;i++)bytes[i]=0;
 for(scenario=0;scenario<8;scenario++){
  calls=0;wr.write_calls=wr.write_bytes=0;
  i64 actual=pwrite_exact(1,bytes,16,100);
  i64 expected=scenario<3?0:scenario==6?-11:scenario==7?-28:-5;
  if(actual!=expected||calls>4096)ExitProcess(100+scenario);
  if(scenario<3&&wr.write_bytes!=16)ExitProcess(120+scenario);
  if(scenario==1&&(calls!=6||offsets[5]!=115))ExitProcess(140);
  if(scenario==4&&(wr.write_bytes!=4||calls!=2))ExitProcess(141);
 }
 for(scenario=10;scenario<15;scenario++){
  calls=0;wr.write_calls=wr.write_bytes=0;
  i64 actual=rollback();i64 expected=scenario==10?0:scenario==14?-84:-5;
  if(actual!=expected||wr.rollback!=(scenario==10?1:2)||calls!=2||offsets[0]!=20||offsets[1]!=10)
   ExitProcess(200+scenario);
 }
 ExitProcess(0);
}
'''
        (out/'io.c').write_text(io_prefix+write_exact+rollback+io_suffix,'utf-8')
        exe=out/'io.exe'
        compiled=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-O1','-nostdlib','-fno-builtin',
            '-fno-stack-protector','-mno-stack-arg-probe',str(out/'io.c'),str(out/'kernel32.lib'),
            '-Wl,--entry,mainCRTStartup','-Wl,--subsystem,console','-o',str(exe)],**flags)
        assert compiled.returncode==0,compiled.stderr.decode(errors='replace')
        result=subprocess.run([str(exe)],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,dict(native_io_failure=result.returncode)
        rows.append(dict(operation='production pwrite_exact and rollback',passed_cases=13))
    print(json.dumps(dict(passed=True,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        cases=rows,device_operations=0,scope='production C with inert syscall boundaries; no hardware'),ensure_ascii=False))


if __name__=='__main__':main()
