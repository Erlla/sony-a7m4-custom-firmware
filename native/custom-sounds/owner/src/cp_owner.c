/* CP 8ea53 only. Transaction RPC is bounded and has no wait/Stop/allocator.
 * AP retains six native leases for the entire ownership session. Data transfer
 * is allowed only after PREPARED; publication only after transfer completion.
 * The original registry is never modified. All samples retain format 0.
 */
#include "cp_owner.h"
struct sound_owner csnd_cp_owner;
extern u32 csnd_cp_lookup_original(void*,u32,void*);
extern u32 csnd_cp_exists_original(void*,u32);
extern u32 csnd_cp_start_original(void*,const u8*,u32);
extern u32 csnd_cp_validate_original(void*,const u8*);
extern void csnd_cp_clean_buffer(void*,u32);
#define W(a) (*(volatile const u32*)(a))
#define B(a) (*(volatile const u8*)(a))
#define WRITER 0x80000000u
#define REG ((void*)0x106a620)
#define MAX_ENCODED 123872u
static u32 r16(const u8*p){return p[0]|(u32)p[1]<<8;}
static u32 r32(const u8*p){return r16(p)|r16(p+2)<<16;}
static void w16(u8*p,u32 x){p[0]=x;p[1]=x>>8;}
static void w32(u8*p,u32 x){w16(p,x);w16(p+2,x>>16);}
static void clear(void*p,u32 n){u8*b=p;while(n--)*b++=0;}
static u32 crc_byte(u32 c,u8 b){c^=b;for(u32 i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));return c;}
static int cas(u32 old,u32 value){return __atomic_compare_exchange_n(
 &csnd_cp_owner.gate,&old,value,1,__ATOMIC_ACQ_REL,__ATOMIC_RELAXED);}
