/* Read-only posthoc BIND diagnostic. No owner/session/lease mutation. */
typedef unsigned int u32; typedef unsigned char u8;
#define OWNER ((volatile u32*)0x1564840u)
extern u32 csnd_driver_owner_reply(const u8*,u8*);
#define old_reply csnd_driver_owner_reply
#define original_exists ((u32(*)(u32,u32))0xba667bu)
#define native_extent ((u32(*)(const void*,void*,void*))0xafd00bu)
u32 csnd_bind_diag_reply(const u32*q,u32*r){
 if(q[1]!=5||(q[6]!=3&&q[6]!=4))return old_reply((const u8*)q,(u8*)r);
 /* Frozen QUERY validates/consumes receipt; INVALID/BUSY stay authoritative.
  * This is read-only original transact, including foreign/empty session. */
 u32 rc0=old_reply((const u8*)q,(u8*)r);
 if(rc0!=2||r[4]==2||r[4]==1||r[4]>7)return rc0;
 volatile u32*o=OWNER;u32 phase=2;
 for(u32 i=5;i<10;i++)r[i]=0;
 u32 zero=0;
 if(!__atomic_compare_exchange_n(o,&zero,0x80000000u,1,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED)){phase=1;goto done;}
 if(q[6]==3){
  if(q[7]||q[8]||q[9])goto unlock;
  r[5]=0x10001;r[6]=o[1];r[7]=o[12];r[8]=o[26];
  r[9]=original_exists(0x106a620,17);phase=0;
 }else{
  if(q[7]>5||q[9])goto unlock;
  volatile u32 a[13],b[10];for(u32 i=0;i<13;i++)a[i]=0;for(u32 i=0;i<10;i++)b[i]=0;
  a[3]=0x2a;a[5]=q[8];a[8]=1;
  r[5]=q[8];r[6]=1;
  if(q[8]&&q[8]!=~0u){
   u32 rc=native_extent((const void*)a,(void*)b,(void*)(b+6));r[6]=rc!=2?2:(b[0]&0xffff)!=0x802a?3:b[0]>>16?4:b[3]!=q[8]?5:b[8]!=51200?6:0;
   if(rc==2&&(b[0]&0xffff)==0x802a){r[7]=b[6];r[8]=b[7];r[9]=b[8];}
  }phase=0;
 }
unlock:__atomic_store_n(o,0,__ATOMIC_RELEASE);
done:r[4]=phase;return 2;
}
