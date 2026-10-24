/* Fixed, two-instruction M4 RAM window. All device I/O is /proc memory on
 * retained descriptors; no block device, persistent firmware or ptrace access.
 * The app candidate is selected only after a complete bounded /proc scan.
 * Every attempted write is unwound in reverse order, even after a short write.
 */
#include "linux_a64.h"
#include "job.h"
#include "../workflow/version_labels.h"

struct DualResult {
    u8 magic[8],nonce[16];
    i64 version,phase,error,euid,pid,ppid,loader_pid,cleanup;
    i64 maps_bytes,polls,target_addr,base_addr,machine_version;
    i64 patched,restored,hold_seconds,flags,mem_status,restore_status;
    i64 app_pid,app_target_addr,app_base_addr,app_machine_version;
    i64 app_patched,app_restored,app_mem_status,app_restore_status,app_write_attempted;
    i64 app_maps_bytes,proc_candidates,identity_checks,lib_identity_status,app_identity_status;
    i64 snapshot_before_status,snapshot_end_status;
    i64 before[8],end[8];
};
_Static_assert(sizeof(struct DualResult)==432,"dual window result ABI");
static struct DualResult wr;
static struct Fs fs;
static u8 maps[524289],dirents[8192],command[33],readbuf[64];
enum { F_ROOT=1,F_TMPFS=4,F_INHERITED=8,F_STARTED=16,F_MAPPED=32,
       F_ANCHOR=64,F_PATCHED=128,F_RESTORED=256,F_WRITE_ATTEMPTED=512 };
struct Target {
    i64 pid,fd;
    u64 base,addr,patch_offset,anchor_offset,anchor_bytes,version_offset,version_bytes;
    u64 row_bytes;
    u8 row[512];
    const char *name;
    const u8 *anchor,*original,*patch;
    i64 attempted,patched,restored,identity_status,restore_status;
};
static struct Target lib,app;

static u32 proc_path(char*out,u64 pid,const char*suffix) {
    const char prefix[]="/proc/";u32 n=0;
    for(u32 i=0;i<6;i++)out[n++]=prefix[i];n+=decimal(out+n,pid);
    for(u32 i=0;suffix[i];i++)out[n++]=suffix[i];out[n]=0;return n;
}
static i64 monotonic_ns(void) {
    i64 ts[2];i64 r=sc(113,1,(i64)ts,0,0,0,0);
    if(r)return r;
    if(ts[0]<0 || ts[0]>9223372035LL || ts[1]<0 || ts[1]>=1000000000)return -75;
    return ts[0]*1000000000+ts[1];
}
static i64 sleep_ns(i64 n) {
    i64 ts[2]={n/1000000000,n%1000000000};i64 r=sc(101,(i64)ts,0,0,0,0,0);
    return r==-4?0:r;
}
static i64 verify_inherited_closed(void) {
    i64 fd=op("/proc/self/fd",A64_DIRECTORY,0);if(fd<0)return fd;
    i64 result=-75;u32 calls=0;
    while(++calls<=256) {
        i64 n=sc(61,fd,(i64)dirents,sizeof(dirents),0,0,0);
        if(n==-4)continue;if(n<0){result=n;break;}if(!n){result=0;break;}
        if(n>(i64)sizeof(dirents))break;
        for(u64 at=0;at<(u64)n;) {
            if(at+20>(u64)n){result=-22;goto done;}
            u64 size=dirents[at+16]+((u64)dirents[at+17]<<8);
            if(size<20 || at+size>(u64)n){result=-22;goto done;}
            u8*name=dirents+at+19;u64 len=0,value=0;
            while(19+len<size && name[len])len++;
            if(!len || 19+len>=size){result=-22;goto done;}
            if(name[0]!='.') {
                for(u64 j=0;j<len;j++) {
                    if(name[j]<'0'||name[j]>'9'||j>=10){result=-22;goto done;}
                    value=value*10+(u64)(name[j]-'0');
                }
                if(value!=(u64)fd){result=-16;goto done;}
            }
            at+=size;
        }
    }
done:
    {i64 c=cl(fd);return result?result:c;}
}
static i64 wait_start(void) {
    i64 begin=monotonic_ns();if(begin<0)return begin;
    for(u32 poll=0;poll<=START_TIMEOUT*10;poll++) {
        i64 n=read_all(JOB_DIR "/start",command,sizeof(command));
        if(n>=0 && n!=0) {
            if(n!=32 || !same(command,(const u8*)"M4DSTART",8) || !same(command+8,job_nonce,16))return -84;
            u64 mode=0;for(u32 j=0;j<8;j++)mode|=(u64)command[24+j]<<(8*j);
            if(mode!=1)return -22;
            return unlink(JOB_DIR "/start");
        }
        if(n<0 && n!=-2)return n;
        i64 t=monotonic_ns();if(t<0)return t;
        if(t<begin || t-begin>=(i64)START_TIMEOUT*1000000000)return -110;
        i64 r=sleep_ns(100000000);if(r)return r;
    }
    return -110;
}
static i64 hex_at(const u8*line,u64 end,u64*at,u64*out) {
    u64 value=0;u32 digits=0;
    while(*at<end) {
        u8 c=line[*at];i64 v=(c>='0'&&c<='9')?c-'0':(c>='a'&&c<='f')?c-'a'+10:-1;
        if(v<0)break;if(++digits>16)return -22;
        value=value*16+(u64)v;(*at)++;
    }
    if(!digits || value>0x7fffffffffffffffUL)return -22;*out=value;return 0;
}
static void spaces(u64 end,u64*p){while(*p<end && maps[*p]==' ')(*p)++;}
/* Require an exact final pathname component: aliases, deleted maps and a
 * basename substring never qualify. Complete selected maps row is retained. */