static void unlock(void){__atomic_store_n(&csnd_cp_owner.gate,0,__ATOMIC_RELEASE);}
static u32 busy(void){
 static const u32 fields[]={0xfc6aec,0xfc6af0,0xfc6b20,0xfc6b38,
  0xf57bad,0x14b36a5,0x121f118,0x121f130,0xf57b4d,0x121f195,0x121f135};
 u32 state=W(0x121f118),active=W(0x121f130),m=0;
 __asm__ volatile("dmb sy":::"memory");
 for(u32 i=0;i<11;i++){
  u32 a=fields[i],v=(a&1)?B(a&~1u):W(a);
  if(v)m|=1u<<i;
 }
 __asm__ volatile("dmb sy":::"memory");
 if(W(0x121f118)!=state||W(0x121f130)!=active)m|=WRITER;
 csnd_cp_owner.last_busy=m;return m;
}
static int get_extent(u32 handle,u32*out){
 u8 request[52],reply[40];clear(request,52);clear(reply,40);
 w16(request+12,0x2a);w32(request+20,handle);w16(request+32,1);
 u32 rc=((u32(*)(void*,void*,void*))0xafd00b)(request,reply,reply+24);
 if(rc!=2||r16(reply)!=0x802a||r16(reply+2)||r32(reply+12)!=handle||
    r32(reply+32)!=51200)return 0;
 out[0]=r32(reply+24);out[1]=r32(reply+28);return 1;
}
static int bind(struct sound_slot*s,const u8*a,u32 slot){
 u32 p[6];
 if(r32(a+12))return OWN_INVALID;
 for(u32 i=0;i<3;i++){
  u32 h=r32(a+4*i);
  if(!h||h==0xffffffffu||!get_extent(h,p+2*i))return OWN_INVALID;
  for(u32 j=0;j<i;j++)if(h==r32(a+4*j))return OWN_INVALID;
  struct sound_slot*other=&csnd_cp_owner.slot[slot^1];
  if(other->phase)for(u32 j=0;j<3;j++)if(h==other->handle[j])return OWN_INVALID;
 }
 if(p[1]!=8||p[3]!=8||p[5]!=8||p[0]<0x1b800000u||
    p[0]>0x1b800000u+3*51200u||p[2]!=p[0]+51200u||
    p[4]!=p[0]+102400u)return OWN_INVALID;
 if(slot==0&&csnd_cp_exists_original(REG,17)==2)return OWN_INVALID;
 if(s->phase){
  for(u32 i=0;i<3;i++)if(s->handle[i]!=r32(a+4*i))return OWN_STALE;
  return OWN_OK;
 }
 for(u32 i=0;i<3;i++)s->handle[i]=r32(a+4*i);
 s->phys_lo=p[0];s->phys_hi=p[1];s->phase=OWN_OFF;return OWN_OK;
}
static u32 transact(u32 op,u32 session,u32 slot,const u8*a){
 struct sound_slot*s=&csnd_cp_owner.slot[slot];
 if(!cas(0,WRITER))return OWN_BUSY;
 u32 result=OWN_INVALID,gen=r32(a),rev=r32(a+4),n=r32(a+8),flags=r32(a+12);
 if(csnd_cp_owner.session&&csnd_cp_owner.session!=session){result=OWN_STALE;goto done;}
 if(op==OWN_BIND){
  result=bind(s,a,slot);if(result==OWN_OK)csnd_cp_owner.session=session;goto done;
 }
 if(!s->phase){result=OWN_NOTBOUND;goto done;}
 if(op==OWN_QUERY){result=s->quiesce?OWN_BUSY:s->phase;goto done;}
 if(op==OWN_PREPARE){
  if(!gen||n||flags)goto done;
  if(s->quiesce&&(s->pending_generation!=gen||s->pending_revision!=rev)&&busy()){result=OWN_BUSY;goto done;}
  if(s->phase==OWN_PREPARED&&s->generation==gen&&s->revision==rev){result=OWN_PREPARED;goto done;}
  if((int)(gen-s->generation)<0){result=OWN_STALE;goto done;}
  s->pending_generation=gen;s->pending_revision=rev;s->quiesce=1;
  __asm__ volatile("dmb sy":::"memory");
  if(busy()){result=OWN_BUSY;goto done;}
  s->phase=OWN_PREPARED;s->generation=gen;s->revision=rev;s->quiesce=0;
  s->received=0;s->crc=0xffffffffu;
  result=OWN_PREPARED;goto done;
 }
 if(op==OWN_COMMIT){
  if(s->generation!=gen||s->revision!=rev){result=OWN_STALE;goto done;}
  if(!n||n>MAX_ENCODED||(n&31)||s->quiesce||n!=s->received||flags!=~s->crc)goto done;
  if(s->phase==OWN_ACTIVE&&s->length==n){result=OWN_ACTIVE;goto done;}
  if(s->phase!=OWN_PREPARED)goto done;
  clear((void*)(s->phys_lo+n),64);
  csnd_cp_clean_buffer((void*)s->phys_lo,n+64);
  s->length=n;__asm__ volatile("dmb sy":::"memory");s->phase=OWN_ACTIVE;
  result=OWN_ACTIVE;goto done;
 }
 if(op==OWN_POLICY){
  if(s->generation!=gen||s->revision!=rev){result=OWN_STALE;goto done;}
  if(n>1||flags>3||(n&&flags)||s->phase==OWN_PREPARED)goto done;
  if(n){
   if(!s->length||s->quiesce)goto done;
   s->phase=OWN_ACTIVE;result=OWN_ACTIVE;goto done;
  }
  for(u32 i=0;i<2;i++)if((flags&(1u<<i))&&csnd_cp_owner.slot[i].phase==OWN_ACTIVE)
   csnd_cp_owner.slot[i].quiesce=2;
  s->pending_generation=gen;s->pending_revision=rev;s->quiesce=2;
  __asm__ volatile("dmb sy":::"memory");
  if(busy()){result=OWN_BUSY;goto done;}
  s->phase=OWN_OFF;s->quiesce=0;result=OWN_OFF;
 }
done:unlock();return result;
}
/* Raw native message is still owned by AFF9F0 here. No raw pointer escapes.
 * Its original min(72,length) copy/free and service response remain intact. */
