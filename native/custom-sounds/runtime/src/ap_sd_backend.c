/* Source-bound original Fsys wrappers: no CUBE parser/model/parameter mutation. */
#include "ap_sd_backend.h"
extern void *csnd_malloc(size_t);
extern void csnd_free(void *);
extern void *memset(void *,int,size_t);
extern void *memcpy(void *,const void *,size_t);
extern int csnd_find_first(const char *,void *);
extern int csnd_find_next(void *);
extern int csnd_fsys_open(const char *,uint32_t,uint64_t *);
extern int csnd_fsys_read(uint64_t,void *,size_t,size_t *);
extern int csnd_fsys_close(uint64_t);
static const char sound_directory[]="/PRIVATE/SONY/PRO/SOUNDS/";
static int wav_name(const char *name,size_t bytes) {
    if(!ss_valid_name(name,bytes) || bytes<5)return 0;
    return name[bytes-4]=='.' && (name[bytes-3]|32)=='w' && (name[bytes-2]|32)=='a' && (name[bytes-1]|32)=='v';
}
static int card_path(const uint8_t *media,uint32_t card,const char *name,size_t bytes,char path[512]) {
    const uint8_t *entry;uint32_t status;char letter;
    if(!media || card>1 || !name || bytes>255)return SS_INVALID;
    entry=media+card*0x70;
    memcpy(&status,entry+0x1c,4);letter=(char)entry[0x19];
    /* Native3139794 accepts both kind3 and kind9 directory routes. The actual
     * internal export's kind9 is the same28ECD30->3231170 copied media object,
     * not a boolean card-ready field. Keep the user SOUNDS path explicit;
     * unknown media kinds and unbound/unsafe drive letters remain rejected.
     */
    if((status!=3 && status!=9) || letter<'A' || letter>'Z')return CSND_AP_NOT_READY;
    path[0]=letter;path[1]=':';
    memcpy(path+2,sound_directory,sizeof(sound_directory)-1);
    memcpy(path+2+sizeof(sound_directory)-1,name,bytes);
    path[2+sizeof(sound_directory)-1+bytes]=0;
    return SS_OK;
}
int csnd_ap_scan_wavs(const uint8_t *media,uint32_t card,uint32_t slot,csnd_picker_list *out) {
    char path[512];uint8_t *fileinfo;int status;uint32_t visited=0;
    if(!out)return SS_INVALID;
    memset(out,0,sizeof(*out));out->schema=1;out->slot=slot;out->card=card;
    if(slot>1){out->status=SS_INVALID;return SS_INVALID;}
    status=card_path(media,card,"*",1,path);
    if(status!=SS_OK){out->status=(uint32_t)status;return status;}
    fileinfo=(uint8_t *)csnd_malloc(4096);
    if(!fileinfo){out->status=SS_STORAGE;return SS_STORAGE;}
    memset(fileinfo,0,4096);
    if(slot==SS_FOCUS) {
        out->has_default=1;out->count=1;out->entries[0].kind=1;
    }
    status=csnd_find_first(path,fileinfo);
    while(status==0) {
        const char *name;size_t length=0;uint64_t bytes;
        if(++visited>4096){status=SS_LIMIT;break;}
        memcpy(&name,fileinfo,8);memcpy(&bytes,fileinfo+8,8);
        /* Original Fsys sets name pointer inside its 3112B FILEINFO. Reject a
         * malformed pointer before dereferencing, and bound NUL within object.
         */
        if(!name || (uintptr_t)name<(uintptr_t)fileinfo || (uintptr_t)name>=(uintptr_t)fileinfo+4096){status=SS_CORRUPT;break;}
        while(length<256 && (uintptr_t)name+length<(uintptr_t)fileinfo+4096 && name[length])++length;
        if(length<256 && (uintptr_t)name+length<(uintptr_t)fileinfo+4096 && !name[length] && !(fileinfo[0x26]&0x10) && bytes>0 && bytes<=CSND_AP_MAX_WAV_BYTES && wav_name(name,length)) {
            csnd_picker_entry *entry;
            if(out->count==CSND_PICKER_CAPACITY){status=SS_LIMIT;break;}
            entry=&out->entries[out->count++];entry->kind=2;entry->name_bytes=(uint32_t)length;entry->file_bytes=bytes;memcpy(entry->name,name,length);
        }
        status=csnd_find_next(fileinfo);
    }
    /* Real wrappers map raw Fsys status2 to END=4; all other failures stay
     * failures. No FindClose export exists; mirror original stack scanner's
     * borrowed FILEINFO lifetime, with 4KiB owned heap allocation.
     */
    csnd_free(fileinfo);
    if(status==4)status=SS_OK;
    if(status!=SS_OK){out->count=0;out->has_default=0;}
    out->status=(uint32_t)status;return status;
}
int csnd_ap_import_sd(const uint8_t *media,uint32_t card,uint32_t slot,const char *name,size_t name_bytes) {
    char path[512];uint8_t *buffer;size_t at=0;uint64_t handle=0;int status;
    if(slot>1 || !wav_name(name,name_bytes))return SS_INVALID;
    if(!csnd_ap_enabled(slot))return SS_DISABLED;
    status=card_path(media,card,name,name_bytes,path);
    if(status!=SS_OK)return status;
    buffer=(uint8_t *)csnd_malloc(CSND_AP_MAX_WAV_BYTES+1u);
    if(!buffer)return SS_STORAGE;
    status=csnd_fsys_open(path,0,&handle);
    if(status!=0){csnd_free(buffer);return CSND_AP_IO;}
    while(at<=CSND_AP_MAX_WAV_BYTES) {
        size_t count=0;
        status=csnd_fsys_read(handle,buffer+at,CSND_AP_MAX_WAV_BYTES+1u-at,&count);
        if(status!=0 || count>CSND_AP_MAX_WAV_BYTES+1u-at){status=CSND_AP_IO;break;}
        if(count==0)break;
        at+=count;
    }
    if(csnd_fsys_close(handle)!=0)status=CSND_AP_IO;
    if(status==0)status=at>CSND_AP_MAX_WAV_BYTES?SS_LIMIT:csnd_ap_import_bytes(slot,name,name_bytes,buffer,at);
    csnd_free(buffer);
    return status;
}
