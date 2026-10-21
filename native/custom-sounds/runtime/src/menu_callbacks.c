/* Native descriptor callback ABI. Durable writes only execute in the original
 * nativeSequence worker; no menu getter/setter performs filesystem IO. */
#include "menu_callbacks.h"
extern void *memset(void *,int,size_t);
extern void *csnd_native_manager_get(void);
extern uint32_t csnd_native_shutter_60a_get(void);
extern uint32_t csnd_original_menu_blocked(uint32_t);
typedef struct {uint32_t gate,generation,status[2];csnd_private_session *session[2];} menu_requests;
static menu_requests requests;
static int enter(void){uint32_t expected=0;return __atomic_compare_exchange_n(&requests.gate,&expected,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);}
static void leave(void){__atomic_store_n(&requests.gate,0,__ATOMIC_RELEASE);}
static void collect(uint32_t slot) {
    csnd_private_session *s=requests.session[slot];uint32_t phase;
    if(!s)return;phase=__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE);
    if(phase!=CSND_COMPLETE && phase!=CSND_CANCELED)return;
    requests.status[slot]=s->status;requests.session[slot]=0;csnd_private_session_release(s);
    __atomic_store_n(&csnd_ap_state.pending[slot],csnd_ap_enabled(slot),__ATOMIC_RELEASE);
}
static int rejected(uint32_t slot,int status) {
    requests.status[slot]=(uint32_t)status;
    __atomic_store_n(&csnd_ap_state.pending[slot],csnd_ap_enabled(slot),__ATOMIC_RELEASE);
    return status;
}
static uint32_t getter(uint32_t slot) {
    if(enter()){collect(slot);leave();}
    /* Original1C15674→1C04200 calls this getter to translate the selected raw
     * value to an option alias. It must see the staged native setter value,
     * while import availability continues to use only committed core state. */
    if(!__atomic_load_n(&csnd_ap_state.initialized,__ATOMIC_ACQUIRE) ||
       (slot==SS_ELECTRONIC && csnd_ap_mechanical_pending()))return 1;
    return __atomic_load_n(&csnd_ap_state.pending[slot],__ATOMIC_ACQUIRE)?0u:1u;
}
uint32_t csnd_menu_electronic_getter(void){return getter(SS_ELECTRONIC);}
uint32_t csnd_menu_focus_getter(void){return getter(SS_FOCUS);}
static void setter(uint32_t slot,uint32_t raw) {
    if(raw<=1)__atomic_store_n(&csnd_ap_state.pending[slot],raw^1u,__ATOMIC_RELEASE);
}
void csnd_menu_electronic_setter(uint32_t raw){setter(SS_ELECTRONIC,raw);}
void csnd_menu_focus_setter(uint32_t raw){setter(SS_FOCUS,raw);}
static int commit(uint32_t slot,uint32_t alias,uint32_t base) {
    uint8_t empty_media[0x150];uint32_t enabled,shutter=SS_SHUTTER_ELECTRONIC,raw,generation;int status;
    void *manager;csnd_private_session *session;
    if(alias<base || alias>base+1)return SS_INVALID;enabled=(alias-base)^1u;
    if(!__atomic_load_n(&csnd_ap_state.initialized,__ATOMIC_ACQUIRE))return CSND_AP_NOT_READY;
    if(!enter())return CSND_AP_BUSY;collect(slot);
    if(requests.session[slot]){leave();return CSND_AP_BUSY;}
    if(slot==SS_ELECTRONIC && enabled) {
        raw=csnd_native_shutter_60a_get();
        if(raw!=1 || csnd_ap_mechanical_pending()){status=rejected(slot,SS_INCOMPATIBLE);leave();return status;}
    }
    manager=csnd_native_manager_get();
    if(!manager || requests.generation==0x3fffffffu){status=rejected(slot,CSND_AP_NOT_READY);leave();return status;}
    generation=0x40000000u+(++requests.generation);memset(empty_media,0,sizeof(empty_media));
    session=csnd_private_session_create(generation,slot,empty_media,0);
    if(!session){status=rejected(slot,SS_LIMIT);leave();return status;}
    status=csnd_private_submit(manager,session,CSND_ENABLE,0,enabled,shutter);
    requests.status[slot]=(uint32_t)status;
    if(status==SS_OK)requests.session[slot]=session;
    else {csnd_private_session_release(session);rejected(slot,status);}
    leave();return status;
}
int csnd_menu_electronic_commit(uint32_t alias){return commit(SS_ELECTRONIC,alias,5607);}
int csnd_menu_focus_commit(uint32_t alias){return commit(SS_FOCUS,alias,5609);}
/* Profile+50 is the native exclusion callback/cache byte2:1 means blocked.
 * Its polarity differs from the runtime's positive import_available API. */
int csnd_menu_electronic_available(void){return !csnd_ap_import_available(SS_ELECTRONIC);}
int csnd_menu_focus_available(void){return !csnd_ap_import_available(SS_FOCUS);}
uint32_t csnd_menu_import_blocked(uint32_t mid) {
    if(mid==1594)return (uint32_t)csnd_menu_electronic_available();
    if(mid==1597)return (uint32_t)csnd_menu_focus_available();
    return csnd_original_menu_blocked(mid);
}
uint32_t csnd_menu_zero(void){return 0;}
int csnd_menu_no_direct_import(uint32_t unused){(void)unused;return CSND_AP_NOT_READY;}
int csnd_menu_request_status(uint32_t slot,uint32_t *queued,uint32_t *status) {
    if(queued)*queued=0;if(status)*status=SS_INVALID;
    if(slot>1 || !queued || !status)return SS_INVALID;
    if(!enter())return CSND_AP_BUSY;collect(slot);
    *queued=requests.session[slot]!=0;*status=requests.status[slot];leave();return SS_OK;
}
