/* Dedicated worker only, except two pointer-free atomic snapshot readers.
 * Never install without actual CP owner + finite transport integration proof.
 * No original power/mode/photo progress function consults this manager.
 */
#include "resource.h"
#include "native_transport.h"
#include "convert.h"
#include "ap_runtime.h"

extern uint32_t csnd_event_revision(void);
extern int csnd_event_resource_epoch(uint32_t expected_revision);
extern uint32_t csnd_volume_get(uint32_t);
extern uint32_t csnd_sysnd_async_once(uint32_t kind);
extern int csnd_stop_async_request(uint64_t base,uint32_t kind);
_Static_assert(sizeof(csnd_runtime)==800,"pinned runtime634 ABI");
_Static_assert(sizeof(ss_format)==28,"pinned detached PCM ABI");
#define LD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define ST(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define FN(t,o) ((t)(uintptr_t)(base+(o)))
typedef int(*ticket_fn)(uint32_t,uint32_t*,uint32_t*);
typedef int(*copy_fn)(uint32_t,uint32_t,uint8_t*,uint32_t,ss_format*,uint32_t*);
typedef void*(*alloc_fn)(uint64_t);
typedef void(*free_fn)(void*);
typedef uint32_t(*crc_fn)(const uint8_t*,uint64_t);
enum {R_INIT,R_CLAIM,R_BIND,R_IDLE,R_PREPARE,R_CONVERT,R_TRANSFER,R_COMMIT,R_POLICY,R_ROLLBACK,R_QUERY,R_HOLD};
enum {CP_BIND=1,CP_PREPARE=2,CP_COMMIT=3,CP_POLICY=4,CP_QUERY=5,CP_COPY=6};
enum {CP_OK,CP_BUSY,CP_INVALID,CP_NOTBOUND,CP_STALE,CP_PREPARED,CP_ACTIVE,CP_OFF};
enum {D_SCHEMA,D_STATE,D_ERROR,D_TICK,D_CLAIM,D_BOUND,D_PREPARES,D_CONVERTS,
 D_TRANSFERS,D_COMMITS,D_POLICIES,D_FOCUS,D_READY0,D_READY1,D_LAST_SLOT,D_LAST_CP_PHASE,
 D_LAST_NATIVE,D_BYTES,D_GENERATION,D_REVISION,D_DISPATCH_CALLS,D_DISPATCH_RETURNED,
 D_DISABLED,D_STALE,D_UNCERTAIN,D_ROLLBACK,D_RPC_REASON,D_XFER_REASON,D_SESSION,D_MASK,D_RESERVED0,D_RESERVED1};
struct unit {uint64_t physical;uint32_t handle,capacity,owned,side;};
struct bank {uint8_t key[32];uint32_t valid,active,cp_generation,cp_revision,length,phase,crc,volume_step;};
struct meta {uint32_t generation,enabled,custom,volume_step;uint8_t key[32];};
struct manager {
 ns_rpc allocation,control;struct unit unit[6];
 struct bank bank[2];struct meta target;
 uint32_t diag[32],cp_stats[8],state,index,slot,transfer_index,tick,revision,last_scan;
 uint32_t desired,prepared,reuse,rollback_index,initialized;
 uint32_t resume_state,resume_slot,resume_revision,resume_desired,checked_revision;
 uint32_t stop_pending,stop_deadline,stop_mask,revoke_mask;
 uint32_t driver_record[48],driver_staging[24],driver_sequence[2],driver_missed[2];
 uint32_t driver_stage,driver_slot,driver_expected,driver_valid,driver_version,driver_tick,driver_error,driver_epoch;
 uint8_t *pcm,*encoded;
 uint32_t fault[26],recovery_state,retired_drops,recovery_identity[8];
 uint32_t recovery_rounds,recovery_next_tick,recovery_rebind_mask,fault_query_stage,current_fault[20];
 uint32_t bind_diag[54],bind_stage,bind_tries,bind_collect,bind_version,bind_tick;
 struct unit provisional[6];
 uint32_t reclaim_attempt,reclaim_stage,reclaim_index;
 uint16_t retired_query_token[64];
 uint32_t retired_count,retired_endpoint,readonly_series,query_snapshot_version;
 uint32_t control_receive_tick,query_selector;
 uint32_t focus_diag[8],focus_stage[8],focus_expected;
};
static struct manager run;
static void copy(void*d,const void*s,uint32_t n){uint8_t*a=d;const uint8_t*b=s;while(n--)*a++=*b++;}
static uint32_t r16(const uint8_t*p){return p[0]|(uint32_t)p[1]<<8;}
static uint32_t r32(const uint8_t*p){return r16(p)|(uint32_t)r16(p+2)<<16;}
static uint64_t r64(const uint8_t*p){return r32(p)|(uint64_t)r32(p+4)<<32;}
static int equal(const uint8_t*a,const uint8_t*b){uint32_t v=0;for(uint32_t i=0;i<32;i++)v|=a[i]^b[i];return !v;}
static void phase(uint32_t state){run.state=state;ST(run.diag[D_STATE],state);}
enum {F_MAGIC,F_SCHEMA,F_ERROR,F_PRESTATE,F_CONTEXT,F_OP,F_CMD,F_TOKEN,F_ENDPOINT,F_SESSION,F_DEST,F_SOURCE,F_ACTUAL_SOURCE,F_DEADLINE,F_TICK,F_RECEIVE,F_BYTES,F_LATE,F_REPLY_STATE,F_POLLS,F_ATTEMPTS,F_ACKS,F_RECOVERY_ERROR,F_RECOVERY_TICK,F_QUERY_STAGE,F_RECOVERY_STAGE};
static void fault_capture(uint32_t error,const ns_rpc*c){
 int publish=!LD(run.fault[F_MAGIC]);
 uint32_t f[26]={0};f[F_SCHEMA]=1;f[F_ERROR]=error;f[F_PRESTATE]=run.state;
 f[F_CONTEXT]=c==&run.allocation?1u:c==&run.control?2u:0u;
 f[F_TICK]=run.tick;f[F_QUERY_STAGE]=run.driver_stage;
 if(c){f[F_OP]=c->operation;f[F_CMD]=c->command;f[F_TOKEN]=c->token;
  f[F_ENDPOINT]=c->endpoint;f[F_SESSION]=c->session;f[F_DEST]=c->destination;
  f[F_SOURCE]=c->expected_source;f[F_ACTUAL_SOURCE]=c->source;f[F_DEADLINE]=c->deadline;f[F_RECEIVE]=c->receive_rc;
  f[F_BYTES]=c->actual_bytes;f[F_LATE]=c->late;f[F_REPLY_STATE]=c->state;f[F_POLLS]=c->polls;
 }
 if(c){
  for(uint32_t i=0;i<20;i++)run.current_fault[i]=f[i];
  run.current_fault[F_MAGIC]=0x544c4146u;run.fault_query_stage=run.driver_stage;
  if(!(run.readonly_series&&run.recovery_state==2&&c==&run.control&&
       c->operation==CP_QUERY&&c->command==0x807e&&c->reason==NT_REASON_TIMEOUT)){
   run.recovery_state=run.recovery_rounds=0;run.readonly_series=0;
  }
  ST(run.fault[F_RECOVERY_ERROR],0);
 }
 if(!publish)return;
 for(uint32_t i=1;i<26;i++)ST(run.fault[i],f[i]);
 /* Immutable first-fault identity publishes only after every field exists. */
 ST(run.fault[F_MAGIC],0x544c4146u);
}
static int hold(uint32_t error){
 if(run.reclaim_attempt){run.reclaim_stage=4;ST(run.fault[F_RECOVERY_ERROR],error);ST(run.fault[F_RECOVERY_TICK],run.tick);}
 fault_capture(error,0);if(error!=0x106u){run.current_fault[F_ERROR]=error;
 if(run.recovery_state||run.recovery_rebind_mask){ST(run.fault[F_RECOVERY_ERROR],error);ST(run.fault[F_RECOVERY_TICK],run.tick);}}ST(run.diag[D_ERROR],error);ST(run.diag[D_UNCERTAIN],1);ST(run.diag[D_READY0],0);ST(run.diag[D_READY1],0);ST(run.diag[D_FOCUS],0);phase(R_HOLD);return (int)error;}
