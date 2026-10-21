/* Independent state: old SSND001/core/runtime/layout are untouched. */
#include <stdint.h>
#include <stddef.h>
static uint32_t volume_backup,volume_rollback;
static uint32_t packed=0x0505,ready,pending;
extern void *csnd_malloc(size_t);
extern void csnd_free(void *);
extern int csnd_open(const char *,int,...);
extern long csnd_read(int,void *,size_t);
extern long csnd_write(int,const void *,size_t);
extern int csnd_close(int),csnd_fsync(int);
extern int csnd_rename(const char *,const char *),csnd_remove(const char *);
extern int csnd_mkdir(const char *,unsigned int);
extern int *csnd_errno(void);
extern void *memcpy(void *,const void *,size_t);
extern void *memset(void *,int,size_t);

static const char directory[]="/setting/csnd";
static const char primary[]="/setting/csnd/volume.bin";
static const char temporary[]="/setting/csnd/volume.tmp";
static const char backup[]="/setting/csnd/volume.bak";
enum { READ_FLAGS=0x88000, WRITE_FLAGS=0x88241, DIR_FLAGS=0x8c000, EINTR_=4, ENOENT_=2, EEXIST_=17, RETRIES=16 };

static int open_retry(const char *path,int flags) {
    int result; unsigned int retries=0;
    do {result=csnd_open(path,flags,0600);} while(result<0 && *csnd_errno()==EINTR_ && ++retries<RETRIES);
    return result;
}
static int remove_optional(const char *path) {
    if(csnd_remove(path)==0)return 0;
    return *csnd_errno()==ENOENT_ ? 0 : -1;
}
static int sync_dir(void) {
    int fd=open_retry(directory,DIR_FLAGS),a,b;
    if(fd<0)return -1;
    a=csnd_fsync(fd);b=csnd_close(fd);
    return (a==0 && b==0) ? 0 : -1;
}
static int write_all(int fd,const uint8_t *data,size_t bytes) {
    size_t at=0;unsigned int retries=0;
    while(at<bytes) {
        long n=csnd_write(fd,data+at,bytes-at);
        if(n<0 && *csnd_errno()==EINTR_ && ++retries<RETRIES)continue;
        if(n<=0 || (size_t)n>bytes-at)return -1;
        at+=(size_t)n;retries=0;
    }
    return 0;
}
static int publish(const uint8_t *data,size_t bytes) {
    int fd=-1,old_moved=0,new_moved=0,ok=0;
    if(csnd_mkdir(directory,0700)<0 && *csnd_errno()!=EEXIST_)goto end;
    if(remove_optional(temporary)<0)goto end;
    fd=open_retry(temporary,WRITE_FLAGS);
    if(fd<0)goto end;
    if(write_all(fd,data,bytes)<0 || csnd_fsync(fd)<0)goto end;
    {int close_status=csnd_close(fd);fd=-1;if(close_status<0)goto end;}
    if(volume_backup) {
        /* RAM was restored from verified backup: primary is absent/corrupt.
         * Retain that only valid persistent generation throughout publication.
         */
        if(remove_optional(primary)<0)goto end;
    } else {
        if(remove_optional(backup)<0)goto end;
        if(csnd_rename(primary,backup)==0)old_moved=1;
        else if(*csnd_errno()!=ENOENT_)goto end;
    }
    if(csnd_rename(temporary,primary)<0)goto end;
    new_moved=1;
    if(sync_dir()<0)goto end;
    ok=1;
    volume_backup=0;
end:
    if(fd>=0)(void)csnd_close(fd);
    if(!ok) {
        int rollback=0;
        if(new_moved && remove_optional(primary)<0)rollback=1;
        if(old_moved && csnd_rename(backup,primary)<0)rollback=1;
        if(remove_optional(temporary)<0)rollback=1;
        if((old_moved || new_moved) && sync_dir()<0)rollback=1;
        volume_rollback=(uint32_t)rollback;
    }
    /* Keep a complete previous snapshot as backup; no cleanup success fiction. */
    return ok?0:-1;
}

extern uint32_t ss_crc32(const uint8_t *,size_t);
extern int csnd_ap_import_available(uint32_t);
static void put(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t get(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int read_volume(const char *path,uint32_t *value){
 uint8_t b[25];size_t at=0;int fd=open_retry(path,READ_FLAGS);unsigned retries=0;
 if(fd<0)return -1;
 while(at<25){long n=csnd_read(fd,b+at,25-at);if(n<0 && *csnd_errno()==EINTR_ && ++retries<RETRIES)continue;if(n<0){csnd_close(fd);return -1;}if(!n)break;if((size_t)n>25-at){csnd_close(fd);return -1;}at+=(size_t)n;retries=0;}
 if(csnd_close(fd)<0 || at!=24)return -1;
 if(get(b)!=0x4c4f5643 || get(b+4)!=1 || get(b+8)<1 || get(b+8)>10 || get(b+12)<1 || get(b+12)>10 || get(b+16)!=0 || get(b+20)!=ss_crc32(b,20))return -1;
 *value=get(b+8)|(get(b+12)<<8);return 0;
}
/* Called ONLY by dedicated persistent worker; no IO in GUI/event callers. */
int csnd_volume_worker_tick(void){
 uint32_t value;
 if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE)){
  if(read_volume(primary,&value)){if(read_volume(backup,&value)){value=0x0505;}else volume_backup=1;}
  __atomic_store_n(&packed,value,__ATOMIC_RELEASE);__atomic_store_n(&ready,1,__ATOMIC_RELEASE);
 }
 uint32_t request=__atomic_exchange_n(&pending,0,__ATOMIC_ACQ_REL);
 if(!request)return 0;
 uint32_t slot=(request>>8)&1,step=request&255;
 if(!csnd_ap_import_available(slot))return 6;
 value=__atomic_load_n(&packed,__ATOMIC_ACQUIRE);value=(value&~(255u<<(8*slot)))|(step<<(8*slot));
 uint8_t b[24];put(b,0x4c4f5643);put(b+4,1);put(b+8,value&255);put(b+12,value>>8);put(b+16,0);put(b+20,ss_crc32(b,20));
 if(publish(b,24))return 4;
 __atomic_store_n(&packed,value,__ATOMIC_RELEASE);return 0;
}
uint32_t csnd_volume_get(uint32_t slot){if(slot>1)return 5;return (__atomic_load_n(&packed,__ATOMIC_ACQUIRE)>>(8*slot))&255;}
int csnd_volume_blocked(uint32_t slot){return !__atomic_load_n(&ready,__ATOMIC_ACQUIRE)||!csnd_ap_import_available(slot);}
int csnd_volume_enqueue(uint32_t slot,uint32_t step){
 if(slot>1||step<1||step>10)return 1;if(csnd_volume_blocked(slot))return 6;
 uint32_t zero=0;return __atomic_compare_exchange_n(&pending,&zero,0x10000|(slot<<8)|step,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED)?0:8;
}
