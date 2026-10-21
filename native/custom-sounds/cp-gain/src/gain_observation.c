#include <stdint.h>
typedef uint32_t u32;
struct slot {u32 h[3],lo,hi,n,g,r,pg,pr,phase,q,received,crc;};
struct owner {volatile u32 gate;u32 session;struct slot s[2];};
struct receipt {volatile u32 version;u32 caller,packed,kind,g,r,lo,n,context,tick_raw;};
struct gain_diag {volatile u32 gate;u32 sequence;volatile u32 missed;struct receipt rec[2];};
struct gain_diag csnd_gain_diag __attribute__((section(".bss.gain_obs")));
_Static_assert(sizeof(struct gain_diag)==92,"bounded same-page gain observations92");
#define OWNER ((struct owner*)0x1564840u)
#define W(a) (*(volatile const u32*)(a))
static void publish(u32 kind,u32 caller,u32 mask,u32 original,u32 selected,u32 g,u32 r,u32 lo,u32 n,u32 context){
 if(kind!=4&&kind!=17)return;
 struct gain_diag*d=&csnd_gain_diag;u32 zero=0;
 if(!__atomic_compare_exchange_n(&d->gate,&zero,1,1,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED)){d->missed=1;return;}
 volatile struct receipt*t=&d->rec[kind==4];
 __atomic_store_n(&t->version,t->version+1,__ATOMIC_RELEASE);
 __atomic_thread_fence(__ATOMIC_RELEASE);
 t->caller=caller;t->packed=mask|((original&7)<<24)|((selected&7)<<27)|(1u<<30);
 t->kind=kind;t->g=g;t->r=r;t->lo=lo;t->n=n;t->context=context;t->tick_raw=W(0x122072cu+5*0x2cu);d->sequence++;
 __atomic_store_n(&t->version,t->version+1,__ATOMIC_RELEASE);
 __atomic_store_n(&d->gate,0,__ATOMIC_RELEASE);
}
/* Actual native APP has the same caller-SP+0x60 descriptor as PIN/CLIP.
 * All ownership, mode and descriptor predicates remain mandatory. */
u32 csnd_custom_gain_scalar(u32 original,u32 kind,const volatile u32*desc,u32 caller){
 u32 mask=0,selected=original,g=0,r=0,lo=0,n=0,context=0;
 struct owner*o=OWNER;u32 zero=0;
#define REJECT(condition,bit) do{if(condition){mask=1u<<(bit);goto done;}}while(0)
 REJECT(caller!=0x5dea2fu&&caller!=0x5df8fbu&&caller!=0x5dedbfu,0);
 REJECT(kind!=4&&kind!=17,1);REJECT(original>7,2);REJECT(!(W(0xf4aeccu)&2),3);
 REJECT(!__atomic_compare_exchange_n(&o->gate,&zero,1,1,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED),4);
 const volatile struct slot*s=&o->s[kind==4];
 g=s->g;r=s->r;lo=s->lo;n=s->n;context=1u|(s->phase<<1)|(s->q<<5);
#define LOCK_REJECT(condition,bit) do{if(condition){mask=1u<<(bit);goto unlock;}}while(0)
 LOCK_REJECT(!o->session||o->session==0xffffffffu,5);LOCK_REJECT(s->phase!=6,6);LOCK_REJECT(s->q,7);
 LOCK_REJECT(!s->g,8);LOCK_REJECT(s->g!=s->pg,9);LOCK_REJECT(s->r!=s->pr,10);LOCK_REJECT(s->received!=s->n,11);
 LOCK_REJECT(s->hi!=8,12);LOCK_REJECT(s->n<64||s->n>123872u||(s->n&31),13);
 LOCK_REJECT(s->lo<0x1b800000u||s->lo>0x1b825800u,14);
 LOCK_REJECT(!s->h[0]||!s->h[1]||!s->h[2],15);LOCK_REJECT(s->h[0]==s->h[1]||s->h[1]==s->h[2]||s->h[0]==s->h[2],16);
 LOCK_REJECT(desc[0]!=s->lo,17);LOCK_REJECT(desc[1]!=8,18);LOCK_REJECT(desc[2]!=s->n,19);LOCK_REJECT(desc[8]!=s->lo,20);
 LOCK_REJECT((desc[3]&255)!=kind,21);LOCK_REJECT((desc[3]>>16)!=1,22);
 LOCK_REJECT(kind==17&&((u32(*)(void*,u32))0xba667bu)((void*)0x106a620u,17)==2,23);
 selected=7;
unlock:__atomic_store_n(&o->gate,0,__ATOMIC_RELEASE);
done:publish(kind,caller,mask,original,selected,g,r,lo,n,context);return selected;
}
/* One stable last-observation read. context_match is not a same-play nonce.
 * Any publication collision sets a sticky cold-boot loss flag and invalidates context. */
void csnd_gain_snapshot(u32 kind,u32 g,u32 r,u32 lo,u32 n,u32*caller,u32*packed){
 *caller=0xffffffffu;*packed=0;
 if(kind!=4&&kind!=17)return;
 const struct gain_diag*d=&csnd_gain_diag;const volatile struct receipt*t=&d->rec[kind==4];
 u32 before=__atomic_load_n(&t->version,__ATOMIC_ACQUIRE);if(!before||(before&1))return;
 u32 c=t->caller,p=t->packed;
 u32 match=t->context&&t->kind==kind&&t->g==g&&t->r==r&&t->lo==lo&&t->n==n&&!d->missed;
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if(before!=__atomic_load_n(&t->version,__ATOMIC_RELAXED))return;
 *caller=c;*packed=p|(match?(1u<<31):0);
}

/* Two stable read-only pages; never authorizes playback or owner changes. */
u32 csnd_focus_observation_page(u32 page,u32 expected,u32*out,u32*seq){
 if(page>1)return 2;
 const struct gain_diag*d=&csnd_gain_diag;const volatile struct receipt*t=&d->rec[1];
 u32 v=__atomic_load_n(&t->version,__ATOMIC_ACQUIRE);
 if(v&1)return 1;
 if(page&&v!=expected)return 3;
 if(page){out[0]=t->g;out[1]=t->r;out[2]=t->context;out[3]=d->missed;}
 else{out[0]=v;out[1]=t->tick_raw;out[2]=t->caller;out[3]=t->packed;}
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 if(v!=__atomic_load_n(&t->version,__ATOMIC_RELAXED))return 3;
 *seq=v;return 0;
}
