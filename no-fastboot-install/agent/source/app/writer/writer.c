/* M4 fixed p1 transaction worker. No shell, driver, configuration, NOR or
 * arbitrary device API. All target data/hashes are bound at build time.
 * The reviewed lifecycle helpers are included in place; their old entrypoints
 * are renamed and removed by --gc-sections, not copied into a new live tool.
 */
#define _start lifecycle_start_unused
#define worker_main lifecycle_main_unused
#define result lifecycle_result
#include "../native/lifecycle_worker.c"
#undef result
#undef worker_main
#undef _start
#include "sha256.h"

#define P1_BYTES 25100288UL
#define TARGET "/dev/cnflasha1"
#define MAX_ROWS 768
#define MAX_WINDOW 16384
enum {F_ROOT=1,F_TMPFS=2,F_LOADER=4,F_STAGED=8,F_BEFORE=16,F_EXCLUSIVE=32,F_AFTER=64,F_READBACK=128};
struct Row{u64 offset,length;u8 before[32],after[32];};
_Static_assert(sizeof(struct Row)==80,"window ABI");
struct WriteResult{u8 magic[8],nonce[16];i64 version,phase,error,euid,pid,ppid,loader_pid,cleanup,mode,rows,
    write_calls,write_bytes,rollback,flags,io_status;u8 before[32],after[32];};
_Static_assert(sizeof(struct WriteResult)==208,"result ABI");
static struct WriteResult wr;
static struct Row rows[MAX_ROWS];
static u32 packet_at[MAX_ROWS];
static u8 packets[STAGE_BYTES ? STAGE_BYTES : 1],io_buf[65536],small[256],stat_buf[128],mounts[131073];
static i64 device=-1;
static u32 attempted;