static int basename_is(u64 p,u64 end,const char*name) {
    if(p>=end || maps[p]!='/')return 0;
    u64 last=p;for(u64 j=p;j<end;j++)if(maps[j]=='/')last=j+1;
    u64 i=0;while(name[i])i++;
    return end-last==i && same(maps+last,(const u8*)name,i);
}
static i64 select_map(struct Target*t,u64 n,int bind) {
    if(!n)return -3;if(maps[n-1]!='\n')return -75;
    u64 at=0,found=0,base=0,address=0,row_at=0,row_bytes=0;
    while(at<n) {
        u64 end=at;while(end<n && maps[end]!='\n')end++;
        u64 p=at,start=0,stop=0,offset=0;
        if(hex_at(maps,end,&p,&start) || p>=end || maps[p++]!='-' ||
           hex_at(maps,end,&p,&stop) || p>=end || maps[p++]!=' ')return -22;
        if(p+4>=end)return -22;
        u64 perms=p; p+=4;if(maps[p++]!=' ')return -22;spaces(end,&p);
        if(hex_at(maps,end,&p,&offset) || p>=end || maps[p++]!=' ')return -22;
        spaces(end,&p);
        /* dev and inode are kept byte-for-byte in the identity row. */
        for(u32 field=0;field<2;field++) {
            u64 first=p;while(p<end && maps[p]!=' ')p++;
            if(p==first)return -22;spaces(end,&p);
        }
        if(basename_is(p,end,t->name)) {
            /* Current camera evidence names both modules under /usr/lib.
             * A same-named module elsewhere makes discovery ambiguous. */
            u64 name_bytes=0;while(t->name[name_bytes])name_bytes++;
            if(end-p!=9+name_bytes || !same(maps+p,(const u8*)"/usr/lib/",9))return -84;
            if(maps[perms]!='r' || maps[perms+2]!='x'){at=end+1;continue;}
            if(stop<=start || start<offset || t->patch_offset<offset ||
               t->patch_offset+4-offset>stop-start){at=end+1;continue;}
            /* /proc mem must write private COW executable pages, not shared
             * file mappings or an unexpected writable executable mapping. */
            if(maps[perms+1]!='-' || maps[perms+3]!='p')return -84;
            if(++found>1)return -75;
            base=start-offset;address=base+t->patch_offset;row_at=at;row_bytes=end-at;
            if(!row_bytes || row_bytes>sizeof(t->row))return -75;
            if(t->anchor_offset<offset || t->anchor_offset+t->anchor_bytes-offset>stop-start)return -75;
        }
        at=end+1;
    }
    if(!found)return -3;
    if(bind) {
        t->base=base;t->addr=address;t->row_bytes=row_bytes;
        for(u64 i=0;i<row_bytes;i++)t->row[i]=maps[row_at+i];
    } else if(t->base!=base || t->addr!=address || t->row_bytes!=row_bytes ||
              !same(t->row,maps+row_at,row_bytes))return -116;
    return 0;
}
static i64 read_maps(struct Target*t,int bind) {
    char path[64];proc_path(path,(u64)t->pid,"/maps");
    i64 n=read_all(path,maps,sizeof(maps));if(n<0)return n;
    if(t==&lib && bind)wr.maps_bytes=n;
    if(t==&app)wr.app_maps_bytes=n;
    return select_map(t,(u64)n,bind);
}
/* A complete bounded enumeration precedes any mem write. Empty maps (kernel
 * tasks) and processes disappearing during enumeration are skipped. */
