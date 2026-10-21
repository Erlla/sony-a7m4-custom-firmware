#include "private_worker.h"
extern void *csnd_malloc(size_t);
extern void csnd_free(void *);
extern void *memcpy(void *,const void *,size_t);
extern void *memset(void *,int,size_t);
extern void csnd_native_base_construct(void *);
extern void csnd_native_base_destroy(void *);
extern void csnd_native_sized_delete(void *,size_t);
extern char csnd_native_sequence_rtti;
extern void csnd_native_empty_cancel(void *),csnd_native_empty_finish(void *);
extern void csnd_native_register(void *,void *,uint32_t,uint32_t,uint32_t);
/* Root-owned absolute entry8F9C000. It only publishes an atomic pending bit;
 * its own worker performs player creation/policy updates outside this job. */
extern void csnd_sound_config_changed(void);
extern void csnd_sound_startup(void);
static int enter(csnd_private_session *s) {
    uint32_t expect=0;
    return __atomic_compare_exchange_n(&s->gate,&expect,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
}
static void leave(csnd_private_session *s){__atomic_store_n(&s->gate,0,__ATOMIC_RELEASE);}
static void retain(csnd_private_session *s){__atomic_add_fetch(&s->references,1,__ATOMIC_RELAXED);}
void csnd_private_session_release(csnd_private_session *s) {
    if(s && __atomic_sub_fetch(&s->references,1,__ATOMIC_ACQ_REL)==0)csnd_free(s);
}
csnd_private_session *csnd_private_session_create(uint32_t generation,uint32_t slot,const uint8_t *media,uint32_t card) {
    csnd_private_session *s;
    if(!generation || slot>1 || !media || card>1)return 0;
    s=csnd_malloc(sizeof(*s));if(!s)return 0;
    memset(s,0,sizeof(*s));s->references=1;s->generation=generation;s->slot=slot;s->card=card;s->selected=0xffffffffu;
    memcpy(s->media,media,sizeof(s->media));return s;
}
int csnd_private_cancel(csnd_private_session *s,uint32_t generation) {
    if(!s || s->generation!=generation)return SS_INVALID;
    if(!enter(s))return CSND_AP_BUSY;
    uint32_t phase=__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE);
    do {
        if(phase==CSND_RUNNING){leave(s);return CSND_AP_BUSY;}
    } while(!__atomic_compare_exchange_n(&s->phase,&phase,CSND_CANCELED,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
    leave(s);return SS_OK;
}
int csnd_private_list_copy(csnd_private_session *s,uint32_t generation,csnd_picker_list *out) {
    int status;
    if(!out)return SS_INVALID;
    memset(out,0,sizeof(*out));
    if(!s || s->generation!=generation)return SS_INVALID;
    if(!enter(s))return CSND_AP_BUSY;
    if(__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE)!=CSND_COMPLETE)status=CSND_AP_BUSY;
    else if(s->status!=SS_OK)status=(int)s->status;
    else {memcpy(out,&s->list,sizeof(*out));status=SS_OK;}
    leave(s);return status;
}
csnd_private_job *csnd_private_job_create(csnd_private_session *s,uint32_t operation,uint32_t row,uint32_t enabled,uint32_t shutter) {
    csnd_private_job *j;csnd_picker_entry *entry=0;
    if(!s || operation<CSND_SCAN || operation>CSND_COLD_LOAD || enabled>1 || shutter>SS_SHUTTER_EFCS || !enter(s))return 0;
    uint32_t phase=__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE);
    if(phase==CSND_QUEUED || phase==CSND_RUNNING || phase==CSND_CANCELED){leave(s);return 0;}
    if(operation==CSND_IMPORT) {
        if(row>=s->list.count || s->list.status!=SS_OK){leave(s);return 0;}
        entry=&s->list.entries[row];
        if(entry->kind!=2 || !ss_valid_name(entry->name,entry->name_bytes)){leave(s);return 0;}
    }
    if(operation==CSND_DEFAULT && (s->slot!=SS_FOCUS || row>=s->list.count || s->list.entries[row].kind!=1)){leave(s);return 0;}
    j=csnd_malloc(sizeof(*j));if(!j){leave(s);return 0;}
    memset(j,0,sizeof(*j));
    /* The actual original base constructor owns separate1B0 context. All
     * custom immutable identity lives after16B, never native+1B0/+1AC fields. */
    csnd_native_base_construct(j);
    /* Build vtable at run time with PC-relative addresses, no absolute pointer
     * constants needing unrecorded ELF RELATIVE fixups. */
    j->private_vtable[0]=0;j->private_vtable[1]=(uintptr_t)&csnd_native_sequence_rtti;
    j->private_vtable[2]=(uintptr_t)csnd_private_job_destroy;j->private_vtable[3]=(uintptr_t)csnd_private_job_delete;
    j->private_vtable[4]=(uintptr_t)csnd_private_job_execute;
    j->private_vtable[5]=(uintptr_t)csnd_private_job_cancel;j->private_vtable[6]=(uintptr_t)csnd_private_job_abandon;
    j->vtable=&j->private_vtable[2];
    j->reserved[0]=0; /* Private magic/type fields initialized before publication. */
    j->magic=0x534a4e44;j->schema=1;j->generation=s->generation;j->operation=operation;j->slot=s->slot;j->card=s->card;j->row=row;
    j->enabled=enabled;j->shutter=shutter;j->session=s;memcpy(j->media,s->media,sizeof(j->media));
    if(entry){j->name_bytes=entry->name_bytes;memcpy(j->name,entry->name,entry->name_bytes);}
    retain(s);s->status=CSND_AP_BUSY;__atomic_store_n(&s->phase,CSND_QUEUED,__ATOMIC_RELEASE);leave(s);return j;
}
void csnd_private_job_execute(csnd_private_job *j) {
    csnd_private_session *s;int status;
    if(!j || j->magic!=0x534a4e44 || j->schema!=1 || !(s=j->session))return;
    uint32_t phase=CSND_QUEUED;
    if(j->generation!=s->generation || j->slot!=s->slot)return;
    /* The worker never returns merely because the UI holds its bounded copy
     * gate: the native consumer retires every returned job without retry.
     * QUEUED->RUNNING arbitrates queued cancel; RUNNING owns list/status until
     * the release COMPLETE publication. UI readers only consume COMPLETE. */
    if(!__atomic_compare_exchange_n(&s->phase,&phase,CSND_RUNNING,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
    /* This is the private worker entry. Native parameter notifications only
     * latch; all durable sound IO is here, including coldload and switches. */
    switch(j->operation) {
    case CSND_SCAN:status=csnd_ap_scan_wavs(j->media,j->card,j->slot,&s->list);break;
    case CSND_IMPORT:status=csnd_ap_import_sd(j->media,j->card,j->slot,j->name,j->name_bytes);break;
    case CSND_ENABLE:status=csnd_ap_set_enabled(j->slot,j->enabled,j->shutter);break;
    case CSND_DEFAULT:status=csnd_ap_focus_default();break;
    case CSND_NATIVE_DRAIN:status=csnd_ap_apply_pending_native();break;
    case CSND_COLD_LOAD:status=csnd_ap_load_once();break;
    default:status=SS_INVALID;break;
    }
    /* Coldload may initialize safe factory defaults while reporting an invalid
     * persisted image. That state still needs the original focus policy. */
    if(j->operation!=CSND_SCAN &&
       (status==SS_OK || (j->operation==CSND_COLD_LOAD &&
        __atomic_load_n(&csnd_ap_state.initialized,__ATOMIC_ACQUIRE))))
        {csnd_sound_startup();csnd_sound_config_changed();}
    /* UI cannot cancel a running transaction as if it were already canceled.
     * It receives BUSY; an eventual completion must match this exact session.
     * An unregistered completion sink is never called as a success fiction. */
    s->status=(uint32_t)status;
    __atomic_store_n(&s->phase,CSND_COMPLETE,__ATOMIC_RELEASE);
}
void csnd_private_job_cancel(csnd_private_job *j) {
    if(j && j->magic==0x534a4e44 && j->session)
        csnd_private_cancel(j->session,j->generation);
}
void csnd_private_job_abandon(csnd_private_job *j) {
    uint32_t phase=CSND_QUEUED;
    if(j && j->magic==0x534a4e44 && j->session)
        __atomic_compare_exchange_n(&j->session->phase,&phase,CSND_CANCELED,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
void csnd_private_job_destroy(csnd_private_job *j) {
    csnd_private_session *s;
    if(!j || j->magic!=0x534a4e44)return;
    csnd_private_job_abandon(j);
    s=j->session;j->session=0;j->magic=0;
    csnd_native_base_destroy(j);csnd_private_session_release(s);
}
void csnd_private_job_delete(csnd_private_job *j){csnd_private_job_destroy(j);csnd_free(j);}
int csnd_private_submit(void *manager,csnd_private_session *s,uint32_t operation,uint32_t row,uint32_t enabled,uint32_t shutter) {
    csnd_private_job *j;
    if(!manager)return SS_INVALID;
    j=csnd_private_job_create(s,operation,row,enabled,shutter);
    if(!j)return CSND_AP_BUSY;
    /* Registry takes the original index, not a function pointer. Existing
     * scan group is reused; immutable private tags select our operation. */
    csnd_native_register(manager,j,0x1bd,0,1);
    return SS_OK;
}
