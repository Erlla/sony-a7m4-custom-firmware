#include "cache_common.h"
#include "cache_config.h"
#include "../custom-sounds/worker/include/convert.h"
extern const uint8_t cache_anchor[];
extern int snd_convert_original(const uint8_t*,uint32_t,const ss_format*,uint8_t*,uint32_t,csnd_convert_info*,uint32_t);
typedef int(*open_fn)(const char*,uint32_t,uint32_t);
typedef int64_t(*rw_fn)(int,void*,uint64_t);
typedef int(*fd_fn)(int);
typedef int(*rename_fn)(const char*,const char*);
typedef struct {uint8_t magic[8];uint32_t abi,bytes,volume;uint8_t key[32];ss_format format;csnd_convert_info info;uint32_t crc;} sound_header;
_Static_assert(sizeof(sound_header)==116,"sound cache ABI");
static uint64_t bias(void){return (uintptr_t)cache_anchor-CACHE_VA;}
static int full_io(uint64_t base,int fd,void*p,uint32_t n,int write){
 uint8_t*d=p;rw_fn fn=(rw_fn)(uintptr_t)(base+(write?0x17163c0:0x1715270));
 while(n){int64_t got=fn(fd,d,n);if(got<=0||(uint64_t)got>n)return -1;d+=got;n-=(uint32_t)got;}return 0;
}
static void path(char*p,uint32_t slot,int temporary){
 const char*s="/setting/csnd/f0_";while(*s)*p++=*s++;*p++=(char)('0'+slot);s=temporary?".tmp":".bin";while((*p++=*s++));
}
static int restore(uint64_t base,uint32_t slot,const uint8_t*key,const ss_format*format,uint32_t volume,uint8_t*output,uint32_t capacity,csnd_convert_info*info){
 char name[40];path(name,slot,0);int fd=((open_fn)(uintptr_t)(base+0x1715170))(name,0x88000,0);
 if(fd<0)return 0;
 sound_header h;int rc=full_io(base,fd,&h,sizeof(h),0);
 if(!rc&&(!cache_equal(h.magic,"M4F0C001",8)||h.abi!=1||h.volume!=volume||!cache_equal(h.key,key,32)||!cache_equal(&h.format,format,sizeof(*format))||h.info.encoded_bytes>CSND_MAX_F0_BYTES||h.bytes!=h.info.encoded_bytes+CSND_F0_GUARD||h.bytes>capacity))rc=-1;
 if(!rc)rc=full_io(base,fd,output,h.bytes,0);
 if(!rc){uint8_t end;int64_t got=((rw_fn)(uintptr_t)(base+0x1715270))(fd,&end,1);if(got)rc=-1;}
 if(((fd_fn)(uintptr_t)(base+0x17173f0))(fd))rc=-1;
 if(!rc&&h.crc!=cache_crc_pair(&h,offsetof(sound_header,crc),output,h.bytes))rc=-1;
 if(rc)return 0;
 for(uint32_t i=h.bytes;i<capacity;i++)output[i]=0;
 *info=h.info;return 1;
}
static void persist(uint64_t base,uint32_t slot,const uint8_t*key,const ss_format*format,uint32_t volume,uint8_t*output,const csnd_convert_info*info){
 sound_header h={{'M','4','F','0','C','0','0','1'},1,info->encoded_bytes+CSND_F0_GUARD,volume,{0},*format,*info,0};
 cache_copy(h.key,key,32);h.crc=cache_crc_pair(&h,offsetof(sound_header,crc),output,h.bytes);
 char temp[40],name[40];path(temp,slot,1);path(name,slot,0);
 int fd=((open_fn)(uintptr_t)(base+0x1715170))(temp,0x88241,0600);if(fd<0)return;
 int rc=full_io(base,fd,&h,sizeof(h),1);if(!rc)rc=full_io(base,fd,output,h.bytes,1);
 if(!rc)rc=((fd_fn)(uintptr_t)(base+0x17175b0))(fd);
 if(((fd_fn)(uintptr_t)(base+0x17173f0))(fd))rc=-1;
 if(!rc)(void)((rename_fn)(uintptr_t)(base+0x1714e50))(temp,name);
}
int snd_convert_cached(const uint8_t*pcm,uint32_t bytes,const ss_format*format,uint8_t*output,uint32_t capacity,csnd_convert_info*info,uint32_t volume){
 uint64_t base=bias();uint8_t*state=(void*)(uintptr_t)(base+S_RUN);
 uint32_t slot=*(uint32_t*)(void*)(state+S_SLOT);
 uint8_t*target=state+S_TARGET;uint8_t key[32];cache_copy(key,target+16,32);
 /* Only the original resource convert callsite enters here. Its detached PCM,
  * metadata generation and staging ownership checks have already completed. */
 int use_cache=slot<2&&volume>=1&&volume<=10&&volume==*(uint32_t*)(void*)(target+12)&&capacity<=CSND_MAX_STAGING_BYTES;
 if(use_cache&&restore(base,slot,key,format,volume,output,capacity,info))return 0;
 int rc=snd_convert_original(pcm,bytes,format,output,capacity,info,volume);
 if(!rc&&use_cache)persist(base,slot,key,format,volume,output,info);
 return rc;
}
