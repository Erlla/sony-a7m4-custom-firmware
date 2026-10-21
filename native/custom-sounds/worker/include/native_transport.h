#ifndef CSND_NATIVE_TRANSPORT_H
#define CSND_NATIVE_TRANSPORT_H
typedef unsigned char nt_u8;
typedef unsigned short nt_u16;
typedef unsigned int nt_u32;
typedef unsigned long long nt_u64;
typedef int nt_i32;
/* All methods except transfer_callback run on the single resource worker.
 * Contexts are persistent, zero-initialized, never stack temporaries.
 * Clock arguments are caller's monotonic modulo32 tick, NOT wall time.
 */
enum {NT_EMPTY=0,NT_READY=1,NT_PENDING=2,NT_REPLIED=3,NT_LOCAL_FAIL=4,NT_UNCERTAIN=5};
enum {NT_REASON_NONE=0,NT_REASON_ALLOC=1,NT_REASON_DIRTY=2,NT_REASON_POOL=3,
 NT_REASON_SEND=4,NT_REASON_RECEIVE=5,NT_REASON_TIMEOUT=6,NT_REASON_PROTOCOL=7,
 NT_REASON_FREE=8,NT_REASON_STATE=9,NT_REASON_RELEASE=10,NT_REASON_TOKEN=11};
typedef struct {
 nt_u32 state,endpoint,destination,command,token,deadline,reason,attempted;
 nt_u32 polls,receive_rc,actual_bytes,source,free_rc,late,session,operation;
 nt_u32 next_token,expected_source;
 nt_u8 reply[40];
} ns_rpc; /*112 bytes; remote status stays signed16 reply+2. */

nt_u32 csnd_rpc_open(nt_u64 base,ns_rpc *c);
/* Caller must open first. request40 remains caller-owned and is copied.
 * expected_source0 explicitly means capture-only (not a verified source).
 * Native send consumes only success; send error is conservative UNCERTAIN.
 */
nt_u32 csnd_rpc_start(nt_u64 base,ns_rpc*c,nt_u32 destination,
 const nt_u8 request40[40],nt_u32 deadline,nt_u32 expected_source);
/* Optional COPY payload 1..960B; native pool allocation remains wait0.
 * No 1KiB stack or persistent staging copy. Entire request is copied before
 * returning; source data may be retained by parent for its own ownership. */
nt_u32 csnd_rpc_start_parts(nt_u64 base,ns_rpc*c,nt_u32 destination,
 const nt_u8 request40[40],const nt_u8*data,nt_u32 bytes,nt_u32 deadline,nt_u32 expected_source);
/* Exactly one receive timeout0. Timeout/protocol error retains endpoint,
 * permits late matching ACK consumption, never resends or frees an owner. */
nt_u32 csnd_rpc_poll(nt_u64 base,ns_rpc*c,nt_u32 now_tick);
/* Only REPLIED (or clean never-sent READY) can finish. retain1 is for private
 * session queue; retain0 stat-checks and releases native dynamic ID. Parent
 * must first reconcile remote status/handle; this function owns no DMM data.
 */
nt_u32 csnd_rpc_finish(nt_u64 base,ns_rpc*c,nt_u32 retain_endpoint);
/* side0 AP61003C;side1 CP9061003C. cmd20 pool/23 owned handle.
 * Alloc wait field is0. These wrappers do not interpret/create ownership.
 */
nt_u32 csnd_dmm_start(nt_u64 base,ns_rpc*c,nt_u32 side,nt_u32 command,
 nt_u32 pool_or_handle,nt_u32 deadline);
/* Private NSCC session is its retained endpoint; monotonic16token never wraps.
 * Four args follow root/CP contract; no registration is assumed here. */
nt_u32 csnd_private_start(nt_u64 base,ns_rpc*c,nt_u32 operation,nt_u32 slot,
 const nt_u32 args[4],nt_u32 deadline);
nt_u32 csnd_private_copy(nt_u64 base,ns_rpc*c,nt_u32 slot,nt_u32 generation,
 nt_u32 revision,nt_u32 offset,const nt_u8*data,nt_u32 bytes,nt_u32 deadline);

typedef struct {
 nt_u32 state,callback_seen,submit_rc,deadline;
 nt_u32 source[2],destination[2];
 nt_u64 descriptor[5]; /* native40B:src*,dst*,len/mode,callback,arg */
 nt_u64 callback_arg0; /* opaque diagnostic only, never success status */
 nt_u32 late,submissions;
} ns_transfer; /*88B, immutable while pending/uncertain. */
nt_u32 csnd_transfer_start(nt_u64 base,ns_transfer*c,nt_u32 source_handle,
 nt_u32 source_offset,nt_u32 destination_handle,nt_u32 destination_offset,
 nt_u32 bytes,nt_u32 deadline);
nt_u32 csnd_transfer_poll(ns_transfer*c,nt_u32 now_tick);
/* Call only after parent has consumed completion and released all backing
 * references. No reset for pending/uncertain-without-callback. */
nt_u32 csnd_transfer_finish(ns_transfer*c);
void csnd_transfer_callback(nt_u64 opaque0,ns_transfer*c);
#endif