static i64 discover_app(void) {
    i64 fd=op("/proc",A64_DIRECTORY,0);if(fd<0)return fd;
    i64 result=-75;u32 calls=0,entries=0;struct Target found=app;
    while(++calls<=256) {
        i64 n=sc(61,fd,(i64)dirents,sizeof(dirents),0,0,0);
        if(n==-4)continue;if(n<0){result=n;break;}if(!n){result=0;break;}
        if(n>(i64)sizeof(dirents))break;
        for(u64 at=0;at<(u64)n;) {
            if(at+20>(u64)n){result=-22;goto done;}
            u64 size=dirents[at+16]+((u64)dirents[at+17]<<8);
            if(size<20 || at+size>(u64)n){result=-22;goto done;}
            u8*name=dirents+at+19;u64 len=0,pid=0;int numeric=1;
            while(19+len<size && name[len])len++;
            if(!len || 19+len>=size){result=-22;goto done;}
            for(u64 j=0;j<len;j++)if(name[j]<'0'||name[j]>'9')numeric=0;
            if(numeric) {
                if(len>10 || ++entries>4096){result=-75;goto done;}
                for(u64 j=0;j<len;j++)pid=pid*10+name[j]-'0';
                if(!pid || pid>0x7fffffffUL){result=-22;goto done;}
                found.pid=(i64)pid;
                i64 r=read_maps(&found,1);
                if(!r) {
                    if(++wr.proc_candidates>1){result=-75;goto done;}
                    app=found;
                } else if(r!=-2 && r!=-3){result=r;goto done;}
            }
            at+=size;
        }
    }
done:
    {i64 c=cl(fd);if(result)return result;if(c)return c;}
    if(wr.proc_candidates!=1)return -3;
    /* Rebind only to the same selection after the full scan. */
    return read_maps(&app,0);
}
static i64 mem_pre(i64 fd,u8*b,u64 n,u64 off) {
    u64 done=0;u32 calls=0;
    while(done<n && ++calls<=64) {
        i64 r=sc(67,fd,(i64)(b+done),n-done,off+done,0,0);
        if(r==-4)continue;if(r<=0 || (u64)r>n-done)return r<0?r:-5;
        done+=(u64)r;
    }
    return done==n?0:-11;
}
static i64 mem_pwr(i64 fd,const u8*b,u64 n,u64 off) {
    u32 calls=0;
    while(++calls<=64) {
        i64 r=sc(68,fd,(i64)b,n,off,0,0);
        if(r==-4)continue;
        /* A short instruction write enters restoration immediately. Never
         * intentionally finish an instruction with a second subword write. */
        return r==(i64)n?0:(r<0?r:-5);
    }
    return -11;
}
static i64 open_check(struct Target*t,i64*version) {
    char path[64];proc_path(path,(u64)t->pid,"/mem");
    t->fd=op(path,A64_READ|2,0);if(t->fd<0)return t->fd;
    i64 r=read_maps(t,0);if(r)return r;
    r=mem_pre(t->fd,readbuf,t->anchor_bytes,t->base+t->anchor_offset);if(r)return r;
    if(!same(readbuf,t->anchor,t->anchor_bytes))return -84;
    r=mem_pre(t->fd,readbuf,t->version_bytes,t->base+t->version_offset);if(r)return r;
    u64 v=0;for(u64 i=0;i<t->version_bytes;i++)v|=(u64)readbuf[i]<<(i*8);
    *version=(i64)v;return 0;
}
/* The fd pins the original mm. Never reopen it, even if PID is reused.
 * Mapping row and present instruction must still belong to this operation. */
