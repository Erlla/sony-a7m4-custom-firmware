#include "native_transport.h"
#define F(o,t) ((t)(base+(o)))
#define LD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define ST(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#ifndef NS_ALLOW_NATIVE_SYNC_SUBMIT
#define NS_ALLOW_NATIVE_SYNC_SUBMIT 0
#endif
static nt_u32 rd16(const nt_u8*p){return p[0]|(nt_u32)p[1]<<8;}
static nt_u32 rd32(const nt_u8*p){return rd16(p)|(rd16(p+2)<<16);}
static void wr16(nt_u8*p,nt_u32 v){p[0]=(nt_u8)v;p[1]=(nt_u8)(v>>8);}
static void wr32(nt_u8*p,nt_u32 v){wr16(p,v);wr16(p+2,v>>16);}
static void zero(void*p,nt_u32 n){nt_u8*b=p;for(nt_u32 i=0;i<n;i++)b[i]=0;}
static nt_u32 state(ns_rpc*c,nt_u32 s,nt_u32 reason){c->reason=reason;ST(c->state,s);return s;}
static nt_u32 empty_queue(nt_u64 base,nt_u32 ep){
 nt_u32 s[4]={0,0,0,0};nt_i32 rc=F(0x17158b0,nt_i32(*)(nt_u32,nt_u32*))(ep,s);
 return !rc&&!s[0]&&!s[1]&&!s[3];
}
nt_u32 csnd_rpc_open(nt_u64 base,ns_rpc*c){
 if(!c)return NT_LOCAL_FAIL;
 if(c->state!=NT_EMPTY)return c->state;
 nt_u32 sub=F(0x1717bb0,nt_u32(*)(void))()&0xffffu,ep=0;
 nt_i32 rc=F(0x17164f0,nt_i32(*)(nt_u32,nt_u32,nt_u32*))(0x2a,sub,&ep);
 c->endpoint=ep;c->receive_rc=(nt_u32)rc;
 if(rc||!ep||!(ep&0x80000000u)||(ep&0x8000u)||!(ep&0x7fffu)||((ep>>16)&0xfffu)!=(sub&0xfffu))
  return state(c,ep?NT_UNCERTAIN:NT_LOCAL_FAIL,NT_REASON_ALLOC);
 if(!empty_queue(base,ep))return state(c,NT_UNCERTAIN,NT_REASON_DIRTY);
 return state(c,NT_READY,0);
}
nt_u32 csnd_rpc_start_parts(nt_u64 base,ns_rpc*c,nt_u32 dest,const nt_u8 req[40],const nt_u8*data,nt_u32 bytes,nt_u32 deadline,nt_u32 expected_source){
 if(!c||!req)return NT_LOCAL_FAIL;
 if(c->state!=NT_READY)return c->state;
 nt_u32 cmd=rd16(req),token=rd16(req+20);void*wire=0;
 if(!c->endpoint||!dest||(cmd!=0x20&&cmd!=0x23&&cmd!=0x7e)||rd16(req+2)||!token||bytes>960||(bytes&&!data)||
    (bytes&&(cmd!=0x7e||rd32(req+4)!=6||rd32(req+36)!=bytes)))
  return state(c,NT_LOCAL_FAIL,NT_REASON_PROTOCOL);
 c->destination=dest;c->command=cmd|0x8000u;c->token=token;c->deadline=deadline;
 c->expected_source=expected_source;c->session=cmd==0x7e?rd32(req+8):0;c->operation=cmd==0x7e?rd32(req+4):0;
 c->polls=0;c->late=0;c->attempted=0;c->actual_bytes=0;c->source=0;c->free_rc=0;zero(c->reply,40);
 nt_i32 rc=F(0x1718130,nt_i32(*)(nt_u32,void**,nt_u32,nt_u32))(dest,&wire,40+bytes,0);c->receive_rc=(nt_u32)rc;
 if(rc||!wire){
  if(wire)c->free_rc=(nt_u32)F(0x1718450,nt_i32(*)(nt_u32,void*))(dest,wire);
  return state(c,c->free_rc?NT_UNCERTAIN:NT_LOCAL_FAIL,NT_REASON_POOL);
 }
 for(nt_u32 i=0;i<40;i++)((nt_u8*)wire)[i]=req[i];
 for(nt_u32 i=0;i<bytes;i++)((nt_u8*)wire)[40+i]=data[i];
 F(0x17153f0,void(*)(void*,nt_u32))(wire,c->endpoint);
 c->attempted=1;ST(c->state,NT_PENDING);
 rc=F(0x17169c0,nt_i32(*)(nt_u32,void*))(dest,wire);c->receive_rc=(nt_u32)rc;
 if(rc){
  c->free_rc=(nt_u32)F(0x1718450,nt_i32(*)(nt_u32,void*))(dest,wire);
  return state(c,NT_UNCERTAIN,NT_REASON_SEND);
 }
 return state(c,NT_PENDING,0);
}
nt_u32 csnd_rpc_start(nt_u64 base,ns_rpc*c,nt_u32 dest,const nt_u8 req[40],nt_u32 deadline,nt_u32 source){
 return csnd_rpc_start_parts(base,c,dest,req,0,0,deadline,source);
}
nt_u32 csnd_rpc_poll(nt_u64 base,ns_rpc*c,nt_u32 now){
 if(!c)return NT_LOCAL_FAIL;
 if((c->state!=NT_PENDING&&c->state!=NT_UNCERTAIN)||!c->attempted)return c->state;
 void*wire=0;c->polls++;
 nt_i32 rc=F(0x1716820,nt_i32(*)(nt_u32,void**,nt_u32))(c->endpoint,&wire,0);c->receive_rc=(nt_u32)rc;
 if(rc){
  if(rc!=-1022)return state(c,NT_UNCERTAIN,NT_REASON_RECEIVE);
  if((nt_i32)(now-c->deadline)>=0){c->late=1;return state(c,NT_UNCERTAIN,NT_REASON_TIMEOUT);}
  return c->state;
 }
 if(!wire)return state(c,NT_UNCERTAIN,NT_REASON_PROTOCOL);
 c->actual_bytes=F(0x17165f0,nt_u32(*)(void*))(wire);
 c->source=F(0x1717740,nt_u32(*)(void*))(wire);
 nt_u32 ok=0;
 if(c->actual_bytes==40){
  for(nt_u32 i=0;i<40;i++)c->reply[i]=((nt_u8*)wire)[i];
  ok=rd16(c->reply)==c->command&&rd16(c->reply+6)==c->token;
  if(c->expected_source&&c->source!=c->expected_source)ok=0;
  if(c->command==0x807e&&(rd16(c->reply+4)!=24||rd32(c->reply+8)!=c->session||rd32(c->reply+12)!=c->operation))ok=0;
 }
 c->free_rc=(nt_u32)F(0x1718450,nt_i32(*)(nt_u32,void*))(c->endpoint,wire);
 if(c->free_rc)return state(c,NT_UNCERTAIN,NT_REASON_FREE);
 if(!ok)return state(c,NT_UNCERTAIN,NT_REASON_PROTOCOL);
 if((nt_i32)(now-c->deadline)>=0)c->late=1;
 /* REPLIED means structurally matching ACK, not successful remote mutation.
  * Parent must read signed16 status and DMM/private reply payload. */
 return state(c,NT_REPLIED,0);
}
nt_u32 csnd_rpc_finish(nt_u64 base,ns_rpc*c,nt_u32 retain){
 if(!c)return NT_LOCAL_FAIL;
 if(c->state!=NT_REPLIED&&c->state!=NT_READY&&!(c->state==NT_LOCAL_FAIL&&!c->attempted))return c->state;
 if(c->endpoint&&!empty_queue(base,c->endpoint))return state(c,NT_UNCERTAIN,NT_REASON_DIRTY);
 if(retain&&c->endpoint){c->attempted=0;return state(c,NT_READY,0);}
 if(c->endpoint){
  nt_i32 rc=F(0x17164f0,nt_i32(*)(nt_u32,nt_u32,nt_u64))(0x4a,0,c->endpoint);
  c->receive_rc=(nt_u32)rc;if(rc)return state(c,NT_UNCERTAIN,NT_REASON_RELEASE);
 }
 zero(c,sizeof(*c));return NT_EMPTY;
}
nt_u32 csnd_dmm_start(nt_u64 base,ns_rpc*c,nt_u32 side,nt_u32 cmd,nt_u32 value,nt_u32 deadline){
 if(!c||side>1||(cmd!=0x20&&cmd!=0x23)||!value)return NT_LOCAL_FAIL;
 if(c->state==NT_EMPTY)csnd_rpc_open(base,c);
 if(c->state!=NT_READY)return c->state;
 nt_u8 req[40]={0};wr16(req,cmd);wr16(req+20,c->endpoint);
 if(cmd==0x20){wr32(req+4,value);wr32(req+12,0);wr16(req+22,1);}
 else{wr32(req+8,value);wr16(req+22,2);}
 return csnd_rpc_start(base,c,side?0x9061003cu:0x61003cu,req,deadline,0);
}
static nt_u32 private_parts(nt_u64 base,ns_rpc*c,nt_u32 op,nt_u32 slot,const nt_u32 args[4],const nt_u8*data,nt_u32 bytes,nt_u32 deadline){
 if(!c||!args||op<1||op>6||slot>1||(op==6&&(!bytes||bytes>960||!data||args[3]!=bytes))||(op!=6&&bytes))return NT_LOCAL_FAIL;
 if(c->state==NT_EMPTY)csnd_rpc_open(base,c);
 if(c->state!=NT_READY)return c->state;
 if(c->next_token>=0xffffu)return state(c,NT_LOCAL_FAIL,NT_REASON_TOKEN);
 c->next_token++;
 nt_u8 req[40]={0};wr16(req,0x7e);wr32(req+4,op);wr32(req+8,c->endpoint);wr32(req+12,0x4e535343u);wr32(req+16,c->endpoint);
 wr16(req+20,c->next_token);wr16(req+22,slot);for(nt_u32 i=0;i<4;i++)wr32(req+24+i*4,args[i]);
 return csnd_rpc_start_parts(base,c,0x9061003cu,req,data,bytes,deadline,0);
}
nt_u32 csnd_private_start(nt_u64 base,ns_rpc*c,nt_u32 op,nt_u32 slot,const nt_u32 args[4],nt_u32 deadline){
 return private_parts(base,c,op,slot,args,0,0,deadline);
}
nt_u32 csnd_private_copy(nt_u64 base,ns_rpc*c,nt_u32 slot,nt_u32 gen,nt_u32 rev,nt_u32 off,const nt_u8*data,nt_u32 bytes,nt_u32 deadline){
 nt_u32 args[4]={gen,rev,off,bytes};
 return private_parts(base,c,6,slot,args,data,bytes,deadline);
}

