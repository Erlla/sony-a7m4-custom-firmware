/* A native Start that already owns the Sysnd current row cannot be refused
 * after its property callback: native code has already published busy/active.
 * Those fields keep PREPARE/OFF from retiring or writing this immutable bank.
 * New/unadmitted requests still use the complete existing owner admission. */
#include "owner_abi.h"
#define W(a) (*(volatile const u32 *)(a))
#define B(a) (*(volatile const u8 *)(a))
extern u32 owner_start_fallback(void*,const u8*,u32);

u32 sound_accepted_start(void*object,const u8*request,u32 mode) {
    u32 kind=request[2];
    struct sound_slot*s=&csnd_cp_owner.slot[kind==4];
    u32 same=1;
    if(request!=(const u8*)0xf57bac || request[0]!=1 ||
       (kind!=4 && kind!=17) || B(0xf57b4c)!=1 ||
       W(0x121f118)!=2 || W(0x121f130)!=1)
        return owner_start_fallback(object,request,mode);
    for(u32 i=0;i<32;i++)if(request[i]!=B(0xf57b4c+i))same=0;
    /* PIN's native admission has checked the path mask before this callback.
     * Do not grant the same shortcut to a private kind17 arriving via APP. */
    if(!same || (kind==17 && object!=(void*)0x106a610) ||
       (kind==4 && object!=(void*)0x106a614 && object!=(void*)0x106a610))
        return owner_start_fallback(object,request,mode);
    u32 phase=__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE);
    if(phase!=OWN_ACTIVE && !(kind==4 && phase==OWN_OFF))
        return owner_start_fallback(object,request,mode);
    /* No gate or quiesce bit is cleared. Native busy is the existing lease:
     * writers can inspect/quiesce it but cannot reach PREPARED or OFF yet. */
    __atomic_fetch_add(&csnd_cp_owner.calls[kind==4],1,__ATOMIC_RELAXED);
    csnd_cp_owner.last_kind=kind;csnd_cp_owner.last_native_rc=0xfffffffeu;
    u32 rc=((u32(*)(void*,const u8*,u32))0x11e9fb)(object,request,mode);
    csnd_cp_owner.last_native_rc=rc;
    return rc;
}