static i64 check_identity(struct Target*t,int mode) {
    wr.identity_checks++;
    i64 r=read_maps(t,0);if(r)return t->identity_status=r;
    r=mem_pre(t->fd,readbuf,4,t->addr);if(r)return t->identity_status=r;
    if(mode==0 && !same(readbuf,t->original,4))r=-84;
    if(mode==1 && !same(readbuf,t->patch,4))r=-84;
    if(mode==2) {
        int owned=0;
        for(u64 prefix=0;prefix<=4;prefix++)
            if(same(readbuf,t->patch,prefix) && same(readbuf+prefix,t->original+prefix,4-prefix))owned=1;
        if(!owned)r=-84;
    }
    return t->identity_status=r;
}
static void sync_result(void) {
    wr.app_pid=app.pid;wr.app_base_addr=(i64)app.base;wr.app_target_addr=(i64)app.addr;
    wr.base_addr=(i64)lib.base;wr.target_addr=(i64)lib.addr;
    wr.patched=lib.patched;wr.restored=lib.restored;wr.restore_status=lib.restore_status;
    wr.app_patched=app.patched;wr.app_restored=app.restored;wr.app_restore_status=app.restore_status;
    wr.app_write_attempted=app.attempted;
    wr.lib_identity_status=lib.identity_status;wr.app_identity_status=app.identity_status;
    if(lib.attempted)wr.flags|=F_WRITE_ATTEMPTED;
    if(lib.patched)wr.flags|=F_PATCHED;
    if(lib.restored)wr.flags|=F_RESTORED;
}
static i64 snapshot(i64*out) {
    for(u64 i=0;i<8;i++)out[i]=-1;
    for(u64 i=0;i<8;i++) {
        i64 r=mem_pre(app.fd,readbuf,observation_sizes[i],app.base+observation_offsets[i]);if(r)return r;
        u64 v=0;for(u64 j=0;j<observation_sizes[i];j++)v|=(u64)readbuf[j]<<(j*8);
        out[i]=(i64)v;
    }
    return 0;
}
static i64 apply_one(struct Target*t) {
    i64 r=check_identity(t,0);if(r)return r;
    t->attempted=1;sync_result();
    r=mem_pwr(t->fd,t->patch,4,t->addr);if(r)return r;
    r=check_identity(t,1);if(r)return r;
    t->patched=1;sync_result();return 0;
}
static i64 restore_one(struct Target*t) {
    if(!t->attempted)return 0;
    /* Once a complete patch was verified, an unexpected instruction change
     * can mean unload/reload. Do not overwrite that new state or claim a
     * successful restore merely because original bytes reappeared. */
    if(t->patched && t->identity_status)return t->restore_status=t->identity_status;
    i64 r=check_identity(t,2);if(r)return t->restore_status=r;
    r=mem_pwr(t->fd,t->original,4,t->addr);if(r)return t->restore_status=r;
    r=check_identity(t,0);t->restore_status=r;if(!r)t->restored=1;return r;
}
static i64 hold_window(void) {
    i64 begin=monotonic_ns();if(begin<0)return begin;i64 previous=begin;
    for(;;) {
        i64 t=monotonic_ns();if(t<0)return t;if(t<previous)return -5;previous=t;
        i64 elapsed=t-begin;wr.hold_seconds=elapsed/1000000000;
        i64 r=check_identity(&lib,1);if(r)return r;
        r=check_identity(&app,1);if(r)return r;
        i64 left=(i64)HOLD_SECONDS*1000000000-elapsed;if(left<=0)return 0;
        if(left>1000000000)left=1000000000;r=sleep_ns(left);if(r)return r;
    }
}
void dual_main(u64*stack) {
    for(i64 fd=0;fd<4096;fd++)cl(fd);
    const u8 magic[]="M4DWL002";
    for(u32 i=0;i<8;i++)wr.magic[i]=magic[i];for(u32 i=0;i<16;i++)wr.nonce[i]=job_nonce[i];
    wr.version=1;wr.phase=1;
    lib=(struct Target){.fd=-1,.name="libupdaterufp.so",.patch_offset=PATCH_OFFSET,
        .anchor_offset=ANCHOR_OFFSET,.anchor_bytes=20,.version_offset=GLOBAL_OFFSET,.version_bytes=2,
        .anchor=anchor,.original=original4,.patch=patch4};
    app=(struct Target){.fd=-1,.name="appFw.so",.patch_offset=APP_PATCH_OFFSET,
        .anchor_offset=APP_ANCHOR_OFFSET,.anchor_bytes=32,.version_offset=APP_GLOBAL_OFFSET,.version_bytes=4,
        .anchor=app_anchor,.original=app_original4,.patch=app_patch4};
    for(u32 i=0;i<8;i++){wr.before[i]=-1;wr.end[i]=-1;}
    wr.snapshot_before_status=-11;wr.snapshot_end_status=-11;
    wr.euid=sc(175,0,0,0,0,0,0);wr.pid=sc(172,0,0,0,0,0,0);wr.ppid=sc(173,0,0,0,0,0,0);
    if(stack[0]!=2){wr.error=-22;goto done;}
    const char*p=(const char*)stack[2];u64 value=0;u32 digits=0;
    while(p[digits] && digits<10){if(p[digits]<'0'||p[digits]>'9'){wr.error=-22;goto done;}value=value*10+p[digits++]-'0';}
    if(!digits || p[digits] || value<=1 || value>0x7fffffffUL){wr.error=-22;goto done;}
    lib.pid=wr.loader_pid=(i64)value;
    for(u32 i=0;wr.ppid!=1 && i<100;i++){sleep_ns(1000000);wr.ppid=sc(173,0,0,0,0,0,0);}
    wr.cleanup=unlink(JOB_DIR "/worker");
    if(wr.ppid!=1 || wr.euid || wr.cleanup){wr.error=wr.cleanup?wr.cleanup:-13;goto done;}
    wr.flags|=F_ROOT;
    wr.error=tmpfs(&fs);if(wr.error)goto done;wr.flags|=F_TMPFS;
    wr.error=verify_inherited_closed();if(wr.error)goto done;wr.flags|=F_INHERITED;
    wr.error=save_new(JOB_DIR "/ready",&wr,sizeof(wr),0600);if(wr.error)goto done;
    wr.phase=2;wr.error=wait_start();if(wr.error)goto done;wr.flags|=F_STARTED;
    wr.phase=3;
    {
        i64 begin=monotonic_ns();if(begin<0){wr.error=begin;goto done;}
        for(;;) {
            wr.polls++;wr.error=read_maps(&lib,1);if(!wr.error)break;
            if(wr.error!=-2 && wr.error!=-3)goto done;
            i64 t=monotonic_ns();if(t<0){wr.error=t;goto done;}
            if(t<begin || t-begin>=(i64)MAPS_WAIT_SECONDS*1000000000){wr.error=-110;goto done;}
            wr.error=sleep_ns(100000000);if(wr.error)goto done;
        }
    }
    wr.error=discover_app();if(wr.error)goto done;wr.flags|=F_MAPPED;sync_result();
    wr.error=open_check(&lib,&wr.machine_version);if(wr.error)goto done;
    wr.error=open_check(&app,&wr.app_machine_version);if(wr.error)goto done;
    if(!m4_versions_consistent((u64)wr.machine_version,(u64)wr.app_machine_version)){wr.error=-84;goto done;}
    wr.error=check_identity(&lib,0);if(wr.error)goto done;
    wr.error=check_identity(&app,0);if(wr.error)goto done;
    wr.flags|=F_ANCHOR;
    wr.snapshot_before_status=snapshot(wr.before);
    if(wr.snapshot_before_status){wr.error=wr.snapshot_before_status;goto done;}
    wr.phase=4;wr.error=apply_one(&app);if(wr.error)goto unwind;
    wr.error=apply_one(&lib);if(wr.error)goto unwind;
    wr.phase=5;
    wr.snapshot_end_status=snapshot(wr.end);
    if(wr.snapshot_end_status){wr.error=wr.snapshot_end_status;goto unwind;}
    sync_result();wr.error=save_new(JOB_DIR "/patched",&wr,sizeof(wr),0600);if(wr.error)goto unwind;
    wr.snapshot_end_status=-11;for(u32 i=0;i<8;i++)wr.end[i]=-1;
    wr.error=hold_window();if(wr.error)goto unwind;
    wr.snapshot_end_status=snapshot(wr.end);
    if(wr.snapshot_end_status){wr.error=wr.snapshot_end_status;goto unwind;}
    wr.phase=6;
unwind:
    /* Reverse order, including partial or failed second writes. The original
     * failure is retained; independent restore statuses are always reported. */
    {i64 r=restore_one(&lib);if(!wr.error && r)wr.error=r;}
    {i64 r=restore_one(&app);if(!wr.error && r)wr.error=r;}
done:
    sync_result();
    if(lib.fd>=0){wr.mem_status=cl(lib.fd);lib.fd=-1;if(!wr.error && wr.mem_status)wr.error=wr.mem_status;}
    if(app.fd>=0){wr.app_mem_status=cl(app.fd);app.fd=-1;if(!wr.error && wr.app_mem_status)wr.error=wr.app_mem_status;}
    if(wr.error)wr.phase=90;
    save_new(JOB_DIR "/result",&wr,sizeof(wr),0600);exit_child(wr.error?1:0);
}
__attribute__((naked,noreturn,visibility("default"))) void _start(void) {
    __asm__ volatile("mov x0,sp\nbl dual_main\nmov x0,#127\nmov x8,#94\nsvc #0");
}