static int meta(uint64_t base,uint32_t slot,struct meta*out){
 csnd_runtime*s=(csnd_runtime*)(uintptr_t)(base+0x8fc8008ull);uint32_t idle=0;
 if(!__atomic_compare_exchange_n(&s->busy,&idle,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED))return 8;
 int rc=10;
 if(s->initialized){
  out->generation=s->state.generation;out->enabled=s->state.slots[slot].enabled;
  out->volume_step=csnd_volume_get(slot);out->custom=s->state.slots[slot].custom;copy(out->key,s->state.slots[slot].sha256,32);rc=0;
 }
 __atomic_store_n(&s->busy,0,__ATOMIC_RELEASE);return rc;
}
static int matches(const struct meta*m,const struct bank*b){return equal(m->key,b->key)&&m->volume_step==b->volume_step;}
static int wanted(uint64_t base,uint32_t slot,uint32_t generation){
 uint32_t g=0,r=0;
 return !FN(ticket_fn,0x8f9242c)(slot,&g,&r)&&g==generation&&r==slot+2;
}
/* Native CP serializer/source contract, independently checked against actual
 * complete CP. This is not derived by masking the destination route bits. */
#define CP_REPLY_SOURCE 0x61003cu
static int retired_packet(const ns_rpc*c){
 if(c->free_rc||c->actual_bytes!=40||c->source!=CP_REPLY_SOURCE||
    c->endpoint!=LD(run.retired_endpoint)||c->command!=0x807e||
    c->destination!=0x9061003c||c->session!=c->endpoint||r16(c->reply)!=0x807e||
    r16(c->reply+2)||r16(c->reply+4)!=24||r32(c->reply+8)!=c->endpoint||
    r32(c->reply+12)!=CP_QUERY)return 0;
 uint32_t token=r16(c->reply+6);
 uint32_t count=LD(run.retired_count);if(count>64)return 0;
 for(uint32_t i=0;i<count;i++)if(token==run.retired_query_token[i]&&token!=c->token)return 1;
 return 0;
}
static uint32_t control_poll(uint64_t base,ns_rpc*c){
 uint32_t previous=c->state,reason=c->reason;
 /* A fresh receive must prove both size and successful native free in this
  * invocation. rc0/wireNULL and receive failures cannot reuse old metadata. */
 if(c==&run.control&&c->attempted&&(previous==NT_PENDING||previous==NT_UNCERTAIN)){
  if(run.control_receive_tick==run.tick)return previous;
  run.control_receive_tick=run.tick;
  c->actual_bytes=0;c->free_rc=0xffffffffu;
 }
 uint32_t s=csnd_rpc_poll(base,c,run.tick);
 if(c!=&run.control||s!=NT_UNCERTAIN||c->reason!=NT_REASON_PROTOCOL||!retired_packet(c))return s;
 /* No eviction/TTL. A retired read's payload never reaches any consumer,
  * including a later BIND/COPY/COMMIT consumer sharing this endpoint. */
  run.retired_drops++;
  if((int32_t)(run.tick-c->deadline)>=0){c->late=1;c->reason=NT_REASON_TIMEOUT;ST(c->state,NT_UNCERTAIN);return NT_UNCERTAIN;}
  c->reason=reason;ST(c->state,previous);return previous;
}
static int rpc_wait(uint64_t base,ns_rpc*c){
 uint32_t s=control_poll(base,c);
 ST(run.diag[D_RPC_REASON],c->reason);
 if(s==NT_UNCERTAIN){fault_capture(0x100u+c->reason,c);hold(0x100u+c->reason);return -1;}
 return s==NT_REPLIED;
}
static int cp_start(uint64_t base,uint32_t op,const uint32_t a[4]){
 uint32_t s=csnd_private_start(base,&run.control,op,run.slot,a,run.tick+2500);
 if(s==NT_PENDING)run.control.expected_source=CP_REPLY_SOURCE;
 if(s==NT_PENDING&&op==CP_QUERY)run.query_selector=0x80000000u|(a[0]&255u)|((run.slot&255u)<<8)|((a[1]&255u)<<16);
 if(s==NT_PENDING)return 0;
 return hold(0x200u+run.control.reason);
}
static int control_tail(uint64_t base,ns_rpc*c){
 uint32_t stat[4]={0};int rc=FN(int(*)(uint32_t,uint32_t*),0x17158b0)(c->endpoint,stat);
 if(rc)return -hold(0x721);
 if(!stat[0]&&!stat[1]&&!stat[3])return 1;
 if(run.control_receive_tick==run.tick)return 0;
 ns_rpc shadow=*c;shadow.state=NT_PENDING;shadow.attempted=1;shadow.reason=0;
 shadow.actual_bytes=0;shadow.free_rc=0xffffffffu;run.control_receive_tick=run.tick;
 (void)csnd_rpc_poll(base,&shadow,run.tick);
 if(!retired_packet(&shadow))return -hold(0x722); /* Tail fault, not a current ACK. */
 run.retired_drops++;return 0;
}
static int control_finish(uint64_t base,ns_rpc*c){
 int ready=control_tail(base,c);if(ready<=0)return ready;
 uint32_t state=csnd_rpc_finish(base,c,1);
 if(state==NT_READY)return 1;
 if(state==NT_UNCERTAIN&&c->reason==NT_REASON_DIRTY){
  uint32_t stat[4]={0};int rc=FN(int(*)(uint32_t,uint32_t*),0x17158b0)(c->endpoint,stat);
  if(!rc&&(stat[0]||stat[1]||stat[3])){c->reason=0;ST(c->state,NT_REPLIED);return 0;}
 }
 return -hold(0x723);
}
static int cp_reply(uint64_t base,uint32_t op){
 int ready=rpc_wait(base,&run.control);if(ready<=0)return ready;
 const uint8_t*p=run.control.reply;
 if(r16(p+2)||r16(p+4)!=24||r32(p+8)!=run.control.endpoint||r32(p+12)!=op)return -hold(0x220);
 uint32_t result=r32(p+16);ST(run.diag[D_LAST_CP_PHASE],result);
 if(result>CP_OFF)return -hold(0x221);
 if(result!=CP_BUSY&&result!=CP_INVALID&&result!=CP_NOTBOUND&&result!=CP_STALE){
  struct bank*b=&run.bank[run.slot];
  uint32_t expected_gen=op==CP_PREPARE?run.target.generation:b->cp_generation;
  uint32_t expected_rev=op==CP_PREPARE?run.revision:b->cp_revision;
  if(op!=CP_BIND&&op!=CP_QUERY&&(r32(p+20)!=expected_gen||r32(p+24)!=expected_rev))return -hold(0x223);
  if(op==CP_BIND){
   uint64_t physical=run.unit[run.slot*3].physical;
   if(r64(p+28)!=physical)return -hold(0x224);
  }
 }
 if(result!=CP_INVALID&&result!=CP_NOTBOUND&&result!=CP_STALE&&
    (op==CP_PREPARE||op==CP_COMMIT||op==CP_POLICY)){
  struct bank*b=&run.bank[run.slot];
  if(result!=CP_BUSY){b->phase=result;b->cp_generation=r32(p+20);b->cp_revision=r32(p+24);}
 }
 int finished=control_finish(base,&run.control);if(finished<=0)return finished;
 return (int)result+1;
}
static int extent_valid(const struct unit*u){
 uint64_t end=u->physical+u->capacity;
 return u->handle&&u->handle!=0xffffffffu&&((u->handle>>15)&1)==u->side&&
  u->capacity==51200u&&!(u->physical&63u)&&end>=u->physical&&
  (u->side?(u->physical>=0x800000000ull&&end<=0x900000000ull):
   (u->physical>=0x400000000ull&&end<=0x600000000ull));
}
static int sort_spans(void){
 for(uint32_t i=0;i<6;i++)for(uint32_t j=i+1;j<6;j++){
   if(run.unit[j].physical<run.unit[i].physical){struct unit t=run.unit[i];run.unit[i]=run.unit[j];run.unit[j]=t;}
 }
 for(uint32_t i=0;i<6;i++)for(uint32_t j=i+1;j<6;j++)
   if(run.unit[j].handle==run.unit[i].handle||run.unit[j].physical==run.unit[i].physical)return 1;
 for(uint32_t i=1;i<6;i++)if(run.unit[i].physical!=run.unit[0].physical+(uint64_t)i*51200u)return 1;
 return 0;
}
/* One episode only; old numeric handles never grant RELEASE authority. */
static int reclaim_eligible(void){
 if(run.reclaim_attempt||run.bind_collect||LD(run.bind_diag[3])!=15||
    LD(run.bind_diag[5])!=63||LD(run.bind_diag[6])||LD(run.bind_diag[49])!=15||
    run.control.state!=NT_READY||run.allocation.state!=NT_EMPTY||
    run.stop_pending||run.resume_state||run.pcm||run.encoded)return 0;
 if(LD(run.bind_diag[0])||LD(run.bind_diag[1])||LD(run.bind_diag[2])!=1||
    LD(run.bind_diag[46])||LD(run.bind_diag[47])||LD(run.bind_diag[48])!=1)return 0;
 for(uint32_t i=0;i<6;i++){
  uint32_t at=16+5*i;
  if(LD(run.bind_diag[10+i])!=run.unit[i].handle||
     LD(run.bind_diag[at])!=run.unit[i].handle)return 0;
  uint32_t verdict=LD(run.bind_diag[at+1]);
  if(verdict==4){
   if(LD(run.bind_diag[at+2])||LD(run.bind_diag[at+3])||LD(run.bind_diag[at+4]))return 0;
  }else if(verdict==6){
   /* Authenticated native extent has the same number but another capacity.
    * Abandon only our obsolete numeric reference. Never release or access it.
    * Fresh six CLAIM ACKs + original BIND remain the sole new authority. */
   uint32_t capacity=LD(run.bind_diag[at+4]);
   if(!capacity||capacity==51200u)return 0;
  }else return 0;
 }
 return 1;
}
static int reclaim_fail(uint32_t why){return hold(why);}
static int reclaim_tick(uint64_t base){
 ns_rpc*c=&run.allocation;struct unit*u=&run.provisional[run.reclaim_index];
 ST(run.fault[F_RECOVERY_TICK],run.tick);
 if(c->state==NT_EMPTY){
  if(csnd_dmm_start(base,c,1,0x20,0x70817,run.tick+2500)!=NT_PENDING)return reclaim_fail(0x6b0+c->reason);
  return 0;
 }
 uint32_t state=csnd_rpc_poll(base,c,run.tick);ST(run.diag[D_RPC_REASON],c->reason);
 if(state==NT_UNCERTAIN){fault_capture(0x100+c->reason,c);return reclaim_fail(0x100+c->reason);}
 if(state!=NT_REPLIED)return 0;
 if(r16(c->reply+2)){
  if(csnd_rpc_finish(base,c,0)!=NT_EMPTY)return reclaim_fail(0x6c0);
  return reclaim_fail(0x6c1);
 }
 u->handle=r32(c->reply+12);u->physical=r64(c->reply+24);u->capacity=r32(c->reply+32);u->side=1;
 if(!extent_valid(u))return reclaim_fail(0x6c2);
 for(uint32_t i=0;i<run.reclaim_index;i++)if(run.provisional[i].handle==u->handle)return reclaim_fail(0x6c3);
 u->owned=1;
 if(csnd_rpc_finish(base,c,0)!=NT_EMPTY)return reclaim_fail(0x6c4);
 ST(run.diag[D_CLAIM],LD(run.diag[D_CLAIM])+1);
 if(++run.reclaim_index!=6)return 0;
 for(uint32_t i=0;i<6;i++)for(uint32_t j=i+1;j<6;j++)if(run.provisional[j].physical<run.provisional[i].physical){struct unit t=run.provisional[i];run.provisional[i]=run.provisional[j];run.provisional[j]=t;}
 for(uint32_t i=1;i<6;i++)if(run.provisional[i].physical!=run.provisional[0].physical+(uint64_t)i*51200)return reclaim_fail(0x6c5);
 /* Only now adopt new native ACK identities. No old object is released. */
 copy(run.unit,run.provisional,sizeof(run.unit));
 for(uint32_t i=0;i<2;i++){
  run.bank[i].valid=run.bank[i].active=0;run.bank[i].phase=CP_ACTIVE;
  ST(run.diag[D_READY0+i],0);
 }
 ST(run.diag[D_FOCUS],0);ST(run.driver_valid,0);run.driver_stage=0;
 run.recovery_rebind_mask=3;run.recovery_state=0;run.reclaim_stage=3;
 run.slot=0;run.last_scan=~csnd_event_revision();phase(R_BIND);return 0;
}
static void resource_ready(uint32_t slot,uint32_t value){
 if(run.reclaim_attempt&&value)value=0;
 ST(run.diag[D_READY0+slot],value);if(slot)ST(run.diag[D_FOCUS],value);
}
static int reclaim_publish(uint64_t base){
 if(run.reclaim_stage!=3||run.state!=R_IDLE||run.stop_pending||run.resume_state||
    run.pcm||run.encoded||run.control.state!=NT_READY||run.allocation.state!=NT_EMPTY)return 0;
 uint32_t mask=0,expected_revision=csnd_event_revision();
 for(uint32_t i=0;i<2;i++){
  struct meta m;if(meta(base,i,&m))return 0;
  struct bank*b=&run.bank[i];
  if(m.enabled&&m.custom&&wanted(base,i,m.generation)){
   if(!b->valid||!b->active||b->phase!=CP_ACTIVE||!matches(&m,b))return 0;
   mask|=1u<<i;
  }else if(b->active||b->phase!=CP_OFF)return 0;
 }
 if(!csnd_event_resource_epoch(expected_revision))return 0;
 /* Single success edge: no queued job is removed or replayed here. */
 run.reclaim_attempt=run.reclaim_stage=0;run.reclaim_index=0;
 ST(run.diag[D_ERROR],0);ST(run.diag[D_UNCERTAIN],0);
 for(uint32_t i=0;i<2;i++)resource_ready(i,(mask>>i)&1);
 run.last_scan=~csnd_event_revision();return 1;
}
static void claimed_failure(uint32_t error){ST(run.diag[D_ERROR],error);run.rollback_index=6;phase(R_ROLLBACK);}
static int claim_tick(uint64_t base){
 ns_rpc*c=&run.allocation;struct unit*u=&run.unit[run.index];
 if(c->state==NT_EMPTY){
  if(csnd_dmm_start(base,c,1,0x20,0x70817,run.tick+2500)!=NT_PENDING)return hold(0x300u+c->reason);
  return 0;
 }
 int ready=rpc_wait(base,c);if(ready<=0)return ready;
 if(r16(c->reply+2)){
  if(csnd_rpc_finish(base,c,0)!=NT_EMPTY)return hold(0x310);
  claimed_failure(0x311);return 0;
 }
 u->handle=r32(c->reply+12);u->physical=r64(c->reply+24);u->capacity=r32(c->reply+32);u->side=1;
 if(!extent_valid(u))return hold(0x312); /* Never release an arbitrary malformed positive handle. */
 for(uint32_t i=0;i<run.index;i++)if(run.unit[i].handle==u->handle)return hold(0x315);
 u->owned=1;ST(run.diag[D_CLAIM],run.index+1);
 if(csnd_rpc_finish(base,c,0)!=NT_EMPTY)return hold(0x313);
 if(++run.index==6){
  if(sort_spans()){claimed_failure(0x314);return 0;}
  run.slot=0;phase(R_BIND);
 }
 return 0;
}
static int rollback_tick(uint64_t base){
 ns_rpc*c=&run.allocation;
 while(run.rollback_index&&!run.unit[run.rollback_index-1].owned)run.rollback_index--;
 if(!run.rollback_index){phase(R_HOLD);return (int)LD(run.diag[D_ERROR]);}
 struct unit*u=&run.unit[run.rollback_index-1];
 if(c->state==NT_EMPTY){
  if(csnd_dmm_start(base,c,u->side,0x23,u->handle,run.tick+2500)!=NT_PENDING)return hold(0x320u+c->reason);
  return 0;
 }
 int ready=rpc_wait(base,c);if(ready<=0)return ready;
 if(r16(c->reply+2))return hold(0x330);
 u->owned=0;run.rollback_index--;run.diag[D_ROLLBACK]++;
 if(csnd_rpc_finish(base,c,0)!=NT_EMPTY)return hold(0x331);
 return 0;
}
/* Posthoc only: never re-BIND, release or claim on this diagnostic path. */
static void bind_diag_begin(uint32_t cp_phase){
 ST(run.bind_version,run.bind_version+1);
 for(uint32_t i=0;i<54;i++)ST(run.bind_diag[i],0xffffffffu);
 ST(run.bind_diag[3],0);ST(run.bind_diag[4],cp_phase);
 ST(run.bind_diag[5],0);ST(run.bind_diag[6],0);
 ST(run.bind_diag[8],0x400);ST(run.bind_diag[9],run.tick);
 for(uint32_t i=0;i<6;i++)ST(run.bind_diag[10+i],run.unit[i].handle);
 ST(run.bind_diag[49],0);ST(run.bind_diag[50],run.tick);
 ST(run.bind_diag[51],0);ST(run.bind_diag[52],0);ST(run.bind_diag[53],0);
 run.bind_tick=run.tick;run.bind_stage=run.bind_tries=0;
 run.bind_collect=cp_phase==CP_INVALID;
 if(!run.bind_collect){ST(run.bind_diag[3],24);ST(run.bind_diag[52],0x200+cp_phase);}
 ST(run.driver_valid,0);
 ST(run.bind_version,run.bind_version+1);
}
static int bind_diag_end(uint32_t error){
 ST(run.bind_version,run.bind_version+1);
 ST(run.bind_diag[52],error);ST(run.bind_diag[51],run.tick);
 ST(run.bind_diag[3],LD(run.bind_diag[3])|8u|(error?16u:0u));
 run.bind_collect=0;run.bind_tick=run.tick;
 ST(run.bind_version,run.bind_version+1);return 0x400;
}
static int bind_diag_tick(uint64_t base){
 if(!run.bind_collect)return 0x400;
 ns_rpc*c=&run.control;
 if(c->state==NT_EMPTY||c->state==NT_READY){
  uint32_t a[4]={3,0,0,0};
  if(run.bind_stage>0&&run.bind_stage<7){a[0]=4;a[1]=run.bind_stage-1;a[2]=LD(run.bind_diag[10+a[1]]);}
  uint32_t s=csnd_private_start(base,c,CP_QUERY,run.slot,a,run.tick+2500);
  if(s==NT_PENDING){c->expected_source=CP_REPLY_SOURCE;run.query_selector=0x80000000u|(a[0]&255u)|((run.slot&255u)<<8)|((a[1]&255u)<<16);}
  if(s!=NT_PENDING)return bind_diag_end(0x100+c->reason);
  return 0x400;
 }
 uint32_t s=control_poll(base,c);
 if(s==NT_UNCERTAIN)return bind_diag_end(0x100+c->reason);
 if(s!=NT_REPLIED)return 0x400;
 const uint8_t*p=c->reply;uint32_t result=r32(p+16),data[5];
 for(uint32_t i=0;i<5;i++)data[i]=r32(p+20+4*i);
 if(r16(p+2)||r16(p+4)!=24||r32(p+8)!=c->endpoint||r32(p+12)!=CP_QUERY||result>CP_OFF)return bind_diag_end(0x300);
 int finished=control_finish(base,c);if(finished<0)return bind_diag_end(0x100+c->reason);if(!finished)return 0x400;
 ST(run.bind_diag[4],result);
 if(result==CP_BUSY){if(++run.bind_tries<3)return 0x400;return bind_diag_end(0x301);}
 if(result!=CP_OK)return bind_diag_end(0x200+result);
 run.bind_tries=0;ST(run.bind_version,run.bind_version+1);
 if(run.bind_stage==0||run.bind_stage==7){
  if(data[0]!=0x10001){ST(run.bind_version,run.bind_version+1);return bind_diag_end(0x300);}
  uint32_t at=run.bind_stage?46:0;
  ST(run.bind_diag[at],data[1]);ST(run.bind_diag[at+1],data[2]|data[3]<<16);ST(run.bind_diag[at+2],data[4]);
  ST(run.bind_diag[3],LD(run.bind_diag[3])|(run.bind_stage?2u:1u));
  if(run.bind_stage){uint32_t flags=1;
   for(uint32_t i=0;i<3;i++)if(LD(run.bind_diag[i])==LD(run.bind_diag[46+i]))flags|=2u<<i;
   ST(run.bind_diag[49],flags);
  }
 }else{
  uint32_t i=run.bind_stage-1;
  if(data[0]!=LD(run.bind_diag[10+i])||data[1]>6||(!data[1]&&data[4]!=51200)){ST(run.bind_version,run.bind_version+1);return bind_diag_end(0x300);}
  for(uint32_t j=0;j<5;j++)ST(run.bind_diag[16+5*i+j],data[j]);
  ST(run.bind_diag[5],LD(run.bind_diag[5])|(1u<<i));
  if(!data[1])ST(run.bind_diag[6],LD(run.bind_diag[6])|(1u<<i));
  else if(LD(run.bind_diag[7])==0xffffffffu)ST(run.bind_diag[7],i);
  if(i==5)ST(run.bind_diag[3],LD(run.bind_diag[3])|4u);
 }
 ST(run.bind_version,run.bind_version+1);run.bind_tick=run.tick;
 if(++run.bind_stage==8)return bind_diag_end(0);
 return 0x400;
}
static int bind_tick(uint64_t base){
 ns_rpc*c=&run.control;
 if(c->state==NT_EMPTY||c->state==NT_READY){
  uint32_t at=3*run.slot;uint32_t a[4]={run.unit[at].handle,run.unit[at+1].handle,run.unit[at+2].handle,0};
  return cp_start(base,CP_BIND,a);
 }
 int r=cp_reply(base,CP_BIND);if(r<=0)return r;
 if(r-1==CP_BUSY)return 0;
 if(r-1!=CP_OK){ST(run.bind_diag[8],0);hold(0x400);bind_diag_begin(r-1);return 0x400;}
 run.diag[D_BOUND]++;
 /* Post-timeout BIND may leave a live CP slot ACTIVE. Preserve a conservative
  * AP ACTIVE phase until PREPARE so original BUSY handling can emit Stop. */
 if(run.recovery_rebind_mask&(1u<<run.slot)){
  run.bank[run.slot].cp_generation=r32(run.control.reply+20);
  run.bank[run.slot].cp_revision=r32(run.control.reply+24);
 }
 run.bank[run.slot].phase=(run.recovery_rebind_mask&(1u<<run.slot))?CP_ACTIVE:CP_OFF;
 ST(run.diag[D_SESSION],run.control.endpoint);
 if(++run.slot==2){run.slot=0;phase(R_IDLE);}
 return 0;
}
static void unready(uint32_t slot){run.bank[slot].active=0;ST(run.diag[D_READY0+slot],0);if(slot)ST(run.diag[D_FOCUS],0);}
static int idle_tick(uint64_t base,uint32_t revision){
 if(run.last_scan==revision&&run.tick%50)return 0;
 for(uint32_t n=0;n<2;n++){
  uint32_t slot=(run.slot+n)&1;struct meta m;
  if(meta(base,slot,&m))continue;
  int w=m.enabled&&m.custom&&wanted(base,slot,m.generation);
  struct bank*b=&run.bank[slot];int same=b->valid&&matches(&m,b);
  if(b->phase==CP_ACTIVE&&!b->active&&(!(run.recovery_rebind_mask&(1u<<slot))||!w)){
   run.slot=slot;run.revision=revision;run.desired=0;phase(R_POLICY);return 0;
  }
  if(!same&&w){
   run.slot=slot;run.target=m;run.revision=revision;run.reuse=0;run.desired=1;
   unready(slot);phase(R_PREPARE);return 0;
  }
  if(same&&w&&!b->active){
   run.slot=slot;run.target=m;run.revision=revision;run.reuse=1;run.desired=1;
   phase(b->phase==CP_PREPARED?R_COMMIT:R_POLICY);return 0;
  }
  if((!w||!same)&&b->active){
   run.slot=slot;run.revision=revision;run.desired=0;unready(slot);phase(R_POLICY);return 0;
  }
 }
 run.last_scan=revision;run.slot^=1;
 if(run.tick%250==0)phase(R_QUERY);
 return 0;
}
static int resume_bind(void){
  if(run.stop_pending||run.resume_state||run.pcm||run.encoded||
     run.control.state!=NT_READY||run.allocation.state!=NT_EMPTY)return hold(0x491);
  for(uint32_t i=0;i<6;i++)if(!run.unit[i].owned||!extent_valid(&run.unit[i]))return hold(0x492);
  for(uint32_t i=0;i<2;i++){run.bank[i].valid=0;unready(i);}
  ST(run.driver_valid,0);run.driver_stage=0;
  ST(run.diag[D_FOCUS],0);run.slot=0;run.last_scan=~csnd_event_revision();
  phase(R_BIND);return 0;
 }

