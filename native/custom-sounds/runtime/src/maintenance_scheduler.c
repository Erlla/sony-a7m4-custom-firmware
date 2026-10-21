/* Runs only in the proved original post-virtual-execute window32EDF8C.
 * Original group mutex was released32EDF50, metadata/group reacquisition
 * starts32EDFA8/32EDFB4. This window queues work, never performs durable IO.
 * No self retry: after a BUSY/error maintenance job retires, another unrelated
 * native job completion is required. No OS lock is assumed to requeue a job.
 * First actual unrelated native completion proves this manager/consumer is
 * running; real libcstatfs/access checks additionally prove the settings mount
 * type/readonly flag and this process's write permission before automatic arm.
 * The guard performs read-only syscalls, never creates or writes a file. */
#include "maintenance_scheduler.h"
extern void *memset(void *,int,size_t);
extern void *csnd_native_manager_get(void);
extern void *csnd_native_dlsym(void *,const char *);
static int (*native_statfs)(const char *,void *);
static int (*native_access)(const char *,int);
static int setting_ready(void) {
    _Alignas(16) uint64_t opaque[32];
    /* Source615libcstatfsBC130 uses the A64statfs syscall43. The exported
     * A64UAPI layout has f_type@0/f_flags@80 and size120;256B is bounded and
     * aligned. Resolution failures and unknown filesystems remain closed. */
    if(!native_statfs)native_statfs=(int (*)(const char *,void *))csnd_native_dlsym(0,"statfs");
    if(!native_access)native_access=(int (*)(const char *,int))csnd_native_dlsym(0,"access");
    if(!native_statfs || !native_access)return 0;
    memset(opaque,0,sizeof(opaque));
    return native_statfs("/setting",opaque)==0 && opaque[0]==0x4d44 && !(opaque[10]&1u) && native_access("/setting",2)==0;
}
typedef struct {
    uint32_t gate,armed,cold_done,cold_status,mechanical_status,generation;
    void *manager;
    csnd_private_session *session;
    uint32_t operation,reserved;
} maintenance;
static maintenance state;
static int enter(void) {
    uint32_t expected=0;
    return __atomic_compare_exchange_n(&state.gate,&expected,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
}
static void leave(void){__atomic_store_n(&state.gate,0,__ATOMIC_RELEASE);}
static void collect_completion(void) {
    csnd_private_session *session=state.session;uint32_t phase;int status;
    if(!session)return;
    phase=__atomic_load_n(&session->phase,__ATOMIC_ACQUIRE);
    if(phase!=CSND_COMPLETE && phase!=CSND_CANCELED)return;
    status=(int)session->status;
    if(state.operation==CSND_COLD_LOAD) {
        state.cold_status=(uint32_t)status;
        /* Backend one-shot load records factory OFF on missing/corrupt/IO.
         * Preserve that nonzero status rather than inventing successful load. */
        if(__atomic_load_n(&csnd_ap_state.initialized,__ATOMIC_ACQUIRE)) {
            state.cold_done=1;
            /* The final assembly contract installs the native registries,
             * controllers, canonical exclusion/name callbacks and original
             * request/close/timer hooks together. Coldload completes only on
             * this retained private worker after actualmanager+VFAT/rw/access
             * readiness. Missing/corrupt state gives factory OFF but still
             * permits an explicit later enable/import. Initial BSS stays0. */
            if(__atomic_load_n(&state.armed,__ATOMIC_ACQUIRE))
                __atomic_store_n(&csnd_ap_state.picker_ready,1,__ATOMIC_RELEASE);
        }
    } else state.mechanical_status=(uint32_t)status;
    state.session=0;state.operation=0;
    csnd_private_session_release(session);
}
int csnd_maintenance_arm(void *manager,uint32_t mask) {
    if(!manager || manager!=csnd_native_manager_get() || mask!=3)return CSND_AP_NOT_READY;
    if(!enter())return CSND_AP_BUSY;
    if(state.armed){int result=state.manager==manager?SS_OK:SS_INVALID;leave();return result;}
    state.manager=manager;state.generation=0x80000000u;
    state.cold_status=CSND_AP_NOT_READY;state.mechanical_status=CSND_AP_NOT_READY;
    __atomic_store_n(&state.armed,1,__ATOMIC_RELEASE);leave();return SS_OK;
}
void csnd_maintenance_after_execute(void *manager,void *job) {
    uint8_t empty_media[0x150];uint32_t operation;int status;uintptr_t *vtable;
    csnd_private_session *session;
    if(!manager || !job || manager!=csnd_native_manager_get() ||
       (__atomic_load_n(&state.armed,__ATOMIC_ACQUIRE) && manager!=state.manager) || !enter())return;
    /* Stable retained session is the completion mailbox. If a prior postexec
     * callback lost the short gate, its native job may already be destroyed;
     * collect without dereferencing that retired job on this later callback. */
    collect_completion();
    vtable=*(uintptr_t **)job;
    /* Inspect only the original guaranteed vptr/execute slot before reading
     * any extended private fields. Bare original native Sequence may be16B. */
    if(vtable && vtable[2]==(uintptr_t)csnd_private_job_execute) {
        leave();return; /* Never enqueue from our own completion. */
    }
    if(!state.armed) {
        if(!setting_ready()){leave();return;}
        state.manager=manager;state.generation=0x80000000u;
        state.cold_status=CSND_AP_NOT_READY;state.mechanical_status=CSND_AP_NOT_READY;
        __atomic_store_n(&state.armed,1,__ATOMIC_RELEASE);
    }
    if(state.session){leave();return;}
    operation=!state.cold_done?CSND_COLD_LOAD:(csnd_ap_mechanical_pending()?CSND_NATIVE_DRAIN:0);
    if(!operation || state.generation==0xffffffffu){leave();return;}
    memset(empty_media,0,sizeof(empty_media));
    session=csnd_private_session_create(++state.generation,SS_ELECTRONIC,empty_media,0);
    if(!session){leave();return;}
    status=csnd_private_submit(manager,session,operation,0,0,0);
    if(status!=SS_OK){csnd_private_session_release(session);leave();return;}
    state.session=session;state.operation=operation;
    leave();
}
int csnd_maintenance_view_copy(csnd_maintenance_view *out) {
    if(!out)return SS_INVALID;memset(out,0,sizeof(*out));
    if(!enter())return CSND_AP_BUSY;
    *out=(csnd_maintenance_view){state.armed,state.cold_done,state.cold_status,state.mechanical_status,state.session!=0,state.generation};
    leave();return SS_OK;
}
