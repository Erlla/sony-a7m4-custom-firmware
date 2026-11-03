#include <stdint.h>
#include "resource_config.h"
struct bank {uint8_t key[32];uint32_t valid,active,generation,revision,length,phase,crc,volume;};
struct meta {uint32_t generation,enabled,custom,volume;uint8_t key[32];};
#define F(n) (*(uint32_t *)(uintptr_t)(base+S_RUN+O_##n))
#define BANK(i) (((struct bank *)(uintptr_t)(base+S_RUN+O_bank))+(i))
extern int stop_barrier_original(uint64_t,uint32_t);
extern int cp_start_original(uint64_t,uint32_t,const uint32_t *);
extern int cp_reply_original(uint64_t,uint32_t);
extern int stop_async_original(uint64_t,uint32_t);
extern int hold_original(uint32_t);
extern void phase_original(uint32_t);

int prepare_resource(uint64_t base) {
    if(F(control)==1) {
        if(stop_barrier_original(base,0)<=0)return 0;
        struct meta *target=(struct meta *)(uintptr_t)(base+S_RUN+O_target);
        uint32_t args[4]={target->generation,F(revision),0,0};
        return cp_start_original(base,2,args);
    }
    int reply=cp_reply_original(base,2);
    if(reply<=0)return reply;
    if(reply-1==1) {
        /* Focus may be reserved while its custom bank is still OFF. The
         * shared-channel prepare barrier must cancel that native reservation. */
        for(uint32_t slot=0;slot<2;slot++) {
            uint32_t bit=1u<<slot;
            if((F(stop_mask)&bit) || (!slot && BANK(slot)->phase!=6))continue;
            int status=stop_async_original(base,slot?4:17);
            ((uint32_t *)(uintptr_t)(base+S_RUN+O_diag))[16]=(uint32_t)status;
            if(status!=1)return hold_original(0x4a0);
            F(stop_mask)|=bit;F(stop_pending)=1;F(stop_deadline)=F(tick)+5000;
            ((uint32_t *)(uintptr_t)(base+S_RUN+O_diag))[30]++;
        }
        return 0;
    }
    if(reply-1!=5)return hold_original(0x410);
    F(stop_pending)=0;F(stop_mask)=0;
    struct bank *bank=BANK(F(slot));
    struct meta *target=(struct meta *)(uintptr_t)(base+S_RUN+O_target);
    bank->valid=0;bank->phase=5;bank->generation=target->generation;bank->revision=F(revision);
    F(recovery_rebind_mask)&=~(1u<<F(slot));
    ((uint32_t *)(uintptr_t)(base+S_RUN+O_diag))[6]++;
    F(prepared)=1;phase_original(5);return 0;
}