/* QUERY-only late-ACK reconciliation. Original fault identity is immutable.
 * This worker never resends an uncertain request, releases an uncertain queue,
 * resets a token or changes a native owner. A completed BUSY permits only a
 * fresh read-only stats query, with its separately retained new token. */
static int recovery_fail(uint32_t why){
 ST(run.fault[F_RECOVERY_ERROR],why);ST(run.fault[F_RECOVERY_TICK],run.tick);
 return (int)LD(run.diag[D_ERROR]);
}
static void recovery_shadow(const ns_rpc*c){
 run.recovery_identity[0]=c->operation;run.recovery_identity[1]=c->command;
 run.recovery_identity[2]=c->token;run.recovery_identity[3]=c->endpoint;
 run.recovery_identity[4]=c->session;run.recovery_identity[5]=c->destination;
 run.recovery_identity[6]=c->expected_source;run.recovery_identity[7]=c->deadline;
}
static int recovery_stats(uint64_t base){
 ns_rpc*c=&run.control;uint32_t a[4]={1,0,0,0};
 if(c->state!=NT_READY||run.recovery_rounds>=8)return recovery_fail(0x607);
 run.driver_stage=0;run.recovery_rounds++;
 if(cp_start(base,CP_QUERY,a)||c->state!=NT_PENDING)return recovery_fail(0x608);
 run.recovery_state=2;recovery_shadow(c);return (int)LD(run.diag[D_ERROR]);
}
/* Logical retirement is NOT native cancellation/finish. The only authorized
 * outstanding operation is a read-only QUERY; its exact token remains a
 * permanent tombstone in the retained endpoint's non-wrapping lifetime. */
