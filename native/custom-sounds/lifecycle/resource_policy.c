#include <stdint.h>
#include "resource_config.h"
struct meta {uint32_t generation,enabled,custom,volume_step;uint8_t key[32];};
struct bank {uint8_t key[32];uint32_t valid,active,cp_generation,cp_revision,length,phase,crc,volume_step;};
_Static_assert(sizeof(struct meta)==48,"metadata ABI");
_Static_assert(sizeof(struct bank)==64,"bank ABI");
extern int meta_original(uint64_t,uint32_t,struct meta*);
extern int matches_original(const struct meta*,const struct bank*);
extern void phase_original(uint32_t);
extern void unready_original(uint32_t);
#define FIELD(n) (*(uint32_t*)(uintptr_t)(base+S_RUN+O_##n))
#define BANK(i) ((struct bank*)(uintptr_t)(base+S_RUN+O_bank)+(i))
typedef int(*ticket_fn)(uint32_t,uint32_t*,uint32_t*);

/* A failed policy read is not a positive revocation. Retain only an existing
 * preparation/active lease. The per-event playback gate stays unchanged. */
int maintenance_wanted(uint64_t base,uint32_t slot,uint32_t generation) {
    uint32_t current=0,route=0;
    int status=((ticket_fn)(uintptr_t)(base+0x8f9242c))(slot,&current,&route);
    if(!status)return current==generation && route==slot+2;
    struct bank*b=BANK(slot);
    return b->phase==5 || (b->phase==6 && b->valid);
}

/* A canceled PREPARED transfer must release the shared staging barrier through
 * the acknowledged OFF transaction. Discard partial bytes, never reuse them. */
int resource_idle(uint64_t base,uint32_t revision) {
    if(FIELD(last_scan)==revision && FIELD(tick)%50)return 0;
    for(uint32_t n=0;n<2;n++) {
        uint32_t slot=(FIELD(slot)+n)&1;struct meta m;
        if(meta_original(base,slot,&m))continue;
        int wanted=m.enabled&&m.custom&&maintenance_wanted(base,slot,m.generation);
        struct bank*b=BANK(slot);
        int same=b->valid&&matches_original(&m,b);
        if(!wanted && b->phase==5) {
            b->valid=0;FIELD(slot)=slot;FIELD(revision)=revision;FIELD(desired)=0;
            unready_original(slot);phase_original(8);return 0;
        }
        if(b->phase==6&&!b->active&&(!(FIELD(recovery_rebind_mask)&(1u<<slot))||!wanted)) {
            FIELD(slot)=slot;FIELD(revision)=revision;FIELD(desired)=0;phase_original(8);return 0;
        }
        if(!same&&wanted) {
            FIELD(slot)=slot;*(struct meta*)(uintptr_t)(base+S_RUN+O_target)=m;
            FIELD(revision)=revision;FIELD(reuse)=0;FIELD(desired)=1;
            unready_original(slot);phase_original(4);return 0;
        }
        if(same&&wanted&&!b->active) {
            FIELD(slot)=slot;*(struct meta*)(uintptr_t)(base+S_RUN+O_target)=m;
            FIELD(revision)=revision;FIELD(reuse)=1;FIELD(desired)=1;
            phase_original(b->phase==5?7:8);return 0;
        }
        if((!wanted||!same)&&b->active) {
            FIELD(slot)=slot;FIELD(revision)=revision;FIELD(desired)=0;
            unready_original(slot);phase_original(8);return 0;
        }
    }
    FIELD(last_scan)=revision;FIELD(slot)^=1;
    if(FIELD(tick)%250==0)phase_original(10);
    return 0;
}
