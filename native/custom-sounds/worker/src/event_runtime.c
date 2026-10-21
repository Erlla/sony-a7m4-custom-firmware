#include "event_runtime.h"
#ifndef EVENT_LINK_ANCHOR
#define EVENT_LINK_ANCHOR 0x09100000ull
#endif
#define QCAP 32u
#define SCAP 64u
#define LD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define ST(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define INC(x) __atomic_add_fetch(&(x),1,__ATOMIC_RELAXED)
typedef int(*size_fn)(const void*);
typedef int(*ticket_fn)(er_u32,er_u32*,er_u32*);
typedef int(*thread_fn)(const void*);
typedef int(*sleep_fn)(er_u32);
typedef int(*maintenance_fn)(void);
struct key {er_u32 slot,seq,member,ordinal;};
struct job {struct key key;er_u32 generation,epoch;};
struct thread_spec {er_u64 name;er_u32 type,pad;er_u64 entry,arg;unsigned short subsystem,pad2;int priority;};
enum {D_SCHEMA,D_INIT,D_READY,D_REVISION,D_POLICY_SEEN,D_POLICY_ERROR,D_FOCUS_MODE,
 D_EXPOSURE,D_FOCUS,D_BAD_PACKET,D_DUPLICATE,D_PENDING,D_QUEUED,D_OVERFLOW,D_BUSY_DROP,
 D_SUPPRESSED,D_STALE_EPOCH,D_STALE_GENERATION,D_DISPATCH_CALLS,D_DISPATCH_RETURNED,
 D_DISPATCH_ERROR,D_LAST_STATUS,D_LAST_SLOT,D_LAST_GENERATION,D_RESERVED_KIND,
 D_RESERVED_COMPLETION,D_TICKS,D_MAINTENANCE_STATUS,D_HIGHWATER,D_LAST_SOURCE,D_LAST_LENGTH,D_RESOURCE_FLAGS};
struct runtime {er_u32 diag[32],gate,head,tail,count,used,next,throttle;
 struct key seen[SCAP];struct job queue[QCAP];struct thread_spec thread;};
static struct runtime run;
static er_u64 base(void){return (er_u64)&csnd_event_startup-EVENT_LINK_ANCHOR;}
static int enter(void){er_u32 zero=0;return __atomic_compare_exchange_n(&run.gate,&zero,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);}
static void leave(void){ST(run.gate,0);}
static er_u32 word(const er_u8*p){return p[0]|((er_u32)p[1]<<8)|((er_u32)p[2]<<16)|((er_u32)p[3]<<24);}
static er_u32 half(const er_u8*p){return p[0]|((er_u32)p[1]<<8);}
static int equal(struct key a,struct key b){return a.slot==b.slot&&a.seq==b.seq&&a.member==b.member&&a.ordinal==b.ordinal;}
er_u32 csnd_event_revision(void){return LD(run.diag[D_REVISION]);}
void csnd_event_config_changed(void){INC(run.diag[D_REVISION]);}

/* Worker-only, once per successfully rebuilt fresh-lease session.  Gate-busy
 * leaves revision/seen/queue unchanged so resource can retry next tick.
 * Queue is never cleared: its existing revision checks reject old jobs. */