static int retire_query(uint64_t base){
 ns_rpc*c=&run.control;
 uint32_t selector=run.query_selector,a0=selector&255u,a1=(selector>>16)&255u;
 if(c->state!=NT_UNCERTAIN||c->reason!=NT_REASON_TIMEOUT||!c->attempted||
    c->operation!=CP_QUERY||c->command!=0x807e||c->destination!=0x9061003c||
    !c->endpoint||c->session!=c->endpoint||c->expected_source!=CP_REPLY_SOURCE||
    !c->token||c->token>0xffff||c->token!=c->next_token||
    run.control.state!=NT_UNCERTAIN||run.allocation.state!=NT_EMPTY||
    run.stop_pending||run.resume_state||run.pcm||run.encoded||
    !(selector&0x80000000u)||(selector&0x7f000000u)||((selector>>8)&255u)>1||
    !((a0==1&&!a1)||(a0==2&&(a1==4||a1==17))||(a0==5&&a1==4)))return recovery_fail(0x701);
 if(run.retired_count>=64||run.recovery_rounds>=8)return recovery_fail(0x702);
 if(run.retired_count&&run.retired_endpoint!=c->endpoint)return recovery_fail(0x703);
 for(uint32_t i=0;i<run.retired_count;i++)if(run.retired_query_token[i]==c->token)return recovery_fail(0x704);
 ST(run.retired_endpoint,c->endpoint);run.retired_query_token[run.retired_count]=(uint16_t)c->token;
 ST(run.retired_count,run.retired_count+1);
 /* Do not release dynamic ID, drain a queue, clear an owner or reset tokens.
  * Native send semantics remain; only a distinct new read may now be sent. */
 c->attempted=0;c->reason=0;ST(c->state,NT_READY);
 return recovery_stats(base);
}
static int recover_query(uint64_t base){
 ns_rpc*c=&run.control;uint32_t*f=run.current_fault;
 if(LD(f[F_MAGIC])!=0x544c4146u||f[F_ERROR]!=0x106u||
    (f[F_PRESTATE]!=R_QUERY&&!(run.readonly_series&&run.recovery_state==2&&f[F_PRESTATE]==R_HOLD))||
    f[F_CONTEXT]!=2u||f[F_OP]!=CP_QUERY||f[F_CMD]!=0x807eu||!f[F_TOKEN]||
    f[F_REPLY_STATE]!=NT_UNCERTAIN||LD(run.fault[F_RECOVERY_ERROR]))return (int)LD(run.diag[D_ERROR]);
 if(run.stop_pending||run.resume_state||run.pcm||run.encoded||run.allocation.state!=NT_EMPTY)
  return recovery_fail(0x601);
 if(run.recovery_state==3){
  if(c->state!=NT_READY||c->endpoint!=f[F_ENDPOINT]||c->session!=f[F_SESSION])return recovery_fail(0x602);
  if((int32_t)(run.tick-run.recovery_next_tick)<0)return (int)LD(run.diag[D_ERROR]);
  return recovery_stats(base);
 }
 if(!run.recovery_state){
  if(c->operation!=f[F_OP]||c->command!=f[F_CMD]||c->token!=f[F_TOKEN]||
     c->endpoint!=f[F_ENDPOINT]||c->session!=f[F_SESSION]||c->destination!=f[F_DEST]||
     c->expected_source!=f[F_SOURCE]||c->deadline!=f[F_DEADLINE]||
     run.driver_stage!=run.fault_query_stage)return recovery_fail(0x603);
  recovery_shadow(c);run.recovery_state=1;run.readonly_series=1;
 }
 uint32_t*q=run.recovery_identity;
 if(!c->attempted||c->operation!=q[0]||c->command!=q[1]||c->token!=q[2]||
    c->endpoint!=q[3]||c->session!=q[4]||c->destination!=q[5]||
    c->expected_source!=q[6]||c->deadline!=q[7]||!c->endpoint||c->session!=c->endpoint)
  return recovery_fail(0x604);
 if(c->state!=NT_PENDING&&c->state!=NT_UNCERTAIN&&c->state!=NT_REPLIED)return recovery_fail(0x605);
 if(c->state==NT_UNCERTAIN&&c->reason!=NT_REASON_TIMEOUT)return recovery_fail(0x606);
 ST(run.fault[F_ATTEMPTS],LD(run.fault[F_ATTEMPTS])+1);ST(run.fault[F_RECOVERY_TICK],run.tick);
 uint32_t state=control_poll(base,c);ST(run.diag[D_RPC_REASON],c->reason);
 if(state==NT_PENDING)return (int)LD(run.diag[D_ERROR]);
 if(state==NT_UNCERTAIN){
  if(c->reason!=NT_REASON_TIMEOUT)return recovery_fail(0x610u+c->reason);
  if(run.recovery_state==2&&f[F_TOKEN]!=c->token)fault_capture(0x106,c);
  if((int32_t)(run.tick-c->deadline)>=250)return retire_query(base);
  return (int)LD(run.diag[D_ERROR]);
 }
 if(state!=NT_REPLIED)return recovery_fail(0x609);
 /* Drain only: original cp_reply verifies payload/status/session/op and
  * original clean-queue finish(retain1). Old advisory schema/sequence is
  * discarded, never accepted as a current driver snapshot or owner epoch. */
 int r=cp_reply(base,CP_QUERY);if(!r)return (int)LD(run.diag[D_ERROR]);if(r<0)return recovery_fail(0x60a);
 ST(run.fault[F_ACKS],LD(run.fault[F_ACKS])+1);uint32_t phase=(uint32_t)(r-1);
 if(phase!=CP_OK&&phase!=CP_BUSY&&phase!=CP_STALE)return recovery_fail(0x620u+phase);
 if(run.recovery_state==1)return recovery_stats(base);
 if(phase==CP_BUSY){
  run.recovery_state=3;run.recovery_next_tick=run.tick+50;return (int)LD(run.diag[D_ERROR]);
 }
 /* Only a completed new stats QUERY can initiate post-timeout revalidation.
  * Preserve conservative ACTIVE knowledge for Stop on CP PREPARE BUSY. */
 run.recovery_rebind_mask=3u;
 int rc=resume_bind();if(rc||run.state!=R_BIND)return recovery_fail(0x60b);
 run.recovery_state=4;run.readonly_series=0;ST(run.diag[D_ERROR],0);ST(run.diag[D_UNCERTAIN],0);
 return 0;
}
void csnd_resource_fault_snapshot(uint32_t out[26]){
 if(!out)return;
 if(LD(run.fault[F_MAGIC])!=0x544c4146u){for(uint32_t i=0;i<26;i++)out[i]=0;out[F_MAGIC]=0x544c4146u;out[F_SCHEMA]=1;return;}
 for(uint32_t i=0;i<26;i++)out[i]=LD(run.fault[i]);
}
uint32_t csnd_resource_current_fault_snapshot(uint32_t out[20]){
 if(!out)return 1;
 uint32_t version=LD(run.query_snapshot_version);
 for(uint32_t i=0;i<20;i++)out[i]=LD(run.current_fault[i]);
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if((version&1)||version!=LD(run.query_snapshot_version)||out[F_MAGIC]!=0x544c4146u){
  for(uint32_t i=0;i<20;i++)out[i]=0;
  out[F_MAGIC]=0x544c4146u;out[F_SCHEMA]=1;return 1;
 }
 return 0;
}
static void query_snapshot(uint32_t out[64]){
 out[0]=0x32595251;out[1]=1;out[3]=LD(run.tick);
 uint32_t version=LD(run.query_snapshot_version);ns_rpc*c=&run.control;
 if(version&1)goto busy;
 if(csnd_resource_current_fault_snapshot(out+4))goto busy;
 uint32_t*live=out+24;
 uint32_t valid=c->endpoint&&c->session==c->endpoint&&c->token&&c->token<=0xffff&&
  c->operation>=1&&c->operation<=6&&c->command==0x807e;
 if(valid){
 live[F_MAGIC]=0x544c4146u;live[F_SCHEMA]=1;live[F_ERROR]=LD(run.diag[D_ERROR]);
 live[F_PRESTATE]=LD(run.state);live[F_CONTEXT]=2;live[F_OP]=LD(c->operation);
 live[F_CMD]=LD(c->command);live[F_TOKEN]=LD(c->token);live[F_ENDPOINT]=LD(c->endpoint);
 live[F_SESSION]=LD(c->session);live[F_DEST]=LD(c->destination);live[F_SOURCE]=LD(c->expected_source);
 live[F_ACTUAL_SOURCE]=LD(c->source);live[F_DEADLINE]=LD(c->deadline);live[F_TICK]=LD(run.tick);
 live[F_RECEIVE]=LD(c->receive_rc);live[F_BYTES]=LD(c->actual_bytes);live[F_LATE]=LD(c->late);
 live[F_REPLY_STATE]=LD(c->state);live[F_POLLS]=LD(c->polls);
 }
 uint32_t n=LD(run.retired_count),sample=n<4?n:4;
 out[44]=n;out[45]=(1u<<sample)-1u;
 for(uint32_t i=0;i<sample;i++)out[46+i/2]|=(uint32_t)run.retired_query_token[i]<<(16*(i&1));
 out[48]=LD(run.recovery_rounds);out[49]=LD(run.retired_drops);out[50]=CP_REPLY_SOURCE;
 out[51]=run.current_fault[F_CONTEXT]==2&&run.current_fault[F_OP]==CP_QUERY&&c->operation==CP_QUERY?LD(run.query_selector):0;
 out[52]=LD(c->reason);out[53]=LD(c->next_token);
 out[54]=LD(run.reclaim_stage)?0x100+LD(run.reclaim_stage):LD(run.recovery_state);
 out[55]=4u|(out[4]==0x544c4146u?1u:0u)|(valid?2u:0u)|(n==64?8u:0u);
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if(version==LD(run.query_snapshot_version)&&out[4]==0x544c4146u)return;
busy:
 for(uint32_t i=4;i<58;i++)out[i]=0;
 out[50]=CP_REPLY_SOURCE;out[56]=0x302;
}

