/* One-shot RAM lifecycle proof. Never opens a block node or writes firmware.
 * Waits for the fixed nonce START, captures the loader's complete maps/fds,
 * proves libJit has been released, then exits. No shell or dynamic commands.
 */
#include "linux_a64.h"
#include "job.h"
struct Result {
    u8 magic[8],nonce[16];
    i64 version,phase,error,euid,pid,ppid,loader_pid,cleanup;
    i64 maps_bytes,fd_count,fd_audit_bytes,flags,fs_available;
};
static struct Result result;
static u8 maps[524289],dirents[8192],target[4096],audit[131073];
static u8 command[33];
static struct Fs fs;
static i64 verify_inherited_closed(void) {
    i64 fd=op("/proc/self/fd",A64_DIRECTORY,0);if(fd<0)return fd;
    i64 result=-75;u32 calls=0;
    while(++calls<=256) {
        i64 n=sc(61,fd,(i64)dirents,sizeof(dirents),0,0,0);
        if(n==-4)continue;
        if(n<0) {result=n;break;}
        if(!n) {result=0;break;}
        if(n>(i64)sizeof(dirents))break;
        for(u64 at=0;at<(u64)n;) {
            if(at+20>(u64)n) {result=-22;goto done;}
            u64 size=dirents[at+16]+((u64)dirents[at+17]<<8);
            if(size<20 || at+size>(u64)n) {result=-22;goto done;}
            u8*name=dirents+at+19;u64 len=0,value=0;
            while(19+len<size && name[len])len++;
            if(!len || 19+len>=size) {result=-22;goto done;}
            if(name[0]!='.') {
                for(u64 j=0;j<len;j++) {
                    if(name[j]<'0'||name[j]>'9'||j>=10) {result=-22;goto done;}
                    value=value*10+(u64)(name[j]-'0');
                }
                if(value!=(u64)fd) {result=-16;goto done;}
            }
            at+=size;
        }
    }
done:
    i64 c=cl(fd);return result?result:c;
}
static i64 now(void) {
    i64 ts[2];if(sc(113,1,(i64)ts,0,0,0,0))return -1;return ts[0];
}
static i64 pause_poll(void) {i64 ts[2]={0,100000000};i64 r=sc(101,(i64)ts,0,0,0,0,0);return r==-4?0:r;}
static i64 wait_start(void) {
    i64 begin=now();if(begin<0)return -5;
    for(u32 i=0;i<601;i++) {
        i64 n=read_all(JOB_DIR "/start",command,sizeof(command));
        if(n>=32) {
            if(n!=32 || !same(command,(const u8*)"M4START1",8) ||
               !same(command+8,job_nonce,16))return -84;
            u64 mode=0;for(u32 j=0;j<8;j++)mode|=(u64)command[24+j]<<(8*j);
            if(mode!=1)return -22;
            return unlink(JOB_DIR "/start");
        }
        if(n<0 && n!=-2)return n;
        i64 current=now();if(current<begin || current-begin>=60)return -110;
        i64 r=pause_poll();if(r)return r;
    }
    return -110;
}
static u32 proc_path(char*out,u64 pid,const char*suffix) {
    const char prefix[]="/proc/";u32 n=0;
    for(u32 i=0;i<6;i++)out[n++]=prefix[i];n+=decimal(out+n,pid);
    for(u32 i=0;suffix[i];i++)out[n++]=suffix[i];out[n]=0;return n;
}
static i64 inspect_loader(void) {
    char path[64];proc_path(path,(u64)result.loader_pid,"/maps");
    i64 n=read_all(path,maps,sizeof(maps));if(n<0)return n;
    if(!n || maps[n-1]!='\n')return -75;
    result.maps_bytes=n;
    i64 r=save_new(JOB_DIR "/loader_maps",maps,(u64)n,0600);if(r)return r;
    if(contains(maps,(u64)n,"libJit.so",9))return -16;
    result.flags|=1;
    proc_path(path,(u64)result.loader_pid,"/fd");
    i64 fd=op(path,A64_DIRECTORY,0);if(fd<0)return fd;
    u64 audit_size=0;u32 calls=0;int complete=0;
    while(++calls<=256) {
        n=sc(61,fd,(i64)dirents,sizeof(dirents),0,0,0);
        if(n==-4)continue;
        if(n<0) {r=n;break;}
        if(!n) {complete=1;break;}
        if(n>(i64)sizeof(dirents)) {r=-75;break;}
        for(u64 at=0;at<(u64)n;) {
            if(at+20>(u64)n) {r=-22;break;}
            u64 size=dirents[at+16]+((u64)dirents[at+17]<<8);
            if(size<20 || at+size>(u64)n) {r=-22;break;}
            u8*name=dirents+at+19;u64 len=0;
            while(19+len<size && name[len])len++;
            if(19+len>=size || !len) {r=-22;break;}
            if(name[0]!='.') {
                for(u64 j=0;j<len;j++)if(name[j]<'0'||name[j]>'9')r=-22;
                if(r)break;
                i64 count=sc(78,fd,(i64)name,(i64)target,sizeof(target),0,0);
                if(count<=0 || count>=(i64)sizeof(target)) {r=count<0?count:-75;break;}
                if(audit_size+len+(u64)count+2>=sizeof(audit)) {r=-75;break;}
                for(u64 j=0;j<len;j++)audit[audit_size++]=name[j];audit[audit_size++]=' ';
                for(i64 j=0;j<count;j++)audit[audit_size++]=target[j];audit[audit_size++]='\n';
                result.fd_count++;
                if(contains(target,(u64)count,"libJit.so",9)) {r=-16;break;}
            }
            at+=size;
        }
        if(r)break;
    }
    i64 c=cl(fd);result.fd_audit_bytes=(i64)audit_size;
    i64 saved=save_new(JOB_DIR "/loader_fds",audit,audit_size,0600);
    if(r)return r;if(c)return c;if(saved)return saved;
    if(!complete)return -75;
    result.flags|=2;return 0;
}
void worker_main(u64*stack) {
    /* Drop inherited device/file handles before opening our own fixed paths. */
    for(i64 fd=0;fd<4096;fd++)cl(fd);
    const u8 magic[]="M4RAM001";
    for(u32 i=0;i<8;i++)result.magic[i]=magic[i];
    for(u32 i=0;i<16;i++)result.nonce[i]=job_nonce[i];
    result.version=1;result.phase=1;
    result.euid=sc(175,0,0,0,0,0,0);result.pid=sc(172,0,0,0,0,0,0);result.ppid=sc(173,0,0,0,0,0,0);
    if(stack[0]!=2) {result.error=-22;goto finished;}
    const char*pid=(const char*)stack[2];u64 value=0;u32 digits=0;
    while(pid[digits] && digits<10) {
        if(pid[digits]<'0'||pid[digits]>'9') {result.error=-22;goto finished;}
        value=value*10+(u64)(pid[digits]-'0');digits++;
    }
    if(!digits || pid[digits] || value<=1 || value>0x7fffffffUL) {result.error=-22;goto finished;}
    result.loader_pid=(i64)value;
    /* The intermediate can still be alive at the first getppid. Wait for
       reparenting before readiness; a single early PPID is not a failure. */
    for(u32 poll=0;result.ppid!=1 && poll<100;poll++) {
        i64 delay[2]={0,1000000};sc(101,(i64)delay,0,0,0,0,0);
        result.ppid=sc(173,0,0,0,0,0,0);
    }
    if(result.ppid!=1) {result.error=-16;goto finished;}
    result.cleanup=unlink(JOB_DIR "/worker");
    if(result.cleanup || result.euid) {result.error=result.cleanup?result.cleanup:-13;goto finished;}
    result.error=tmpfs(&fs);if(result.error)goto finished;
    result.fs_available=fs.bsize*fs.bavail;result.flags|=4;
    result.error=verify_inherited_closed();if(result.error)goto finished;result.flags|=8;
    result.error=save_new(JOB_DIR "/ready",&result,sizeof(result),0600);if(result.error)goto finished;
    result.phase=2;result.error=wait_start();if(result.error)goto finished;
    result.phase=3;result.error=inspect_loader();if(result.error)goto finished;
    result.phase=4;
finished:
    save_new(JOB_DIR "/result",&result,sizeof(result),0600);
    exit_child(result.error?1:0);
}
__attribute__((naked,noreturn,visibility("default"))) void _start(void) {
    __asm__ volatile("mov x0,sp\nbl worker_main\nmov x0,#127\nmov x8,#94\nsvc #0");
}
