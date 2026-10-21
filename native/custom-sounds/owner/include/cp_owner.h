#ifndef CSND_CP_OWNER_H
#define CSND_CP_OWNER_H
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
enum { OWN_OK=0, OWN_BUSY=1, OWN_INVALID=2, OWN_NOTBOUND=3,
       OWN_STALE=4, OWN_PREPARED=5, OWN_ACTIVE=6, OWN_OFF=7 };
enum { OWN_BIND=1, OWN_PREPARE=2, OWN_COMMIT=3, OWN_POLICY=4, OWN_QUERY=5, OWN_COPY=6 };
struct sound_slot {
 u32 handle[3],phys_lo,phys_hi,length,generation,revision;
 u32 pending_generation,pending_revision,phase,quiesce;
 u32 received,crc;
};
struct sound_owner {
 volatile u32 gate; /* high bit: transaction; low bits: native final starts */
 u32 session;
 struct sound_slot slot[2];
 u32 last_busy;
 u8 receipt_header[40];
 u32 receipt_valid,receipt_result;
 u32 calls[2],last_kind,last_native_rc;
};
extern struct sound_owner csnd_cp_owner;
u32 csnd_cp_owner_reply(const u8*,u8*);
u32 csnd_cp_lookup(void*,u32,void*,u32);
u32 csnd_cp_exists(void*,u32);
u32 csnd_cp_start(void*,const u8*,u32);
void csnd_cp_receive_capture(u32,const u8*,u32);
#endif