void csnd_cp_receive_capture(u32 source,const u8*req,u32 bytes){
 if(bytes<40||bytes>1000||r16(req)!=0x7e||r32(req+12)!=0x4e535343u)return;
 csnd_cp_owner.receipt_valid=0;
 if(r16(req+2)||r32(req+8)!=source||r32(req+16)!=source)return;
 u32 op=r32(req+4),slot=r16(req+22),result=OWN_INVALID;
 if(slot>1||!source||source==0xffffffffu||op<1||op>6)return;
 for(u32 i=0;i<40;i++)csnd_cp_owner.receipt_header[i]=req[i];
 if(op!=OWN_COPY){if(bytes==40)csnd_cp_owner.receipt_valid=1;return;}
 u32 gen=r32(req+24),rev=r32(req+28),off=r32(req+32),n=r32(req+36);
 if(!n||n>960||bytes!=40+n||off>MAX_ENCODED||n>MAX_ENCODED-off)goto publish;
 if(!cas(0,WRITER)){result=OWN_BUSY;goto publish;}
 struct sound_slot*s=&csnd_cp_owner.slot[slot];
 if(csnd_cp_owner.session!=r32(req+8)||s->generation!=gen||s->revision!=rev){result=OWN_STALE;goto release;}
 if(s->phase!=OWN_PREPARED||s->quiesce)goto release;
 u8*dst=(u8*)(s->phys_lo+off);const u8*src=req+40;
 if(off<s->received){
  if(off+n!=s->received)goto release;
  for(u32 i=0;i<n;i++)if(dst[i]!=src[i])goto release;
 }else{
  if(off!=s->received)goto release;
  u32 crc=s->crc;for(u32 i=0;i<n;i++){dst[i]=src[i];crc=crc_byte(crc,src[i]);}
  s->crc=crc;s->received+=n;
 }
 result=OWN_OK;
release:unlock();
publish:csnd_cp_owner.receipt_result=result;csnd_cp_owner.receipt_valid=1;
}
u32 csnd_cp_owner_reply(const u8*req,u8*out){
 clear(out,40);w16(out,0x807e);w16(out+4,24);w16(out+6,r16(req+20));
 u32 op=r32(req+4),session=r32(req+8),slot=r16(req+22),phase=OWN_INVALID;
 w32(out+8,session);w32(out+12,op);
 if(r16(req)==0x7e&&!r16(req+2)&&r32(req+12)==0x4e535343u&&
    session&&session!=0xffffffffu&&session==r32(req+16)&&slot<2&&op>=1&&op<=6&&csnd_cp_owner.receipt_valid){
  for(u32 i=0;i<40;i++)if(req[i]!=csnd_cp_owner.receipt_header[i])goto reply;
  csnd_cp_owner.receipt_valid=0;
  if(op==OWN_QUERY&&r32(req+24)==1){
   if(session!=csnd_cp_owner.session){phase=OWN_STALE;goto reply;}
   /* Advisory counters only: not an atomic audio-completion snapshot. */
   w32(out+20,csnd_cp_owner.calls[1]);w32(out+24,csnd_cp_owner.calls[0]);
   w32(out+28,csnd_cp_owner.last_kind);w32(out+32,csnd_cp_owner.last_native_rc);
   w32(out+36,csnd_cp_owner.last_busy);phase=OWN_OK;goto reply;
  }
  phase=op==OWN_COPY?csnd_cp_owner.receipt_result:transact(op,session,slot,req+24);
  struct sound_slot*s=&csnd_cp_owner.slot[slot];
  w32(out+20,s->generation);w32(out+24,s->revision);
  w32(out+28,s->phys_lo);w32(out+32,s->phys_hi);w32(out+36,op==OWN_COPY?s->received:s->length);
 }
reply:
 w32(out+16,phase);return 2;
}
u32 csnd_cp_lookup(void*registry,u32 kind,void*output,u32 caller){
 u32 rc=csnd_cp_lookup_original(registry,kind,output);
 if(registry!=REG||(kind!=4&&kind!=17)||caller==0x5dcb67)return rc;
 struct sound_slot*s=&csnd_cp_owner.slot[kind==4];
 if(__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE)!=OWN_ACTIVE)return rc;
 if(kind==4&&rc){
  /* A native disable may precede Stop. These three original Stop builders
   * still need the old immutable end address; no Start/ordinary lookup may
   * bypass the original focus enable. */
  if(caller!=0x5deb65&&caller!=0x5df323&&caller!=0x5dfb95&&
     !(s->quiesce&&(caller==0x18f38b||caller==0x18f3a5)))return rc;
  ((u8*)output)[13]=0;
 }
 if(kind==17&&csnd_cp_exists_original(registry,17)==2)return rc;
 /* Native lookup output is an aligned 36-byte descriptor (original STRD). */
 u8*out=output;u32*words=output;words[0]=s->phys_lo;words[1]=s->phys_hi;words[2]=s->length;
 out[12]=kind;if(kind==17)out[13]=6;out[14]=1;out[15]=0;
 clear(out+16,16);words[8]=s->phys_lo;return 0;
}
u32 csnd_cp_exists(void*registry,u32 kind){
 u32 rc=csnd_cp_exists_original(registry,kind);
 if(registry==REG&&kind==17&&rc!=2&&
    __atomic_load_n(&csnd_cp_owner.slot[0].phase,__ATOMIC_ACQUIRE)==OWN_ACTIVE)return 2;
 return rc;
}
u32 csnd_cp_start(void*object,const u8*request,u32 mode){
 u32 kind=request[2];
 if(kind!=4&&kind!=17)return csnd_cp_start_original(object,request,mode);
 struct sound_slot*s=&csnd_cp_owner.slot[kind==4];
 __atomic_fetch_add(&csnd_cp_owner.calls[kind==4],1,__ATOMIC_RELAXED);
 csnd_cp_owner.last_kind=kind;csnd_cp_owner.last_native_rc=0xfffffffeu;
 if(!s->phase){
  u32 rc=csnd_cp_start_original(object,request,mode);
  csnd_cp_owner.last_native_rc=rc;return rc;
 }
 u32 old=__atomic_load_n(&csnd_cp_owner.gate,__ATOMIC_ACQUIRE);
 if((old&WRITER)||old==0x7fffffffu||!cas(old,old+1))return 0xe002;
 u32 rc=0xe002;
 if(!s->quiesce&&(kind==4||s->phase==OWN_ACTIVE)){
  /* Native pathmask bit 1 already guards SSSS PIN. Check also for the private
   * kind dispatched through APP, without changing the original global mask. */
  if(kind==4||(W(0xf4aecc)&2))
   {rc=csnd_cp_start_original(object,request,mode);csnd_cp_owner.last_native_rc=rc;}
 }
 __atomic_fetch_sub(&csnd_cp_owner.gate,1,__ATOMIC_RELEASE);return rc;
}
u32 csnd_cp_validate(void*object,const u8*request){
 u32 kind=request[2];
 if(r16(request)==2&&(kind==4||kind==17)){
  struct sound_slot*s=&csnd_cp_owner.slot[kind==4];
  if(__atomic_load_n(&s->phase,__ATOMIC_ACQUIRE)==OWN_ACTIVE&&s->quiesce){
   /* A queued Stop remains valid after native playback is disabled.
    * Keep original reserve bookkeeping and refusal semantics. */
   void*r=((void*(*)(void))0x5dfcf7)();
   /* This pinned native reserve returns only 0 or E006. */
   return ((u32(*)(void*,u32,u32,u32))0x5dfc2d)(r,2,0,1);
  }
 }
 return csnd_cp_validate_original(object,request);
}