/* Driver pages are advisory only. No error here destroys owners or waits
 * on an original photo/mode/power caller. Only the original stats-page STALE
 * selects retained-session recovery; page sequence STALE merely drops a read.
 */
static void driver_next(void){
 run.driver_stage=1;
 if(++run.driver_slot==2){run.driver_slot=0;run.driver_stage=8;}
}
static int query_tick(uint64_t base){
 if(run.control.state==NT_READY){
  if(run.driver_stage&&run.driver_epoch!=csnd_event_revision()){
   run.driver_stage=0;phase(R_IDLE);return 0;
  }
  uint32_t a[4]={1,0,0,0};
  if(run.driver_stage>=8){a[0]=5;a[1]=4;a[2]=run.driver_stage-8;a[3]=run.driver_stage==8?0:run.focus_expected;}
  else if(run.driver_stage){a[0]=2;a[1]=run.driver_slot?4:17;a[2]=run.driver_stage-1;a[3]=run.driver_stage==1?0:run.driver_expected;}
  return cp_start(base,CP_QUERY,a);
 }
 int r=cp_reply(base,CP_QUERY);if(r<=0)return r;
 if(run.driver_stage&&run.driver_epoch!=csnd_event_revision()){
  run.driver_stage=0;phase(R_IDLE);return 0; /* matched ACK consumed first */
 }
 if(!run.driver_stage){
  if(r-1==CP_BUSY){phase(R_IDLE);return 0;}
  if(r-1==CP_STALE)return resume_bind();
  if(r-1!=CP_OK)return hold(0x490);
  run.cp_stats[0]=1;run.cp_stats[1]=run.tick;
  for(uint32_t i=0;i<5;i++)ST(run.cp_stats[2+i],r32(run.control.reply+20+4*i));
  ST(run.cp_stats[7],run.control.source);
  run.driver_stage=1;run.driver_slot=0;run.driver_epoch=csnd_event_revision();return 0;
 }
 if(run.driver_stage>=8){
  if(r-1!=CP_OK){ST(run.driver_error,0x510u+(uint32_t)(r-1));run.driver_stage=0;phase(R_IDLE);return 0;}
  const uint8_t*p=run.control.reply;uint32_t seq=r32(p+20);
  if(run.driver_stage==8){
   if(seq!=r32(p+24)||(seq&1u)){ST(run.driver_error,0x519);run.driver_stage=0;phase(R_IDLE);return 0;}
   run.focus_expected=seq;
  }else if(seq!=run.focus_expected){ST(run.driver_error,0x51a);run.driver_stage=0;phase(R_IDLE);return 0;}
  for(uint32_t i=0;i<4;i++)run.focus_stage[4*(run.driver_stage-8)+i]=r32(p+24+4*i);
  if(run.driver_stage++==8)return 0;
  ST(run.driver_version,run.driver_version+1);__atomic_thread_fence(__ATOMIC_RELEASE);
  for(uint32_t i=0;i<8;i++)ST(run.focus_diag[i],run.focus_stage[i]);
  ST(run.driver_version,run.driver_version+1);run.driver_stage=0;phase(R_IDLE);return 0;
 }
 if(r-1!=CP_OK){ST(run.driver_error,(uint32_t)(r-1));driver_next();return 0;}
 const uint8_t*p=run.control.reply;uint32_t seq=r32(p+20),kind=run.driver_slot?4:17;
 if(run.driver_stage==1){
  if(r32(p+24)!=0x10003||r32(p+28)!=kind||r32(p+32)!=seq){ST(run.driver_error,0x501);driver_next();return 0;}
  ST(run.driver_missed[run.driver_slot],r32(p+36));
  if(!seq){ST(run.driver_valid,run.driver_valid&~(1u<<run.driver_slot));driver_next();return 0;}
  run.driver_expected=seq;run.driver_stage=2;return 0;
 }
 if(seq!=run.driver_expected){ST(run.driver_error,0x502);driver_next();return 0;}
 for(uint32_t i=0;i<4;i++)run.driver_staging[4*(run.driver_stage-2)+i]=r32(p+24+4*i);
 if(++run.driver_stage<=7)return 0;
 if(run.driver_staging[0]!=seq||run.driver_staging[2]!=kind){ST(run.driver_error,0x503);driver_next();return 0;}
 ST(run.driver_version,run.driver_version+1);__atomic_thread_fence(__ATOMIC_RELEASE);
 for(uint32_t i=0;i<24;i++)ST(run.driver_record[24*run.driver_slot+i],run.driver_staging[i]);
 ST(run.driver_sequence[run.driver_slot],seq);ST(run.driver_tick,run.tick);
 ST(run.driver_valid,run.driver_valid|(1u<<run.driver_slot));
 ST(run.driver_version,run.driver_version+1);driver_next();return 0;
}
/* The original async counter includes the derived Stop request. Zero is a
 * conservative whole-Sysnd drain barrier, not a per-request acknowledgement.
 * No new AP Start/CP publish is allowed before this and native busy==0.
 * Never free or reuse a bank on enqueue return or counter zero alone. */
