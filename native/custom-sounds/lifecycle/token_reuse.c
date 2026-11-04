#include <stdint.h>
typedef uint32_t u32;
typedef uint8_t u8;
struct rpc {
    u32 state,endpoint,destination,command,token,deadline,reason,attempted;
    u32 polls,receive_rc,actual_bytes,source,free_rc,late,session,operation;
    u32 next_token,expected_source;
    u8 reply[40];
};
extern u32 private_parts_original(uint64_t,struct rpc *,u32,u32,const u32 *,const u8 *,u32,u32);
#define RUN 0x8ff77c8ull

/* The one resource worker sends once and admits another transaction only
 * after its ACK is consumed and the retained endpoint is drained. Timed-out
 * reads are the exception: their tokens stay permanently quarantined in the
 * existing ledger, including after their late ACK is consumed. Reuse only
 * completed identities; never reset the endpoint, a live RPC or the ledger. */
u32 private_parts_reuse(uint64_t base,struct rpc *c,u32 op,u32 slot,
                        const u32 *args,const u8 *data,u32 bytes,u32 deadline) {
    if((uintptr_t)c==(uintptr_t)(base+RUN+112) && c->state==1 && !c->attempted) {
        volatile const u32 *count=(volatile const u32 *)(uintptr_t)(base+RUN+1908);
        volatile const u32 *endpoint=(volatile const u32 *)(uintptr_t)(base+RUN+1912);
        volatile const uint16_t *retired=(volatile const uint16_t *)(uintptr_t)(base+RUN+1780);
        u32 n=*count;
        if(n>64 || (n && *endpoint!=c->endpoint) || c->next_token>0xffff) {
            c->reason=9;c->state=4;return 4;
        }
        u32 next=c->next_token;
        for(u32 attempts=0;attempts<=n;attempts++) {
            next=next==0xffff?1:next+1;
            u32 blocked=0;
            for(u32 i=0;i<n;i++)if(retired[i]==next){blocked=1;break;}
            if(!blocked){c->next_token=next-1;break;}
        }
    }
    return private_parts_original(base,c,op,slot,args,data,bytes,deadline);
}
