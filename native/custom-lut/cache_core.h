#ifndef P6_CACHE_CORE_H
#define P6_CACHE_CORE_H
#include <stdint.h>

/* Atomic reclamation core, shared by the protocol and native CP binding.
 * Waiting, Off, and native settings acknowledgements are not lease releases.
 */
#define P6C_BANKS 63u
#define P6C_READY 1u
#define P6C_MAX_REFS 0x7ffffffeu
enum { P6C_OK=0, P6C_BUSY=-1, P6C_STALE=-2, P6C_ARGUMENT=-3 };
typedef struct { uint64_t generation; uint32_t state; uint32_t reserved; } p6c_bank;
typedef struct { p6c_bank bank[P6C_BANKS]; uint32_t cursor; } p6c_cache;
typedef struct { uint64_t generation; uint32_t slot; uint32_t held; } p6c_lease;

void p6c_init(p6c_cache *);
/* One serialized writer. Success exclusively owns the selected payload until
 * publish/abort. The old payload may be changed only between those calls.
 */
int p6c_reserve(p6c_cache *, p6c_lease *);
int p6c_publish(p6c_cache *, p6c_lease *);
int p6c_abort(p6c_cache *, p6c_lease *);
/* Exact acquisition can fail when the caller has only an old, unowned handle.
 * Acquisition from a still-held parent lease cannot race reclamation.
 */
int p6c_acquire(p6c_cache *, uint32_t slot, uint64_t generation, p6c_lease *);
/* Native source fields own a reference. Pin before reading their payload,
 * then re-read the source field to validate the snapshot. */
int p6c_acquire_current(p6c_cache *, uint32_t slot, p6c_lease *);
/* Transfer an already-owned reference to/from a native atomic slot field.
 * This is not an acquisition by an unowned numeric handle. */
void p6c_drop_owned(p6c_cache *, uint32_t slot);
int p6c_clone(p6c_cache *, const p6c_lease *, p6c_lease *);
int p6c_release(p6c_cache *, p6c_lease *);
uint32_t p6c_refs(const p6c_cache *, uint32_t slot);
#endif