static int stop_barrier(uint64_t base,uint32_t mask){
 for(uint32_t i=0;i<2;i++)if(((mask&~run.stop_mask)&(1u<<i))&&run.bank[i].phase==CP_ACTIVE){
  int rc=csnd_stop_async_request(base,i?4:17);ST(run.diag[D_LAST_NATIVE],(uint32_t)rc);
  if(rc!=1)return -hold(0x4a0);
  run.stop_mask|=1u<<i;run.stop_pending=1;
  run.stop_deadline=run.tick+5000;run.diag[D_RESERVED0]++;
 }
 if(run.stop_pending==1){
  uint32_t pending=~0u;
  FN(void(*)(void*,uint32_t*),0x359b45c)(0,&pending);
  ST(run.diag[D_RESERVED1],pending);
  if(pending){
   if((int32_t)(run.tick-run.stop_deadline)>=0)return -hold(0x4a1);
   return 0;
  }
  run.stop_pending=2;
 }
 return 1;
}
static int prepare_tick(uint64_t base){
 if(run.control.state==NT_READY){if(stop_barrier(base,0)<=0)return 0;uint32_t a[4]={run.target.generation,run.revision,0,0};return cp_start(base,CP_PREPARE,a);}
 int r=cp_reply(base,CP_PREPARE);if(r<=0)return r;
 if(r-1==CP_BUSY){if(run.bank[run.slot].phase==CP_ACTIVE)(void)stop_barrier(base,1u<<run.slot);return 0;}
 if(r-1!=CP_PREPARED)return hold(0x410);
 run.stop_pending=run.stop_mask=0;
 struct bank*b=&run.bank[run.slot];b->valid=0;b->phase=CP_PREPARED;
 b->cp_generation=run.target.generation;b->cp_revision=run.revision;
 run.recovery_rebind_mask&=~(1u<<run.slot);run.diag[D_PREPARES]++;run.prepared=1;phase(R_CONVERT);return 0;
}
static int convert_tick(uint64_t base){
 struct meta m;uint32_t bytes=0;ss_format format;csnd_convert_info info;
 if(meta(base,run.slot,&m))return 0;
 if(m.generation!=run.target.generation||m.volume_step!=run.target.volume_step||!equal(m.key,run.target.key)||
    !wanted(base,run.slot,m.generation)||csnd_event_revision()!=run.revision){phase(R_IDLE);return 0;}
 run.pcm=FN(alloc_fn,0x17152c0)(CSND_AP_MAX_WAV_BYTES);
 if(!run.pcm){ST(run.diag[D_ERROR],0x420);phase(R_IDLE);return 0;}
 int rc=FN(copy_fn,0x8f92508)(run.slot,m.generation,run.pcm,CSND_AP_MAX_WAV_BYTES,&format,&bytes);
 if(rc){FN(free_fn,0x1717810)(run.pcm);run.pcm=0;phase(R_IDLE);return rc;}
 run.encoded=FN(alloc_fn,0x17152c0)(153600);
 if(!run.encoded){FN(free_fn,0x1717810)(run.pcm);run.pcm=0;ST(run.diag[D_ERROR],0x430);phase(R_IDLE);return 3;}
 rc=csnd_pcm_f0_volume(run.pcm,bytes,&format,run.encoded,153600,&info,m.volume_step);
 FN(free_fn,0x1717810)(run.pcm);run.pcm=0;
 if(rc){FN(free_fn,0x1717810)(run.encoded);run.encoded=0;ST(run.diag[D_ERROR],0x450u+(uint32_t)(-rc));phase(R_IDLE);return rc;}
 struct bank*b=&run.bank[run.slot];b->volume_step=m.volume_step;b->length=info.encoded_bytes;copy(b->key,m.key,32);
 b->crc=FN(crc_fn,0x8f9902c)(run.encoded,b->length);
 ST(run.diag[D_BYTES],b->length);ST(run.diag[D_GENERATION],m.generation);ST(run.diag[D_REVISION],run.revision);
 run.diag[D_CONVERTS]++;run.transfer_index=0;phase(R_TRANSFER);return 0;
}
static int transfer_tick(uint64_t base){
 ns_rpc*c=&run.control;struct bank*b=&run.bank[run.slot];
 if(c->state==NT_READY){
  uint32_t n=b->length-run.transfer_index;if(n>960)n=960;
  if(!n||!run.encoded)return hold(0x460);
  if(csnd_private_copy(base,c,run.slot,b->cp_generation,b->cp_revision,
      run.transfer_index,run.encoded+run.transfer_index,n,run.tick+2500)!=NT_PENDING)return hold(0x461);
  return 0;
 }
 int r=cp_reply(base,CP_COPY);if(r<=0)return r;
 if(r-1==CP_BUSY)return 0;
 if(r-1!=CP_OK)return hold(0x462);
 uint32_t n=b->length-run.transfer_index;if(n>960)n=960;
 if(r32(c->reply+20)!=b->cp_generation||r32(c->reply+24)!=b->cp_revision||
    r32(c->reply+36)!=run.transfer_index+n)return hold(0x463);
 run.transfer_index+=n;
 run.diag[D_TRANSFERS]++;
 if(run.transfer_index==b->length){
  FN(free_fn,0x1717810)(run.encoded);run.encoded=0;b->valid=1;phase(R_COMMIT);
 }
 return 0;
}
static int commit_tick(uint64_t base){
 struct bank*b=&run.bank[run.slot];struct meta m;
 if(run.control.state==NT_READY){
  if(meta(base,run.slot,&m))return 0;
  if(!m.enabled||!m.custom||!matches(&m,b)||!wanted(base,run.slot,m.generation)||
     csnd_event_revision()!=run.revision){
   phase(R_IDLE);return 0; /* PREPARED contains detached, inactive data. */
  }
  uint32_t a[4]={b->cp_generation,b->cp_revision,b->length,b->crc};return cp_start(base,CP_COMMIT,a);
 }
 int r=cp_reply(base,CP_COMMIT);if(r<=0)return r;
 if(r-1==CP_BUSY)return 0;
 if(r-1!=CP_ACTIVE)return hold(0x470);
 if(meta(base,run.slot,&m)||!m.enabled||!m.custom||!matches(&m,b)||
    !wanted(base,run.slot,m.generation)||csnd_event_revision()!=run.revision){
  unready(run.slot);run.desired=0;phase(R_POLICY);return 0;
 }
 b->active=1;b->phase=CP_ACTIVE;resource_ready(run.slot,1);
 run.diag[D_COMMITS]++;run.last_scan=~run.revision;phase(R_IDLE);return 0;
}
static int policy_tick(uint64_t base){
 struct bank*b=&run.bank[run.slot];
 if(run.control.state==NT_READY){
  if(stop_barrier(base,0)<=0)return 0;
  if(run.desired){
   struct meta m;
   if(meta(base,run.slot,&m)||!m.enabled||!m.custom||!matches(&m,b)||
      !wanted(base,run.slot,m.generation)||csnd_event_revision()!=run.revision){
    unready(run.slot);phase(R_IDLE);return 0;
   }
  }
  uint32_t mask=0;
  if(!run.desired){
   mask=1u<<run.slot;
   for(uint32_t i=0;i<2;i++)if(i!=run.slot&&run.bank[i].phase==CP_ACTIVE){
    struct meta m;
    if(!meta(base,i,&m)&&(!m.enabled||!m.custom||!matches(&m,&run.bank[i])||!wanted(base,i,m.generation))){
     mask|=1u<<i;unready(i);
    }
   }
  }
  run.revoke_mask=mask;
  uint32_t a[4]={b->cp_generation,b->cp_revision,run.desired,mask};return cp_start(base,CP_POLICY,a);
 }
 int r=cp_reply(base,CP_POLICY);if(r<=0)return r;
 if(r-1==CP_BUSY){if(!run.desired)(void)stop_barrier(base,run.revoke_mask);return 0;}
 if((uint32_t)(r-1)!=(run.desired?CP_ACTIVE:CP_OFF))return hold(0x480);
 run.stop_pending=run.stop_mask=0;
 if(run.desired){
  struct meta m;
  if(meta(base,run.slot,&m)||!m.enabled||!m.custom||!matches(&m,b)||
     !wanted(base,run.slot,m.generation)||csnd_event_revision()!=run.revision){
   unready(run.slot);run.desired=0;return 0;
  }
 }
 b->active=run.desired;b->phase=run.desired?CP_ACTIVE:CP_OFF;
 if(!run.desired)run.recovery_rebind_mask&=~(1u<<run.slot);
 resource_ready(run.slot,run.desired);
 run.diag[D_POLICIES]++;run.last_scan=~run.revision;
 if(run.resume_state){
  uint32_t state=run.resume_state;run.slot=run.resume_slot;run.revision=run.resume_revision;
  run.desired=run.resume_desired;run.resume_state=0;phase(state);
 }else phase(R_IDLE);
 return 0;
}
/* A settings change revokes an already active OTHER slot between chunk ACKs.
 * Upload may pause while that native clip retires; photo/mode/power never do.
 * One saved continuation suffices because there are exactly two slots. */
