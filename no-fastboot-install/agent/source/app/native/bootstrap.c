/* One upload, fixed tmpfs executable, double-fork + exec. Parent returns to
 * Jiritsu. Never exits the loader process. No writable source/device handles.
 */
#include "linux_a64.h"
#include "job.h"
#include "worker_blob.h"
struct Launch {u8 magic[8],nonce[16];i64 version,phase,error,euid,loader_pid,cleanup,child,waited,wait_status,fs_available;};
static struct Launch launch;
static struct Fs fs;
__attribute__((visibility("default"),section(".init"))) void _init(void) {
    const u8 magic[]="M4BOOT01";
    for(u32 i=0;i<8;i++)launch.magic[i]=magic[i];
    for(u32 i=0;i<16;i++)launch.nonce[i]=job_nonce[i];
    launch.version=1;launch.phase=1;launch.euid=sc(175,0,0,0,0,0,0);launch.loader_pid=sc(172,0,0,0,0,0,0);
    launch.cleanup=unlink("/tmp/jiritsu/libJit.so");
    if(launch.euid || launch.cleanup) {launch.error=-13;return;}
    launch.error=tmpfs(&fs);if(launch.error)return;
    launch.fs_available=fs.bsize*fs.bavail;
    launch.error=sc(34,-100,(i64)JOB_DIR,0700,0,0,0);if(launch.error)return;
    launch.phase=2;launch.error=save_new(JOB_DIR "/worker",worker_blob,sizeof(worker_blob),0700);
    if(launch.error)goto finished;
    char parent[24];decimal(parent,(u64)launch.loader_pid);
    char*argv[3]={(char*)JOB_DIR "/worker",parent,0};
    i64 child=sc(220,17,0,0,0,0,0);
    if(!child) {
        i64 sid=sc(157,0,0,0,0,0,0);if(sid<0)exit_child(1);
        i64 grandchild=sc(220,17,0,0,0,0,0);
        if(grandchild<0)exit_child(1);
        if(grandchild)exit_child(0);
        i64 error=sc(221,(i64)argv[0],(i64)argv,0,0,0,0);
        save_new(JOB_DIR "/exec_failure",&error,sizeof(error),0600);exit_child(1);
    }
    launch.child=child;
    if(child<0) {launch.error=child;goto finished;}
    /* Wait only for the short-lived intermediate child, not the RAM worker. */
    u32 status=0;u32 attempts=0;i64 waited;
    do {waited=sc(260,child,(i64)&status,0,0,0,0);} while(waited==-4 && ++attempts<4);
    launch.waited=waited;launch.wait_status=status;
    if(waited!=child || status) {launch.error=waited<0?waited:-10;goto finished;}
    launch.phase=3;
finished:
    save_new(JOB_DIR "/launch",&launch,sizeof(launch),0600);
}