int csnd_event_resource_epoch(er_u32 expected_revision){
 er_u32 zero=0;
 if(!__atomic_compare_exchange_n(&run.gate,&zero,1,1,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED))return 0;
 er_u32 revision=expected_revision;
 if(!__atomic_compare_exchange_n(&run.diag[D_REVISION],&revision,revision+1,1,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){leave();return 0;}
 run.used=run.next=0;
 leave();return 1;
}


static int remember(struct key k,er_u32 epoch){
 if(!enter()){INC(run.diag[D_BUSY_DROP]);return 0;}
 if(epoch!=csnd_event_revision()){INC(run.diag[D_STALE_EPOCH]);leave();return 0;}
 for(er_u32 i=0;i<run.used;i++)if(equal(k,run.seen[i])){INC(run.diag[D_DUPLICATE]);leave();return 0;}
 run.seen[run.next]=k;run.next=(run.next+1)&(SCAP-1);if(run.used<SCAP)run.used++;
 leave();return 1;
}
static void admit(struct key k){
 er_u32 gen=0,route=0,epoch=csnd_event_revision();
 if(!remember(k,epoch))return;
 if(!LD(run.diag[D_READY])){INC(run.diag[D_SUPPRESSED]);return;}
 int status=((ticket_fn)(base()+0x8f9242c))(k.slot,&gen,&route);
 if(status||!gen||route!=k.slot+2){ST(run.diag[D_LAST_STATUS],(er_u32)status);INC(run.diag[D_SUPPRESSED]);return;}
 if(epoch!=csnd_event_revision()){INC(run.diag[D_STALE_EPOCH]);return;}
 if(!enter()){INC(run.diag[D_BUSY_DROP]);return;}
 if(run.count==QCAP){INC(run.diag[D_OVERFLOW]);leave();return;}
 run.queue[run.tail]=(struct job){k,gen,epoch};run.tail=(run.tail+1)&(QCAP-1);run.count++;
 ST(run.diag[D_PENDING],run.count);if(run.count>LD(run.diag[D_HIGHWATER]))ST(run.diag[D_HIGHWATER],run.count);
 INC(run.diag[D_QUEUED]);leave();
}
void csnd_event_exposure(const er_u8*p){
 INC(run.diag[D_EXPOSURE]);
 int n=p?((size_fn)(base()+0x17165f0))(p):-1;ST(run.diag[D_LAST_LENGTH],(er_u32)n);
 if(n!=28||p[0]!=4||half(p+2)!=0x1001||word(p+8)!=0xf000){INC(run.diag[D_BAD_PACKET]);return;}
 admit((struct key){0,word(p+4),word(p+12),word(p+16)});
}
int csnd_event_focus(const er_u8*p,er_u32 source){
 ST(run.diag[D_LAST_SOURCE],source);
 if(source!=0x90037ff0u)return 0;
 INC(run.diag[D_FOCUS]);
 int n=p?((size_fn)(base()+0x17165f0))(p):-1;ST(run.diag[D_LAST_LENGTH],(er_u32)n);
 if(n!=28||p[0]!=4||p[1]||half(p+2)!=0x7ff0||word(p+8)!=0xf000||
    word(p+12)!=0x46415343u||word(p+16)!=1||word(p+20)!=1||word(p+24)!=~0x46415343u){INC(run.diag[D_BAD_PACKET]);return 0;}
 er_u32 mode=csnd_resource_focus_mode();ST(run.diag[D_FOCUS_MODE],mode);
 /* Mode1 is native CP playback: no AP duplicate is ever created. */
 if(mode==2)admit((struct key){1,word(p+4),0,0});
 return 1;
}

extern er_u32 csnd_volume_get(er_u32);
extern int csnd_volume_worker_tick(void);
void csnd_event_pump(void){
 er_u32 v0=csnd_volume_get(0),v1=csnd_volume_get(1);
 (void)csnd_volume_worker_tick();
 if(v0!=csnd_volume_get(0)||v1!=csnd_volume_get(1))csnd_event_config_changed();
 er_u32 epoch=csnd_event_revision();INC(run.diag[D_TICKS]);
 if(epoch!=LD(run.diag[D_POLICY_SEEN])||++run.throttle>=50){
  run.throttle=0;
  /* Durable mechanical OFF runs on this worker, never on an event callback.
   * A failed commit leaves the original pending latch authoritative. */
  int r=((maintenance_fn)(base()+0x8f92018))();
  ST(run.diag[D_MAINTENANCE_STATUS],(er_u32)r);
 }
 /* Resource transport is a single nonblocking state-machine step per pump. */
 int policy_status=csnd_resource_tick(base(),epoch);
 ST(run.diag[D_POLICY_ERROR],(er_u32)policy_status);ST(run.diag[D_POLICY_SEEN],epoch);
 ST(run.diag[D_FOCUS_MODE],csnd_resource_focus_mode());
 struct job job;
 if(!enter())return;
 if(!run.count){leave();return;}
 job=run.queue[run.head];run.head=(run.head+1)&(QCAP-1);run.count--;ST(run.diag[D_PENDING],run.count);leave();
 if(job.epoch!=csnd_event_revision()){INC(run.diag[D_STALE_EPOCH]);return;}
 er_u32 gen=0,route=0;int r=((ticket_fn)(base()+0x8f9242c))(job.key.slot,&gen,&route);
 if(r||gen!=job.generation||route!=job.key.slot+2||!gen){INC(run.diag[D_STALE_GENERATION]);ST(run.diag[D_LAST_STATUS],(er_u32)r);return;}
 if(job.key.slot==1&&csnd_resource_focus_mode()!=2){INC(run.diag[D_SUPPRESSED]);return;}
 if(job.epoch!=csnd_event_revision()){INC(run.diag[D_STALE_EPOCH]);return;}
 ST(run.diag[D_LAST_SLOT],job.key.slot);ST(run.diag[D_LAST_GENERATION],job.generation);
 INC(run.diag[D_DISPATCH_CALLS]);
 r=csnd_resource_dispatch(base(),job.key.slot,job.generation,job.epoch);
 ST(run.diag[D_LAST_STATUS],(er_u32)r);
 if(r)INC(run.diag[D_DISPATCH_ERROR]);else INC(run.diag[D_DISPATCH_RETURNED]);
}
void csnd_event_worker(void*unused){
 (void)unused;ST(run.diag[D_SCHEMA],1);ST(run.diag[D_READY],1);
 for(;;){csnd_event_pump();((sleep_fn)(base()+0x1716960))(2000);}
}
__attribute__((section(".text.event_start"),noinline))
void csnd_event_startup(void){
 er_u32 zero=0;if(!__atomic_compare_exchange_n(&run.diag[D_INIT],&zero,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
 ST(run.diag[D_SCHEMA],1);ST(run.diag[D_POLICY_SEEN],~csnd_event_revision());
 run.thread.name=(er_u64)"CSNDSysnd";run.thread.type=0;run.thread.pad=0;
 run.thread.entry=(er_u64)&csnd_event_worker;run.thread.arg=0;run.thread.subsystem=0x105;run.thread.pad2=0;run.thread.priority=0;
 int r=((thread_fn)(base()+0x1715ba0))(&run.thread);
 /* Only actual worker entry publishes ready. Ambiguous positive return is
  * not retried and not evidence of a running thread. */
 ST(run.diag[D_INIT],r<0?3u:2u);if(r<0)ST(run.diag[D_LAST_STATUS],(er_u32)r);
}
void csnd_event_snapshot(er_u32 out[32]){if(out)for(er_u32 i=0;i<32;i++)out[i]=LD(run.diag[i]);}