static void prioritize_revocation(uint64_t base,uint32_t revision){
 if(run.resume_state||run.stop_pending||run.state<R_IDLE||run.state>R_COMMIT||run.control.state!=NT_READY)return;
 if(run.checked_revision==revision&&run.tick%50)return;
 run.checked_revision=revision;
 for(uint32_t slot=0;slot<2;slot++)if(run.bank[slot].active){
  struct meta m;if(meta(base,slot,&m))continue;
  if(m.enabled&&m.custom&&matches(&m,&run.bank[slot])&&wanted(base,slot,m.generation))continue;
  run.resume_state=run.state;run.resume_slot=run.slot;run.resume_revision=run.revision;run.resume_desired=run.desired;
  run.slot=slot;run.revision=revision;run.desired=0;unready(slot);phase(R_POLICY);return;
 }
}
static int resource_tick_impl(uint64_t base,uint32_t revision){
 run.tick++;ST(run.diag[D_TICK],run.tick);
 if(run.recovery_state==4&&!run.recovery_rebind_mask&&run.state==R_IDLE)run.recovery_state=0;
 ST(run.fault[F_QUERY_STAGE],run.driver_stage);ST(run.fault[F_RECOVERY_STAGE],run.reclaim_stage?0x100+run.reclaim_stage:run.recovery_state);ST(run.diag[D_SCHEMA],1);
 if(run.state==R_HOLD){
  if(run.reclaim_stage==1)return reclaim_tick(base);
  if(LD(run.diag[D_ERROR])==0x400){
   if(reclaim_eligible()){
    /* Publish attempt before any send. Failed episodes never auto-retry. */
    ST(run.reclaim_attempt,1);run.reclaim_stage=1;run.reclaim_index=0;
    for(uint32_t i=0;i<6;i++)run.provisional[i]=(struct unit){0};
    ST(run.fault[F_RECOVERY_ERROR],0);return 0;
   }
   return bind_diag_tick(base);
  }
  return recover_query(base);
 }
 (void)reclaim_publish(base);
 if(run.state==R_INIT){
  if(!run.initialized){
   (void)FN(int(*)(void),0x8f92198)();
   csnd_runtime*s=(csnd_runtime*)(uintptr_t)(base+0x8fc8008ull);
   if(!LD(s->initialized))return 10;
   run.initialized=1;
  }
  if(run.last_scan==revision&&run.tick%50)return 0;
  run.last_scan=revision;
  struct meta m;int need=0;
  for(uint32_t i=0;i<2;i++)if(!meta(base,i,&m)&&m.enabled&&m.custom&&wanted(base,i,m.generation))need=1;
  if(!need)return 0;
  phase(R_CLAIM);return 0;
 }
 prioritize_revocation(base,revision);
 switch(run.state){
  case R_CLAIM:return claim_tick(base);case R_BIND:return bind_tick(base);
  case R_IDLE:return idle_tick(base,revision);case R_PREPARE:return prepare_tick(base);
  case R_CONVERT:return convert_tick(base);case R_TRANSFER:return transfer_tick(base);
  case R_COMMIT:return commit_tick(base);case R_POLICY:return policy_tick(base);
  case R_ROLLBACK:return rollback_tick(base);case R_QUERY:return query_tick(base);default:return hold(0x4ff);
 }
}
int csnd_resource_tick(uint64_t base,uint32_t revision){
 ST(run.query_snapshot_version,run.query_snapshot_version+1);
 int rc=resource_tick_impl(base,revision);
 ST(run.query_snapshot_version,run.query_snapshot_version+1);return rc;
}
uint32_t csnd_resource_focus_mode(void){return LD(run.diag[D_FOCUS])?1:0;}
int csnd_resource_dispatch(uint64_t base,uint32_t slot,uint32_t generation,uint32_t revision){
 run.diag[D_DISPATCH_CALLS]++;
 if(slot!=0||run.state==R_HOLD||run.stop_pending||!LD(run.diag[D_READY0]))return 6;
 struct meta m;
 if(meta(base,slot,&m)||m.generation!=generation||!m.enabled||!m.custom||
    !matches(&m,&run.bank[0])||revision!=csnd_event_revision()||!wanted(base,slot,generation)){
  run.diag[D_STALE]++;return 6;
 }
 /* The installed wrapper uses the original Sysnd loop0/sync0 one-shot API.
  * Its return only means the call returned, not speaker output/completion. */
 if(revision!=csnd_event_revision())return 6;
 uint32_t r=csnd_sysnd_async_once(17);ST(run.diag[D_LAST_NATIVE],r);
 if(r==1)run.diag[D_DISPATCH_RETURNED]++;return r==1?0:6;
}
void csnd_resource_snapshot(uint32_t out[32]){if(out)for(uint32_t i=0;i<32;i++)out[i]=LD(run.diag[i]);}
void csnd_resource_cp_snapshot(uint32_t out[16]){
 if(!out)return;
 for(uint32_t i=0;i<8;i++)out[i]=LD(run.cp_stats[i]);
 for(uint32_t i=0;i<2;i++){
  out[8+4*i]=LD(run.bank[i].cp_generation);out[9+4*i]=LD(run.bank[i].cp_revision);
  out[10+4*i]=LD(run.bank[i].length);out[11+4*i]=LD(run.bank[i].crc);
 }
}

