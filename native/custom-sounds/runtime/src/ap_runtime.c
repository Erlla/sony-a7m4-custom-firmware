/* Actual camera POSIX adapter. Linked source-bound PLT thunks provide IO.
 * It is not a host filesystem shim and is never called from event threads.
 */
#include "ap_runtime.h"
#include "ap_native_policy.h"

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

csnd_runtime csnd_ap_state;
static const char directory[]="/setting/csnd";
static const char primary[]="/setting/csnd/settings.bin";
static const char temporary[]="/setting/csnd/settings.tmp";
static const char backup[]="/setting/csnd/settings.bak";
enum { READ_FLAGS=0x88000, WRITE_FLAGS=0x88241, DIR_FLAGS=0x8c000, EINTR_=4, ENOENT_=2, EEXIST_=17, RETRIES=16 };

static int acquire(void) {
    uint32_t expected=0;
    return __atomic_compare_exchange_n(&csnd_ap_state.busy,&expected,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
}
static int drain_mechanical(void);
static void release(int status) {
    /* Only a private storage worker owning busy performs the queued commit.
     * A later request remains latched and is serviced by the next worker. */
    int pending_status=drain_mechanical();
    if(status==SS_OK && pending_status!=SS_OK)status=pending_status;
    csnd_ap_state.status=(uint32_t)status;
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
}
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
    if(csnd_ap_state.loaded_from_backup) {
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
    csnd_ap_state.loaded_from_backup=0;
end:
    if(fd>=0)(void)csnd_close(fd);
    if(!ok) {
        int rollback=0;
        if(new_moved && remove_optional(primary)<0)rollback=1;
        if(old_moved && csnd_rename(backup,primary)<0)rollback=1;
        if(remove_optional(temporary)<0)rollback=1;
        if((old_moved || new_moved) && sync_dir()<0)rollback=1;
        csnd_ap_state.rollback_failure=(uint32_t)rollback;
    }
    /* Keep a complete previous snapshot as backup; no cleanup success fiction. */
    return ok?0:-1;
}
static int durable_commit(void *context,const ss_state *candidate) {
    csnd_runtime *runtime=(csnd_runtime *)context;
    size_t bytes=ss_snapshot_size(candidate),written=0;
    uint8_t *buffer;
    if(!bytes || bytes>CSND_AP_MAX_SNAPSHOT)return -1;
    buffer=(uint8_t *)csnd_malloc(bytes);
    if(!buffer)return -1;
    if(ss_snapshot_write(candidate,buffer,bytes,&written)!=SS_OK || written!=bytes || publish(buffer,bytes)<0) {
        csnd_free(buffer);return -1;
    }
    runtime->commit_owner=buffer;runtime->commit_bytes=bytes;
    return 0;
}
static int reseat_snapshot(int status) {
    csnd_runtime *runtime=&csnd_ap_state;
    if(status==SS_OK && runtime->commit_owner) {
        uint8_t *old=runtime->snapshot_owner;
        /* Serialized our validated candidate. Rebind all borrowed WAV pointers
         * to one owned AP64 allocation before source/old buffers can disappear.
         */
        int restore=ss_snapshot_restore(&runtime->state,runtime->commit_owner,runtime->commit_bytes);
        if(restore!=SS_OK) {
            /* Fail closed, retain both buffers; no dangling waveform pointer. */
            ss_init(&runtime->state);
            runtime->status=SS_CORRUPT;return SS_CORRUPT;
        }
        runtime->snapshot_owner=runtime->commit_owner;runtime->snapshot_bytes=runtime->commit_bytes;
        runtime->commit_owner=0;runtime->commit_bytes=0;
        if(old)csnd_free(old);
    }
    __atomic_store_n(&runtime->pending[0],runtime->state.slots[0].enabled,__ATOMIC_RELEASE);
    __atomic_store_n(&runtime->pending[1],runtime->state.slots[1].enabled,__ATOMIC_RELEASE);
    return status;
}
static int drain_mechanical(void) {
    csnd_runtime *runtime=&csnd_ap_state;
    int status;
    if(!runtime->initialized || !__atomic_exchange_n(&runtime->mechanical_off_pending,0,__ATOMIC_ACQ_REL))return SS_OK;
    status=ss_native_shutter_changed(&runtime->state,SS_SHUTTER_MECHANICAL,durable_commit,runtime);
    status=reseat_snapshot(status);
    runtime->mechanical_off_status=(uint32_t)status;
    if(status!=SS_OK)__atomic_store_n(&runtime->mechanical_off_pending,1,__ATOMIC_RELEASE);
    return status;
}
int csnd_ap_mechanical_pending(void) {
    return __atomic_load_n(&csnd_ap_state.mechanical_off_pending,__ATOMIC_ACQUIRE)!=0;
}
int csnd_ap_apply_pending_native(void) {
    int status;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized){__atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);return CSND_AP_NOT_READY;}
    status=drain_mechanical();
    csnd_ap_state.status=(uint32_t)status;
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
    return status;
}
static int read_snapshot(const char *path) {
    csnd_runtime *runtime=&csnd_ap_state;
    uint8_t *buffer=(uint8_t *)csnd_malloc(CSND_AP_MAX_SNAPSHOT+1u);
    int fd,status=SS_STORAGE;size_t at=0;unsigned int retries=0;
    if(!buffer)return SS_STORAGE;
    fd=open_retry(path,READ_FLAGS);
    if(fd<0){csnd_free(buffer);return SS_STORAGE;}
    while(at<=CSND_AP_MAX_SNAPSHOT) {
        long count=csnd_read(fd,buffer+at,CSND_AP_MAX_SNAPSHOT+1u-at);
        if(count<0 && *csnd_errno()==EINTR_ && ++retries<RETRIES)continue;
        if(count<0 || (size_t)count>CSND_AP_MAX_SNAPSHOT+1u-at)break;
        if(count==0){status=at?SS_OK:SS_CORRUPT;break;}
        at+=(size_t)count;retries=0;
    }
    if(csnd_close(fd)<0)status=SS_STORAGE;
    if(status==SS_OK) {
        ss_state candidate;
        status=ss_snapshot_restore(&candidate,buffer,at);
        if(status==SS_OK && (candidate.slots[0].wav_bytes>CSND_AP_MAX_WAV_BYTES || candidate.slots[1].wav_bytes>CSND_AP_MAX_WAV_BYTES))status=SS_LIMIT;
        if(status==SS_OK)memcpy(&runtime->state,&candidate,sizeof(candidate));
    }
    if(status==SS_OK){runtime->snapshot_owner=buffer;runtime->snapshot_bytes=at;}
    else csnd_free(buffer);
    return status;
}
int csnd_ap_load_once(void) {
    int status;
    if(!acquire())return CSND_AP_BUSY;
    if(csnd_ap_state.initialized){release(SS_OK);return SS_OK;}
    ss_init(&csnd_ap_state.state);
    status=read_snapshot(primary);
    if(status!=SS_OK) {
        status=read_snapshot(backup);
        csnd_ap_state.loaded_from_backup=(status==SS_OK);
    }
    /* No valid durable state means factory OFF/native default. No success
     * notification is emitted for absent/corrupt files. */
    __atomic_store_n(&csnd_ap_state.initialized,1,__ATOMIC_RELEASE);
    __atomic_store_n(&csnd_ap_state.pending[0],csnd_ap_state.state.slots[0].enabled,__ATOMIC_RELEASE);
    __atomic_store_n(&csnd_ap_state.pending[1],csnd_ap_state.state.slots[1].enabled,__ATOMIC_RELEASE);
    release(status);return status;
}
const ss_state *csnd_ap_get_state(void){return &csnd_ap_state.state;}
int csnd_ap_playback_ticket(uint32_t event,uint32_t *generation,uint32_t *route) {
    ss_native native;ss_playback plan;int status;
    if(generation)*generation=0;
    if(route)*route=SS_SUPPRESS;
    if(!generation || !route)return SS_INVALID;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized)status=CSND_AP_NOT_READY;
    else {
        status=csnd_ap_read_native(0x60a,0,0,&native);
        if(status==SS_OK)status=ss_plan(&csnd_ap_state.state,&native,event,&plan);
        if(status==SS_OK){*generation=csnd_ap_state.state.generation;*route=plan.route;}
    }
    /* Ticket is pointer-free. Never drain pending durable IO or overwrite
     * storage diagnostics in an incoming-event observer. Native getters are
     * successive reads, not one atomically captured exposure policy. */
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
    return status;
}
int csnd_ap_copy_playback(uint32_t slot,uint32_t expected_generation,uint8_t *dst,
                         uint32_t capacity,ss_format *out,uint32_t *bytes) {
    ss_native native;ss_playback plan;int status;
    if(out)memset(out,0,sizeof(*out));if(bytes)*bytes=0;
    if(slot>SS_FOCUS || !dst || !out || !bytes || !capacity)return SS_INVALID;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized)status=CSND_AP_NOT_READY;
    else if(csnd_ap_state.state.generation!=expected_generation)status=SS_INCOMPATIBLE;
    else {
        status=csnd_ap_read_native(0x60a,0,0,&native);
        if(status==SS_OK)status=ss_plan(&csnd_ap_state.state,&native,slot==SS_ELECTRONIC?SS_ELECTRONIC_EXPOSURE:SS_FOCUS_CONFIRMED,&plan);
        if(status==SS_OK && plan.route!=(slot==SS_ELECTRONIC?SS_PLAY_ELECTRONIC:SS_PLAY_FOCUS))status=SS_DISABLED;
        if(status==SS_OK && (!plan.pcm || !plan.format.data_bytes || plan.format.data_bytes>capacity))status=SS_LIMIT;
        if(status==SS_OK) {
            memcpy(dst,plan.pcm,plan.format.data_bytes);
            if(slot==SS_ELECTRONIC && csnd_ap_mechanical_pending())status=SS_DISABLED;
            else {*out=plan.format;out->data_offset=0;*bytes=plan.format.data_bytes;}
        }
    }
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);return status;
}
int csnd_ap_menu_view(uint32_t slot,ss_menu_view *out) {
    int status;
    if(!out)return SS_INVALID;
    memset(out,0,sizeof(*out));
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized)status=CSND_AP_NOT_READY;
    else {
        status=ss_get_menu_view(&csnd_ap_state.state,slot,out);
        if(status==SS_OK && slot==SS_ELECTRONIC && csnd_ap_mechanical_pending()) {
            out->enabled=0;out->import_selectable=0;
        }
        if(status==SS_OK && !csnd_ap_state.picker_ready) {
            out->import_selectable=0;out->can_select_default=0;
        }
    }
    /* A pure GUI view must not overwrite the last import/storage diagnostic. */
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
    return status;
}
int csnd_ap_enabled(uint32_t slot) {
    int enabled;
    if(slot>=2 || !acquire())return 0;
    enabled=csnd_ap_state.initialized && csnd_ap_state.state.slots[slot].enabled && !(slot==SS_ELECTRONIC && csnd_ap_mechanical_pending());
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
    return enabled;
}
int csnd_ap_import_available(uint32_t slot) {
    int available;
    if(slot>=2 || !acquire())return 0;
    available=csnd_ap_state.initialized && csnd_ap_state.picker_ready && csnd_ap_state.state.slots[slot].enabled && !(slot==SS_ELECTRONIC && csnd_ap_mechanical_pending());
    __atomic_store_n(&csnd_ap_state.busy,0,__ATOMIC_RELEASE);
    return available;
}
int csnd_ap_note_native_parameter(uint32_t parameter,uint32_t raw) {
    csnd_runtime *runtime=&csnd_ap_state;
    switch(parameter) {
    case 0x604:
        __atomic_store_n(&runtime->native_silent_raw,raw,__ATOMIC_RELAXED);__atomic_fetch_or(&runtime->native_valid_mask,1,__ATOMIC_RELEASE);return SS_OK;
    case 0x825:
        __atomic_store_n(&runtime->native_audio_raw,raw,__ATOMIC_RELAXED);__atomic_fetch_or(&runtime->native_valid_mask,2,__ATOMIC_RELEASE);return SS_OK;
    case 0x697:
        __atomic_store_n(&runtime->native_focus_raw,raw,__ATOMIC_RELAXED);__atomic_fetch_or(&runtime->native_valid_mask,4,__ATOMIC_RELEASE);return SS_OK;
    case 0x60a:case 0x60b:
        __atomic_store_n(&runtime->native_shutter_prm,parameter,__ATOMIC_RELAXED);__atomic_store_n(&runtime->native_shutter_raw,raw,__ATOMIC_RELAXED);__atomic_fetch_or(&runtime->native_valid_mask,8,__ATOMIC_RELEASE);
        if((parameter==0x60a && raw==0)||(parameter==0x60b && raw==1))
            __atomic_store_n(&runtime->mechanical_off_pending,1,__ATOMIC_RELEASE);
        return SS_OK;
    default:return SS_INVALID;
    }
}
int csnd_ap_set_enabled(uint32_t slot,uint32_t enabled,uint32_t shutter) {
    int status;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized){release(CSND_AP_NOT_READY);return CSND_AP_NOT_READY;}
    if(slot==SS_ELECTRONIC && enabled && csnd_ap_mechanical_pending()) {release(SS_INCOMPATIBLE);return SS_INCOMPATIBLE;}
    status=ss_set_enabled(&csnd_ap_state.state,slot,enabled,shutter,durable_commit,&csnd_ap_state);
    status=reseat_snapshot(status);release(status);return status;
}
int csnd_ap_native_shutter_changed(uint32_t shutter) {
    int status;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized){release(CSND_AP_NOT_READY);return CSND_AP_NOT_READY;}
    status=ss_native_shutter_changed(&csnd_ap_state.state,shutter,durable_commit,&csnd_ap_state);
    status=reseat_snapshot(status);release(status);return status;
}
int csnd_ap_focus_default(void) {
    int status;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized){release(CSND_AP_NOT_READY);return CSND_AP_NOT_READY;}
    status=ss_focus_default(&csnd_ap_state.state,durable_commit,&csnd_ap_state);
    status=reseat_snapshot(status);release(status);return status;
}
int csnd_ap_import_bytes(uint32_t slot,const char *name,size_t name_bytes,const uint8_t *wav,size_t wav_bytes) {
    int status;
    if(wav_bytes>CSND_AP_MAX_WAV_BYTES)return SS_LIMIT;
    if(!acquire())return CSND_AP_BUSY;
    if(!csnd_ap_state.initialized){release(CSND_AP_NOT_READY);return CSND_AP_NOT_READY;}
    status=ss_import(&csnd_ap_state.state,slot,name,name_bytes,wav,wav_bytes,durable_commit,&csnd_ap_state);
    status=reseat_snapshot(status);release(status);return status;
}
