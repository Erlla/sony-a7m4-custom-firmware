/* Fixed p1 reader: source is opened O_RDONLY. No pwrite, block write, shell,
 * mount, flash, firmware installation or arbitrary path API exists. */
#define _start lifecycle_start_unused
#define worker_main lifecycle_main_unused
#define result lifecycle_result
#include "../native/lifecycle_worker.c"
#undef result
#undef worker_main
#undef _start
#define rr sha_rotate_right
#include "../writer/sha256.h"
#undef rr
#define P1_BYTES 25100288UL
#define CHUNK 32768UL
#define COUNT ((P1_BYTES+CHUNK-1)/CHUNK)
struct ReadResult {u8 magic[8],nonce[16];i64 version,phase,error,euid,pid,ppid,loader_pid,cleanup,bytes,chunks,flags;u8 first[32],second[32];};
_Static_assert(sizeof(struct ReadResult)==176,"read ABI");
static struct ReadResult rr;
static u8 snapshot[P1_BYTES],digests[COUNT*32],buffer[65536],st[128],mounts[131073];
static i64 device=-1;
static i64 pread_exact(i64 fd,u8*b,u64 n,u64 off){
    u64 done=0;u32 calls=0;while(done<n && ++calls<=4096){i64 r=sc(67,fd,(i64)(b+done),n-done,off+done,0,0);
        if(r==-4)continue;if(r<=0 || (u64)r>n-done)return r<0?r:-5;done+=r;}return done==n?0:-11;
}
__attribute__((noinline,visibility("default"))) i64 digest_fd(i64 fd,u64 size,u8*out){
    struct Sha256 s;sha_init(&s);for(u64 at=0;at<size;){u64 n=size-at;if(n>sizeof(buffer))n=sizeof(buffer);
        i64 r=pread_exact(fd,buffer,n,at);if(r)return r;sha_update(&s,buffer,n);at+=n;}sha_final(&s,out);return 0;
}
static void filename(char*out,u32 index){
    const char*base=JOB_DIR "/c";u32 n=0;while(base[n]){out[n]=base[n];n++;}
    for(u32 j=0;j<4;j++){out[n+3-j]=(char)('0'+index%10);index/=10;}out[n+4]=0;
}
static i64 unmounted(void){
    i64 n=read_all("/proc/self/mountinfo",mounts,sizeof(mounts));if(n<=0)return n<0?n:-22;
    if(mounts[n-1]!='\n')return -75;
    i64 r=save_new(JOB_DIR "/mountinfo",mounts,n,0600);if(r)return r;
    u64 at=0;while(at<(u64)n){u64 end=at;while(end<(u64)n && mounts[end]!='\n')end++;
        u64 a=at;for(u32 field=0;field<2;field++){while(a<end && mounts[a]!=' ')a++;if(a==end)return -22;a++;}
        u64 b=a;while(b<end && mounts[b]!=' ')b++;if(b==end)return -22;
        if((b-a==7 && same(mounts+a,(const u8*)"252:129",7)) ||
           (b-a==5 && same(mounts+a,(const u8*)"252:1",5)))return -16;at=end+1;}
    return 0;
}
static i64 geometry(i64 fd){
    i64 r=sc(80,fd,(i64)st,0,0,0,0);if(r)return r;
    if((*(u32*)(st+16)&0170000)!=0060000 || *(u64*)(st+32)!=64641)return -22;
    u64 bytes=0;r=sc(29,fd,0x80081272UL,(i64)&bytes,0,0,0);if(r)return r;if(bytes!=P1_BYTES)return -22;
    r=read_all("/sys/class/block/cnflasha1/dev",buffer,sizeof(buffer));if(r!=8 || !same(buffer,(const u8*)"252:129\n",8))return -22;
    r=read_all("/sys/class/block/cnflasha1/size",buffer,sizeof(buffer));if(r!=6 || !same(buffer,(const u8*)"49024\n",6))return -22;
    return 0;
}
static i64 capture(void){
    i64 r=unmounted();if(r)return r;rr.flags|=8;
    device=op("/dev/cnflasha1",A64_READ,0);if(device<0)return device;
    r=geometry(device);if(r)return r;rr.flags|=16;
    for(u64 at=0;at<P1_BYTES;){u64 n=P1_BYTES-at;if(n>65536)n=65536;
        r=pread_exact(device,snapshot+at,n,at);if(r)return r;at+=n;rr.bytes=at;}
    digest_bytes(snapshot,P1_BYTES,rr.first);
    /* A second complete source read must agree with the captured buffer. */
    r=digest_fd(device,P1_BYTES,rr.second);if(r)return r;
    if(!same(rr.first,rr.second,32))return -84;rr.flags|=32;
    r=cl(device);device=-1;if(r)return r;
    for(u32 i=0;i<COUNT;i++){u64 at=(u64)i*CHUNK,n=P1_BYTES-at;if(n>CHUNK)n=CHUNK;
        digest_bytes(snapshot+at,n,digests+32*i);char path[128];filename(path,i);
        r=save_new(path,snapshot+at,n,0600);if(r)return r;rr.chunks=i+1;}
    r=save_new(JOB_DIR "/digests",digests,sizeof(digests),0600);if(r)return r;rr.flags|=64;return 0;
}
static void cleanup_chunks(void){
    for(u32 i=0;i<COUNT;i++){char path[128];filename(path,i);i64 r=unlink(path);if(r && r!=-2 && !rr.cleanup)rr.cleanup=r;}
    i64 r=unlink(JOB_DIR "/digests");if(r && r!=-2 && !rr.cleanup)rr.cleanup=r;
}
void reader_main(u64*stack){
    for(i64 fd=0;fd<4096;fd++)cl(fd);
    for(u32 i=0;i<8;i++)rr.magic[i]=((const u8*)"M4P1RD01")[i];for(u32 i=0;i<16;i++)rr.nonce[i]=job_nonce[i];
    rr.version=1;rr.phase=1;rr.euid=sc(175,0,0,0,0,0,0);rr.pid=sc(172,0,0,0,0,0,0);rr.ppid=sc(173,0,0,0,0,0,0);
    if(stack[0]!=2){rr.error=-22;goto done;}const char*p=(const char*)stack[2];u64 value=0;u32 digits=0;
    while(p[digits] && digits<10){if(p[digits]<'0'||p[digits]>'9'){rr.error=-22;goto done;}value=value*10+p[digits++]-'0';}
    if(!digits || p[digits] || value<=1 || value>0x7fffffffUL){rr.error=-22;goto done;}rr.loader_pid=value;
    for(u32 i=0;rr.ppid!=1 && i<100;i++){i64 ts[2]={0,1000000};sc(101,(i64)ts,0,0,0,0,0);rr.ppid=sc(173,0,0,0,0,0,0);}
    rr.cleanup=unlink(JOB_DIR "/worker");if(rr.euid || rr.ppid!=1 || rr.cleanup){rr.error=-13;goto done;}rr.flags|=1;
    rr.error=tmpfs(&fs);if(rr.error)goto done;if((u64)fs.bsize*(u64)fs.bavail<64*1024*1024UL){rr.error=-28;goto done;}rr.flags|=2;
    rr.error=verify_inherited_closed();if(rr.error)goto done;
    rr.error=save_new(JOB_DIR "/ready",&rr,sizeof(rr),0600);if(rr.error)goto done;
    rr.phase=2;rr.error=wait_start();if(rr.error)goto done;
    lifecycle_result.loader_pid=rr.loader_pid;rr.error=inspect_loader();if(rr.error)goto done;rr.flags|=4;
    rr.phase=3;rr.error=capture();if(!rr.error)rr.phase=4;
done:
    if(device>=0){i64 c=cl(device);device=-1;if(!rr.error && c)rr.error=c;}
    if(rr.error)rr.phase=90;
    save_new(JOB_DIR "/result",&rr,sizeof(rr),0600);
    /* Host ACK authorizes deleting only these fixed nonce tmpfs snapshots.
       Timeout performs the same bounded cleanup, without touching Work/p1. */
    if(!rr.error){i64 begin=now();for(u32 i=0;i<12001;i++){
        i64 n=read_all(JOB_DIR "/ack",command,sizeof(command));
        if(n==32 && same(command,(const u8*)"M4ACK001",8) && same(command+8,job_nonce,16) && *(u64*)(command+24)==1)break;
        i64 t=now();if(begin<0 || t<begin || t-begin>=1200)break;pause_poll();}}
    cleanup_chunks();rr.phase=5;save_new(JOB_DIR "/cleaned",&rr,sizeof(rr),0600);exit_child(rr.error?1:0);
}
__attribute__((naked,noreturn,visibility("default"))) void _start(void){
    __asm__ volatile("mov x0,sp\nbl reader_main\nmov x0,#127\nmov x8,#94\nsvc #0");
}
