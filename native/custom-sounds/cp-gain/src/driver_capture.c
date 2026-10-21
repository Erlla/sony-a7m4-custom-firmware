/* Read-only source/MMIO observation. Candidate RX BA5000 and BSS1564900; root integration required.
 * Bounded 128-byte sample signature, no allocation/log/sleep/CRC over payload.
 */
#include "driver_capture.h"
#define W(a) (*(volatile const u32*)(a))
struct driver_diag csnd_driver_diag __attribute__((section(".bss.driver_diag")));
static void record_copy(struct driver_record*d,const struct driver_record*s){
 volatile u32*a=(volatile u32*)d;const volatile u32*b=(const volatile u32*)s;
 for(u32 i=0;i<sizeof(*d)/4;i++)a[i]=b[i];
}
struct slot {u32 h[3],lo,hi,n,g,r,pg,pr,phase,q,received,crc;};
struct owner {u32 gate,session;struct slot s[2];u32 last_busy;u8 receipt_header[40];u32 receipt_valid,receipt_result,calls[2],last_kind,last_rc;};
_Static_assert(__builtin_offsetof(struct owner,receipt_valid)==164,"frozen owner ABI");
#ifndef OWNER_VA
#define OWNER_VA 0x1564840u
#endif
extern void csnd_gain_snapshot(u32 kind,u32 g,u32 r,u32 lo,u32 n,u32*caller,u32*packed);
void csnd_driver_pre(u32 entry_sp){
 struct driver_diag*d=&csnd_driver_diag;u32 zero=0;
 if(!__atomic_compare_exchange_n(&d->gate,&zero,1,1,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED)){
  /* Best-effort lower-bound diagnostic only; never add an LDREX retry. */
  d->missed=d->missed+1;return;
 }
 const struct owner*o=(const struct owner*)OWNER_VA;
 u32 start=W(0x145b098),end=W(0x145b09c),slot=2;
 if(start<0x1b800000u||end>0x1b84b000u){__atomic_store_n(&d->gate,0,__ATOMIC_RELEASE);return;}
 for(u32 i=0;i<2;i++)if(o->s[i].phase==6&&o->s[i].n>=64&&o->s[i].n<=123872&&
  o->s[i].lo==start&&end>=start&&end-start==o->s[i].n&&o->s[i].hi==8)slot=i;
 if(slot==2){__atomic_store_n(&d->gate,0,__ATOMIC_RELEASE);return;}
 const struct slot*s=&o->s[slot];struct driver_record20*r=&d->pending;
 d->entry_sp=entry_sp;d->pending_kind=slot?4:17;
 r->sequence=++d->sequence;r->tick_raw=W(0x122072c+5*0x2c);
 r->kind=d->pending_kind;r->result=0xffffffffu;r->phys_lo=s->lo;r->phys_hi=s->hi;
 r->generation=s->g;r->revision=s->r;
 /* At A56BB2 this is the final encoded/native driver branch. Descriptor
  * format0 is independently checked from actor copied request word+20. */
 r->format=W(0xfc6ad8+0x20);r->base=W(0x145b090);r->capacity=W(0x145b094);
 r->start=start;r->end=end;csnd_gain_snapshot(r->kind,r->generation,r->revision,r->phys_lo,s->n,&r->last_gain_caller,&r->gain_receipt);
 r->flags=1;
}
void csnd_driver_post(u32 entry_sp,u32 result){
 struct driver_diag*d=&csnd_driver_diag;
 if(!__atomic_load_n(&d->gate,__ATOMIC_ACQUIRE)||d->entry_sp!=entry_sp)return;
 struct driver_record20*r=&d->pending;
 r->result=result;r->bus_base=W(0xf48a1c00);r->bus_capacity=W(0xf48a1c04);
 r->bus_start=W(0xf48a1c0c);r->bus_end=W(0xf48a1c18);
 if(W(0x145b098)!=r->start||W(0x145b09c)!=r->end)r->flags|=2;
 __atomic_store_n(&d->version,d->version+1,__ATOMIC_RELEASE);
 __atomic_thread_fence(__ATOMIC_RELEASE); /* odd version visible before fields */
 struct driver_record*dst=&d->record[r->kind==4];
 volatile u32*to=(volatile u32*)dst;const volatile u32*from=(const volatile u32*)r;
 for(u32 i=0;i<20;i++)to[i]=from[i];
 /* Read the real StockVolume row; missing/uninitialized is never default7. */
 dst->stock_kind=0xffffffffu;dst->stock_volume=0xffffffffu;
 const volatile u8*table=(const volatile u8*)0x106a94cu;
 for(u32 i=0;i<20;i++)if(table[4*i+1]==r->kind){
  dst->stock_kind=table[4*i+1];dst->stock_volume=table[4*i];break;
 }
 dst->gain3904=W(0xf48a3904);dst->gain3908=W(0xf48a3908);
 __atomic_store_n(&d->version,d->version+1,__ATOMIC_RELEASE);
 __atomic_store_n(&d->gate,0,__ATOMIC_RELEASE);
}
u32 csnd_driver_query(u32 kind,struct driver_record*out,u32*meta){
 struct driver_diag*d=&csnd_driver_diag;
 if((kind!=4&&kind!=17)||!out||!meta)return 2;
 u32 before=__atomic_load_n(&d->version,__ATOMIC_ACQUIRE);
 if(before&1)return 1;
 record_copy(out,&d->record[kind==4]);
 meta[0]=before;meta[1]=d->missed;
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 return before==__atomic_load_n(&d->version,__ATOMIC_RELAXED)?0:1;
}
u32 csnd_driver_page(u32 kind,u32 page,u32 expected_sequence,u32*out4){
 struct driver_record record;u32 meta[2];
 if(!out4||page>6)return 2;
 u32 rc=csnd_driver_query(kind,&record,meta);if(rc)return rc;
 if(record.sequence&&record.kind!=kind)return 2;
 if(!page){out4[0]=0x10003;out4[1]=kind;out4[2]=record.sequence;out4[3]=meta[1];return 0;}
 if(record.sequence!=expected_sequence)return 3;
 const u32*words=(const u32*)&record;
 for(u32 i=0;i<4;i++)out4[i]=words[4*(page-1)+i];
 return 0;
}
extern u32 csnd_cp_owner_reply_original(const u8*,u8*);
static u32 read16(const u8*p){return p[0]|(u32)p[1]<<8;}
static u32 read32(const u8*p){return read16(p)|(u32)read16(p+2)<<16;}
static void put16(u8*p,u32 x){p[0]=x;p[1]=x>>8;}
static void put32(u8*p,u32 x){put16(p,x);put16(p+2,x>>16);}
extern u32 csnd_focus_observation_page(u32,u32,u32*,u32*);
u32 csnd_driver_owner_reply(const u8*req,u8*out){
 /* All existing op/QUERY pages execute unchanged frozen implementation. */
 if(read32(req+4)!=5||(read32(req+24)!=2&&read32(req+24)!=5))return csnd_cp_owner_reply_original(req,out);
 struct owner*o=(struct owner*)OWNER_VA;u32 phase=2,session=read32(req+8);
 for(u32 i=0;i<40;i++)out[i]=0;
 put16(out,0x807e);put16(out+4,24);put16(out+6,read16(req+20));
 put32(out+8,session);put32(out+12,5);put32(out+20,read32(req+36));
 if(read16(req)!=0x7e||read16(req+2)||read32(req+12)!=0x4e535343u||
  !session||session==0xffffffffu||session!=read32(req+16)||read16(req+22)>1||!o->receipt_valid)goto reply;
 for(u32 i=0;i<40;i++)if(req[i]!=o->receipt_header[i])goto reply;
 o->receipt_valid=0; /* exact original receipt consumed before diagnostic read */
 if(session!=o->session){phase=4;goto reply;}
 u32 words[4],kind=read32(req+28),page=read32(req+32),seq=read32(req+36);
 u32 rc;
 if(read32(req+24)==5){if(kind!=4)goto reply;rc=csnd_focus_observation_page(page,seq,words,&seq);}
 else rc=csnd_driver_page(kind,page,seq,words);
 if(rc){phase=rc==3?4:rc==1?1:2;goto reply;}
 put32(out+20,read32(req+24)==5?seq:page?seq:words[2]);
 for(u32 i=0;i<4;i++)put32(out+24+4*i,words[i]);
 phase=0;
reply:put32(out+16,phase);return 2;
}
