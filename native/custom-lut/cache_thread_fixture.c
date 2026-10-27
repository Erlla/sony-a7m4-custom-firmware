/* Host-only schedule stress. Never linked into a firmware image. */
#include "cache_core.h"
#include <windows.h>
static p6c_cache cache;
static uint64_t advertised[P6C_BANKS];
static uint32_t payload[P6C_BANKS][64];
static uint32_t errors, reads, writes, rejected;
void fixture_init(void) {
    p6c_init(&cache); errors=reads=writes=rejected=0;
    for(unsigned i=0;i<P6C_BANKS;i++)advertised[i]=0;
}
static uint32_t pattern(uint64_t g,unsigned k) {
    return ((uint32_t)g*0x9e3779b9u) ^ (uint32_t)(g>>32) ^ (k*0x01010101u);
}
void fixture_writer(uint32_t n) {
    for(uint32_t i=0;i<n;i++) {
        p6c_lease l={0};
        while(p6c_reserve(&cache,&l)==P6C_BUSY)SwitchToThread();
        for(unsigned k=0;k<64;k++) {
            payload[l.slot][k]=pattern(l.generation,k);
            if(k==31)SwitchToThread();
        }
        if(p6c_publish(&cache,&l))__atomic_fetch_add(&errors,1,__ATOMIC_RELAXED);
        __atomic_store_n(&advertised[l.slot],l.generation,__ATOMIC_RELEASE);
        __atomic_fetch_add(&writes,1,__ATOMIC_RELAXED);
        if(p6c_release(&cache,&l))__atomic_fetch_add(&errors,1,__ATOMIC_RELAXED);
    }
}
void fixture_reader(uint32_t seed,uint32_t n) {
    for(uint32_t i=0;i<n;i++) {
        seed=seed*1664525u+1013904223u;
        uint32_t slot=seed%P6C_BANKS;
        uint64_t generation=__atomic_load_n(&advertised[slot],__ATOMIC_ACQUIRE);
        if(!generation) {SwitchToThread(); continue;}
        p6c_lease l={0};
        if(p6c_acquire(&cache,slot,generation,&l)) {
            __atomic_fetch_add(&rejected,1,__ATOMIC_RELAXED); continue;
        }
        for(unsigned pass=0;pass<2;pass++) {
            for(unsigned k=0;k<64;k++)
                if(payload[slot][k]!=pattern(generation,k))
                    __atomic_fetch_add(&errors,1,__ATOMIC_RELAXED);
            SwitchToThread();
        }
        __atomic_fetch_add(&reads,1,__ATOMIC_RELAXED);
        if(p6c_release(&cache,&l))__atomic_fetch_add(&errors,1,__ATOMIC_RELAXED);
    }
}
uint32_t fixture_stat(uint32_t n) {
    if(n==0)return errors; if(n==1)return reads;
    if(n==2)return writes; if(n==3)return rejected;
    uint32_t count=0; for(unsigned i=0;i<P6C_BANKS;i++)count+=p6c_refs(&cache,i);
    return count;
}
