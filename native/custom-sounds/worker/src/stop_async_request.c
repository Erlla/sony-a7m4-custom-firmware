/* Derived AP329 operation2 adapter; no firmware placement or original public
 * Stop symbol is claimed. Call only from the dedicated sound worker after
 * current policy says suppress. The native queue copies the stack packet.
 * Return1 means only native enqueue returned; never retirement or audibility.
 */
#include <stdint.h>
typedef void(*scoped_fn)(void*);
typedef void(*enqueue_fn)(const void*,int32_t);
int csnd_stop_async_request(uint64_t base,uint32_t kind){
 if(!kind||kind>255)return -3;
 uint8_t req[16]={0x0d,0x20,0x29,0x03,0x10,0,1,0x80,2,0,0,0,0,0,0,0};
 req[10]=(uint8_t)kind;
 uint64_t lock=base+0x8a933b0ull;
 ((scoped_fn)(uintptr_t)(base+0x183b6d4ull))((void*)(uintptr_t)lock);
 volatile uint32_t *pending=(volatile uint32_t*)(uintptr_t)(base+0x8a93394ull);
 if(*pending==0xffffffffu){((scoped_fn)(uintptr_t)(base+0x183b730ull))(&lock);return -4;}
 *pending=*pending+1;
 ((scoped_fn)(uintptr_t)(base+0x183b730ull))(&lock);
 ((enqueue_fn)(uintptr_t)(base+0x35b82a4ull))(req,16);
 return 1;
}

/* Global native async pending count. A zero alone is not a named job ACK or
 * physical idle; combine with stop-issued barrier and full original CP idle. */
uint32_t csnd_stop_pending(uint64_t base){
 uint32_t pending=0xffffffffu;
 ((void(*)(const void*,uint32_t*))(uintptr_t)(base+0x35bfd4cull))((const void*)0,&pending);
 return pending;
}