void csnd_transfer_callback(nt_u64 opaque0,ns_transfer*c){
 if(!c)return;
 /* One persistent native submission owns this callback argument. x0 is
  * intentionally not interpreted: original callback ignores it as well. */
 c->callback_arg0=opaque0;ST(c->callback_seen,1);
}
nt_u32 csnd_transfer_start(nt_u64 base,ns_transfer*c,nt_u32 sh,nt_u32 so,nt_u32 dh,nt_u32 d_o,nt_u32 n,nt_u32 deadline){
 /* Original1715040 allocates with wait1 then synchronous service0746.
  * Disabled until that submission path has its own bounded implementation.
  * Explicit proof-fixture define is not permission to deploy this path. */
 if(!NS_ALLOW_NATIVE_SYNC_SUBMIT){(void)base;(void)c;(void)sh;(void)so;(void)dh;(void)d_o;(void)n;(void)deadline;return NT_LOCAL_FAIL;}
 if(!c)return NT_LOCAL_FAIL;
 if(c->state!=NT_EMPTY)return c->state;
 if(!sh||!dh||!n||so+n<so||d_o+n<d_o)return NT_LOCAL_FAIL;
 c->source[0]=sh;c->source[1]=so;c->destination[0]=dh;c->destination[1]=d_o;
 c->descriptor[0]=(nt_u64)c->source;c->descriptor[1]=(nt_u64)c->destination;
 c->descriptor[2]=(1ull<<32)|n;c->descriptor[3]=(nt_u64)&csnd_transfer_callback;c->descriptor[4]=(nt_u64)c;
 c->deadline=deadline;c->late=0;c->submissions++;ST(c->callback_seen,0);ST(c->state,NT_PENDING);
 nt_i32 rc=F(0x1715040,nt_i32(*)(const void*))(c->descriptor);c->submit_rc=(nt_u32)rc;
 if(rc)ST(c->state,NT_UNCERTAIN);
 return c->state;
}
nt_u32 csnd_transfer_poll(ns_transfer*c,nt_u32 now){
 if(!c)return NT_LOCAL_FAIL;
 if(c->state!=NT_PENDING&&c->state!=NT_UNCERTAIN)return c->state;
 if((nt_i32)(now-c->deadline)>=0)c->late=1;
 if(LD(c->callback_seen)){ST(c->state,NT_REPLIED);return NT_REPLIED;}
 if(c->late)ST(c->state,NT_UNCERTAIN);
 return c->state;
}
nt_u32 csnd_transfer_finish(ns_transfer*c){
 if(!c)return NT_LOCAL_FAIL;
 if(c->state!=NT_REPLIED||!LD(c->callback_seen))return c->state;
 zero(c,sizeof(*c));return NT_EMPTY;
}
_Static_assert(sizeof(ns_rpc)==112,"RPC context ABI");
_Static_assert(sizeof(ns_transfer)==88,"transfer context ABI");