static i64 pread_exact(i64 fd,u8*b,u64 n,u64 off){
    u64 done=0;u32 calls=0;while(done<n && ++calls<=4096){i64 r=sc(67,fd,(i64)(b+done),n-done,off+done,0,0);
        if(r==-4)continue;if(r<=0 || (u64)r>n-done)return r<0?r:-5;done+=(u64)r;}return done==n?0:-11;
}
static i64 pwrite_exact(i64 fd,const u8*b,u64 n,u64 off){
    u64 done=0;u32 calls=0;while(done<n && ++calls<=4096){
        wr.write_calls++;i64 r=sc(68,fd,(i64)(b+done),n-done,off+done,0,0);
        if(r==-4)continue;if(r<=0 || (u64)r>n-done)return r<0?r:-5;done+=(u64)r;wr.write_bytes+=r;
    }return done==n?0:-11;
}
__attribute__((noinline,visibility("default"))) i64 digest_fd(i64 fd,u64 size,u8*out){
    struct Sha256 s;sha_init(&s);
    for(u64 at=0;at<size;){u64 n=size-at;if(n>sizeof(io_buf))n=sizeof(io_buf);
        i64 r=pread_exact(fd,io_buf,n,at);if(r)return r;sha_update(&s,io_buf,n);at+=n;}
    sha_final(&s,out);return 0;
}
static void filename(char*out,const char*prefix,u32 index){
    u32 n=0;const char*base=JOB_DIR "/";while(base[n]){out[n]=base[n];n++;}
    for(u32 j=0;prefix[j];j++)out[n++]=prefix[j];
    for(u32 j=0;j<4;j++){out[n+3-j]=(char)('0'+index%10);index/=10;}out[n+4]=0;
}
static i64 read_regular(const char*path,u8*out,u64 expected){
    i64 fd=op(path,A64_READ,0);if(fd<0)return fd;
    i64 r=sc(80,fd,(i64)stat_buf,0,0,0,0);
    if(!r){u32 mode=*(u32*)(stat_buf+16);u64 size=*(u64*)(stat_buf+48);
        if((mode&0170000)!=0100000 || size!=expected)r=-22;}
    if(!r)r=pread_exact(fd,out,expected,0);i64 c=cl(fd);return r?r:c;
}
static i64 token(const char*path,const char*magic,u64 timeout){
    i64 begin=now();if(begin<0)return -5;
    for(u64 poll=0;poll<=timeout*10;poll++){
        i64 n=read_all(path,small,65);
        if(n>=0){if(n!=64 || !same(small,(const u8*)magic,8) || !same(small+8,job_nonce,16) ||
                !same(small+24,expected_table_digest,32) || *(u64*)(small+56)!=JOB_MODE)return -84;
            return unlink(path);}
        if(n!=-2)return n;i64 t=now();if(t<begin || (u64)(t-begin)>=timeout)return -110;
        i64 r=pause_poll();if(r)return r;
    }return -110;
}
static i64 unmounted(void){
    i64 n=read_all("/proc/self/mountinfo",mounts,sizeof(mounts));if(n<=0)return n<0?n:-22;
    if(mounts[n-1]!='\n')return -75;
    /* mountinfo third token is major:minor. Reject both p1 driver views. */
    u64 at=0;while(at<(u64)n){u64 end=at;while(end<(u64)n && mounts[end]!='\n')end++;
        u64 a=at;for(u32 field=0;field<2;field++){while(a<end && mounts[a]!=' ')a++;if(a==end)return -22;a++;}
        u64 b=a;while(b<end && mounts[b]!=' ')b++;
        if(b==end)return -22;if((b-a==7 && same(mounts+a,(const u8*)"252:129",7)) ||
            (b-a==5 && same(mounts+a,(const u8*)"252:1",5)))return -16;at=end+1;
    }return 0;
}
static i64 geometry(i64 fd){
    i64 r=sc(80,fd,(i64)stat_buf,0,0,0,0);if(r)return r;
    if((*(u32*)(stat_buf+16)&0170000)!=0060000 || *(u64*)(stat_buf+32)!=64641)return -22;
    u64 bytes=0;r=sc(29,fd,0x80081272UL,(i64)&bytes,0,0,0);if(r)return r;
    if(bytes!=P1_BYTES)return -22;
    r=read_all("/sys/class/block/cnflasha1/dev",small,sizeof(small));
    if(r!=8 || !same(small,(const u8*)"252:129\n",8))return -22;
    r=read_all("/sys/class/block/cnflasha1/size",small,sizeof(small));
    if(r!=6 || !same(small,(const u8*)"49024\n",6))return -22;
    return 0;
}
static i64 stage(void){
    i64 r=read_regular(JOB_DIR "/table",(u8*)rows,NROWS*sizeof(struct Row));if(r)return r;
    u8 digest[32];digest_bytes((const u8*)rows,NROWS*sizeof(struct Row),digest);
    if(!same(digest,expected_table_digest,32))return -84;
    u64 cursor=0,used=0;
    for(u32 i=0;i<NROWS;i++){
        struct Row*row=rows+i;
        if(row->offset<cursor || !row->length || row->length>MAX_WINDOW ||
            row->offset>P1_BYTES-row->length || used+2*row->length>STAGE_BYTES)return -22;
        cursor=row->offset+row->length;packet_at[i]=(u32)used;
        char path[128];filename(path,"w",i);r=read_regular(path,packets+used,2*row->length);if(r)return r;
        digest_bytes(packets+used,row->length,digest);if(!same(digest,row->before,32))return -84;
        digest_bytes(packets+used+row->length,row->length,digest);if(!same(digest,row->after,32))return -84;
        used+=2*row->length;
    }return used==STAGE_BYTES?0:-22;
}
static i64 before_hash(i64 fd){
    i64 r=digest_fd(fd,P1_BYTES,wr.before);if(r)return r;
    return same(wr.before,expected_before_digest,32)?0:-84;
}
static i64 rollback(void){
    i64 error=0;
    for(u32 j=attempted;j>0;j--){u32 i=j-1;i64 r=pwrite_exact(device,packets+packet_at[i],rows[i].length,rows[i].offset);if(r && !error)error=r;}
    i64 sync=sc(82,device,0,0,0,0,0);if(sync && !error)error=sync;
    i64 r=digest_fd(device,P1_BYTES,wr.after);if(r && !error)error=r;
    if(!error && !same(wr.after,expected_before_digest,32))error=-84;
    wr.rollback=error?2:1;return error;
}
static i64 transact(void){
    i64 r=unmounted();if(r)return r;
    /* Linux block-device O_EXCL is intentional: reject a claimed/mounted bdev.
       Do not retry without it if the camera driver rejects this open. */
    device=op(TARGET,A64_READ|2|000200,0);if(device<0)return device;
    wr.flags|=F_EXCLUSIVE;r=geometry(device);if(r)return r;
    r=before_hash(device);if(r)return r;
    r=unmounted();if(r)return r;
    wr.phase=5;r=save_new(JOB_DIR "/intent",&wr,sizeof(wr),0600);if(r)return r;
    for(u32 i=0;i<NROWS;i++){
        struct Row*row=rows+i;
        r=pread_exact(device,io_buf,row->length,row->offset);if(r)goto fail;
        if(!same(io_buf,packets+packet_at[i],row->length)){r=-84;goto fail;}
        attempted=i+1;
        r=pwrite_exact(device,packets+packet_at[i]+row->length,row->length,row->offset);if(r)goto fail;
        r=pread_exact(device,io_buf,row->length,row->offset);if(r)goto fail;
        if(!same(io_buf,packets+packet_at[i]+row->length,row->length)){r=-84;goto fail;}
    }
    r=sc(82,device,0,0,0,0,0);if(r)goto fail;
    r=digest_fd(device,P1_BYTES,wr.after);if(r)goto fail;
    if(!same(wr.after,expected_after_digest,32)){r=-84;goto fail;}wr.flags|=F_AFTER;
    for(u32 i=0;i<NROWS;i++){
        r=pread_exact(device,io_buf,rows[i].length,rows[i].offset);if(r)goto fail;
        if(!same(io_buf,packets+packet_at[i]+rows[i].length,rows[i].length)){r=-84;goto fail;}
        char path[128];filename(path,"rb",i);r=save_new(path,io_buf,rows[i].length,0600);if(r)goto fail;
    }
    wr.flags|=F_READBACK;wr.phase=6;return 0;
fail:
    if(attempted)rollback();return r;
}
void writer_main(u64*stack){
    for(i64 fd=0;fd<4096;fd++)cl(fd);
    for(u32 i=0;i<8;i++)wr.magic[i]=((const u8*)"M4P1WR01")[i];
    for(u32 i=0;i<16;i++)wr.nonce[i]=job_nonce[i];
    wr.version=1;wr.phase=1;wr.mode=JOB_MODE;wr.rows=NROWS;
    wr.euid=sc(175,0,0,0,0,0,0);wr.pid=sc(172,0,0,0,0,0,0);wr.ppid=sc(173,0,0,0,0,0,0);
    if(stack[0]!=2){wr.error=-22;goto done;}
    const char*p=(const char*)stack[2];u64 value=0;u32 digits=0;
    while(p[digits] && digits<10){if(p[digits]<'0'||p[digits]>'9'){wr.error=-22;goto done;}value=value*10+p[digits++]-'0';}
    if(!digits || p[digits] || value<=1 || value>0x7fffffffUL){wr.error=-22;goto done;}wr.loader_pid=(i64)value;
    for(u32 i=0;wr.ppid!=1 && i<100;i++){i64 delay[2]={0,1000000};sc(101,(i64)delay,0,0,0,0,0);wr.ppid=sc(173,0,0,0,0,0,0);}
    wr.cleanup=unlink(JOB_DIR "/worker");
    if(wr.ppid!=1 || wr.euid || wr.cleanup){wr.error=-13;goto done;}wr.flags|=F_ROOT;
    wr.error=tmpfs(&fs);if(wr.error)goto done;
    if((u64)fs.bsize*(u64)fs.bavail<REQUIRED_TMPFS){wr.error=-28;goto done;}wr.flags|=F_TMPFS;
    wr.error=verify_inherited_closed();if(wr.error)goto done;
    lifecycle_result.loader_pid=wr.loader_pid;
    wr.phase=2;wr.error=save_new(JOB_DIR "/ready",&wr,sizeof(wr),0600);if(wr.error)goto done;
    wr.error=token(JOB_DIR "/prepare","M4PREP01",1800);if(wr.error)goto done;
    wr.error=inspect_loader();if(wr.error)goto done;wr.flags|=F_LOADER;
    wr.error=stage();if(wr.error)goto done;wr.flags|=F_STAGED;
    wr.error=unmounted();if(wr.error)goto done;
    device=op(TARGET,A64_READ,0);if(device<0){wr.error=device;goto done;}
    wr.error=geometry(device);if(wr.error)goto done;
    wr.error=before_hash(device);if(wr.error)goto done;wr.flags|=F_BEFORE;
    wr.error=cl(device);device=-1;if(wr.error)goto done;
    wr.phase=3;wr.error=save_new(JOB_DIR "/prepared",&wr,sizeof(wr),0600);if(wr.error)goto done;
    wr.error=token(JOB_DIR "/commit","M4COMMIT",120);if(wr.error)goto done;
    wr.error=transact();
done:
    if(device>=0){wr.io_status=cl(device);device=-1;if(!wr.error && wr.io_status)wr.error=wr.io_status;}
    if(wr.error)wr.phase=90;
    save_new(JOB_DIR "/result",&wr,sizeof(wr),0600);exit_child(wr.error?1:0);
}
__attribute__((naked,noreturn,visibility("default"))) void _start(void){
    __asm__ volatile("mov x0,sp\nbl writer_main\nmov x0,#127\nmov x8,#94\nsvc #0");
}
