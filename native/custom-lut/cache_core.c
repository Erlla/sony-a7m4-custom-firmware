#include "cache_core.h"

/* state = 1 + 2*references for published banks, 0 for a writer-owned or empty
 * bank. The final release and the writer's claim compete on this SAME word.
 * A separate `ready` flag and refcount would leave a check-then-overwrite race.
 */
static int valid(const p6c_lease *l) { return l && l->slot<P6C_BANKS && l->generation; }
static void clear(p6c_lease *l) { l->held=0; l->generation=0; l->slot=0; }
void p6c_init(p6c_cache *c) {
    for (uint32_t i=0;i<P6C_BANKS;i++) {
        c->bank[i].state=0; c->bank[i].generation=0; c->bank[i].reserved=0;
    }
    c->cursor=0;
}
int p6c_reserve(p6c_cache *c,p6c_lease *l) {
    if (!c || !l || l->held) return P6C_ARGUMENT;
    for (uint32_t k=0;k<P6C_BANKS;k++) {
        uint32_t i=c->cursor+k; if (i>=P6C_BANKS) i-=P6C_BANKS;
        p6c_bank *b=&c->bank[i];
        uint32_t s=__atomic_load_n(&b->state,__ATOMIC_ACQUIRE);
        if ((s!=0 && s!=P6C_READY) || b->reserved) continue;
        if (!__atomic_compare_exchange_n(&b->state,&s,0,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) continue;
        b->reserved=1;
        /* No reader exists while generation or payload is changed. The 64-bit
         * generation is therefore not concurrently read/written on ARM32.
         */
        if (!++b->generation) b->generation=1;
        l->slot=i; l->generation=b->generation; l->held=2;
        c->cursor=i+1; if(c->cursor==P6C_BANKS)c->cursor=0;
        return P6C_OK;
    }
    return P6C_BUSY;
}
int p6c_publish(p6c_cache *c,p6c_lease *l) {
    if (!c || !valid(l) || l->held!=2) return P6C_ARGUMENT;
    p6c_bank *b=&c->bank[l->slot];
    if (!b->reserved || b->generation!=l->generation || b->state) return P6C_STALE;
    b->reserved=0; l->held=1;
    /* Publish WITH the writer's lease: no unprotected interval before the
     * prepared bank is attached to a native owner / identity transaction.
     */
    __atomic_store_n(&b->state,3u,__ATOMIC_RELEASE);
    return P6C_OK;
}
int p6c_abort(p6c_cache *c,p6c_lease *l) {
    if (!c || !valid(l) || l->held!=2) return P6C_ARGUMENT;
    p6c_bank *b=&c->bank[l->slot];
    if (!b->reserved || b->generation!=l->generation || b->state) return P6C_STALE;
    b->reserved=0; clear(l); return P6C_OK;
}
int p6c_acquire_current(p6c_cache *c,uint32_t slot,p6c_lease *l) {
    if (!c || !l || l->held || slot>=P6C_BANKS) return P6C_ARGUMENT;
    p6c_bank *b=&c->bank[slot];
    uint32_t s=__atomic_load_n(&b->state,__ATOMIC_ACQUIRE);
    for (;;) {
        if (!(s&P6C_READY)) return P6C_BUSY;
        if ((s>>1)>=P6C_MAX_REFS) return P6C_BUSY;
        if (__atomic_compare_exchange_n(&b->state,&s,s+2u,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED)) break;
    }
    /* Pin FIRST, then inspect generation. Reading generation before pinning
     * is a C data race and can tear on ARM32 while a writer reuses a bank.
     */
    l->generation=b->generation; l->slot=slot; l->held=1; return P6C_OK;
}
int p6c_acquire(p6c_cache *c,uint32_t slot,uint64_t generation,p6c_lease *l) {
    if (!generation) return P6C_ARGUMENT;
    int r=p6c_acquire_current(c,slot,l); if(r)return r;
    if(l->generation==generation)return P6C_OK;
    p6c_release(c,l);return P6C_STALE;
}
void p6c_drop_owned(p6c_cache *c,uint32_t slot) {
    __atomic_fetch_sub(&c->bank[slot].state,2u,__ATOMIC_RELEASE);
}
int p6c_clone(p6c_cache *c,const p6c_lease *parent,p6c_lease *child) {
    if (!valid(parent) || parent->held!=1) return P6C_ARGUMENT;
    return p6c_acquire(c,parent->slot,parent->generation,child);
}
int p6c_release(p6c_cache *c,p6c_lease *l) {
    if (!c || !valid(l) || l->held!=1) return P6C_ARGUMENT;
    /* Each lease has exactly one owner. Owners serialize clone/release and
     * never copy the struct to manufacture another reference. Releasing a
     * held reference cannot observe a different generation by construction.
     */
    p6c_bank *b=&c->bank[l->slot];
    if (b->generation!=l->generation) return P6C_STALE;
    uint32_t s=__atomic_load_n(&b->state,__ATOMIC_RELAXED);
    if (!(s&P6C_READY) || s<3) return P6C_STALE;
    clear(l); __atomic_fetch_sub(&b->state,2u,__ATOMIC_RELEASE); return P6C_OK;
}
uint32_t p6c_refs(const p6c_cache *c,uint32_t i) {
    return c && i<P6C_BANKS ? __atomic_load_n(&c->bank[i].state,__ATOMIC_ACQUIRE)>>1 : 0;
}
