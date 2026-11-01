#include "cache_common.h"
#include "include/p4_library.h"

extern int32_t lut_read_original(p4l_context*,const p4l_entry*);
extern int32_t lut_verify_original(p4l_context*,const p4l_entry*);
typedef struct {uint8_t magic[8];uint32_t abi,bytes;p4l_entry entry;uint32_t crc;} cache_header;
_Static_assert(offsetof(p4_json_result,name_bytes)==sizeof(p4l_identity),"result identity prefix");
_Static_assert(sizeof(cache_header)==176,"cache header ABI");
_Static_assert(sizeof(cache_header)+sizeof(p4_json_result)<P4_JSON_MAX_BYTES,"scratch capacity");
static int canceled(p4l_context*c){return __atomic_load_n(&c->cancel,__ATOMIC_ACQUIRE)||(c->io.canceled&&c->io.canceled(c->io.opaque));}
static void filename(char*p,uint32_t record){const char*s=P4L_INTERNAL_DIR;while(*s)*p++=*s++;*p++='/';*p++='C';*p++=(char)('0'+record/10);*p++=(char)('0'+record%10);s=".BIN";while((*p++=*s++));}
static int read_full(p4l_context*c,uint64_t fd,void*data,uint32_t n){uint8_t*p=data;while(n){uint32_t got=0;if(canceled(c)||c->io.read(c->io.opaque,fd,p,n,&got)||!got||got>n)return -1;p+=got;n-=got;}return 0;}
static int write_full(p4l_context*c,uint64_t fd,const void*data,uint32_t n){const uint8_t*p=data;while(n){uint32_t got=0;if(canceled(c)||c->io.write(c->io.opaque,fd,p,n,&got)||!got||got>n)return -1;p+=got;n-=got;}return 0;}
static void persist(p4l_context*c,const p4l_entry*e){
 if(canceled(c))return;
 cache_header h={{'M','4','L','C','C','H','0','1'},P4_JSON_ENGINE_ABI,sizeof(p4_json_result),*e,0};
 h.crc=cache_crc_pair(&h,offsetof(cache_header,crc),&c->compiled,sizeof(c->compiled));
 char path[64];filename(path,e->record);uint64_t fd=0;
 if(c->io.open(c->io.opaque,path,P4L_REPLACE,&fd))return;
 int rc=write_full(c,fd,&h,sizeof(h));if(!rc)rc=write_full(c,fd,&c->compiled,sizeof(c->compiled));
 if(!rc)(void)c->io.sync(c->io.opaque,fd);
 (void)c->io.close(c->io.opaque,fd);
}
static int read_cache(p4l_context*c,const p4l_entry*e){
 char path[64];filename(path,e->record);uint64_t fd=0;
 if(c->io.open(c->io.opaque,path,P4L_READ,&fd))return 0;
 cache_header h;int rc=read_full(c,fd,&h,sizeof(h));
 if(!rc&&(!cache_equal(h.magic,"M4LCCH01",8)||h.abi!=P4_JSON_ENGINE_ABI||h.bytes!=sizeof(p4_json_result)||!cache_equal(&h.entry,e,sizeof(*e))))rc=-1;
 if(!rc)rc=read_full(c,fd,c->json,sizeof(p4_json_result));
 if(!rc){uint32_t got=0;if(c->io.read(c->io.opaque,fd,c->scratch,1,&got)||got)rc=-1;}
 if(c->io.close(c->io.opaque,fd))rc=-1;
 if(!rc&&h.crc!=cache_crc_pair(&h,offsetof(cache_header,crc),c->json,sizeof(p4_json_result)))rc=-1;
 if(!rc&&!cache_equal(c->json,&e->id,sizeof(e->id)))rc=-1;
 if(rc||canceled(c))return 0;
 cache_copy(&c->compiled,c->json,sizeof(c->compiled));return 1;
}
int32_t lut_read_cached(p4l_context*c,const p4l_entry*e){
 if(canceled(c))return P4L_CANCELED;
 /* This worker owns compiled. It is immutable between successful compiles;
  * identity excludes all per-slot micro-adjustments and strength. */
 if(cache_equal(&c->compiled,&e->id,sizeof(e->id)))return 0;
 if(read_cache(c,e))return 0;
 int32_t rc=lut_read_original(c,e);if(!rc)persist(c,e);return rc;
}
int32_t lut_verify_cached(p4l_context*c,const p4l_entry*e){
 int32_t rc=lut_verify_original(c,e);if(!rc)persist(c,e);return rc;
}