/* A single seqlock attempt keeps export bounded; no IPC/filesystem work. */
void csnd_resource_driver_snapshot(uint32_t out[64]){
 if(!out)return;
 for(uint32_t i=0;i<64;i++)out[i]=0;
 if(LD(run.diag[D_STATE])==R_HOLD&&LD(run.diag[D_ERROR])==0x106){query_snapshot(out);return;}
 if(LD(run.diag[D_STATE])==R_HOLD&&LD(run.diag[D_ERROR])==0x400){
  out[0]=0x444e4942;out[1]=1;out[3]=LD(run.bind_tick);
  uint32_t v=LD(run.bind_version);
  for(uint32_t i=0;i<54;i++)out[4+i]=LD(run.bind_diag[i]);
  __atomic_thread_fence(__ATOMIC_ACQUIRE);
  if((v&1)||v!=LD(run.bind_version)||out[12]!=0x400){
   /* Fixed fail-closed template for concurrent/unpublished collection.
    * Never expose partial masks as strict extent evidence. */
   for(uint32_t i=4;i<58;i++)out[i]=0xffffffffu;
   out[7]=24;out[9]=out[10]=0;out[12]=0x400;out[13]=LD(run.diag[D_TICK]);
   out[53]=out[54]=out[55]=0;out[56]=0x302;out[57]=0;
  }
  return;
 }
 out[0]=0x37565244;out[1]=3;
 uint32_t before=LD(run.driver_version);if(before&1){out[49]=1;return;}
 out[2]=LD(run.driver_valid);out[3]=LD(run.driver_tick);
 for(uint32_t slot=0;slot<2;slot++){
  for(uint32_t i=0;i<20;i++)out[4+20*slot+i]=LD(run.driver_record[24*slot+i]);
  for(uint32_t i=0;i<4;i++)out[50+4*slot+i]=LD(run.driver_record[24*slot+20+i]);
 }
 out[44]=LD(run.driver_sequence[0]);out[45]=LD(run.driver_sequence[1]);
 out[46]=LD(run.driver_missed[0]);out[47]=LD(run.driver_missed[1]);out[48]=LD(run.driver_error);
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if(before!=LD(run.driver_version)){out[2]=0;out[49]=1;}
}

/* Last original AF gain call, including factory fallback. Advisory only. */
void csnd_resource_focus_snapshot(uint32_t out[9]){
 if(!out)return;
 for(uint32_t i=0;i<9;i++)out[i]=0;
 uint32_t v=LD(run.driver_version);if(v&1)return;
 out[0]=0x31534346u;
 for(uint32_t i=0;i<8;i++)out[i+1]=LD(run.focus_diag[i]);
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if(v!=LD(run.driver_version))for(uint32_t i=0;i<9;i++)out[i]=0;
}
