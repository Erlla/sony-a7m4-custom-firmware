#ifndef M4_P4_LIBRARY_H
#define M4_P4_LIBRARY_H
#include <stdint.h>
#include "p4_json.h"
#define P4L_SLOTS 16u
#define P4L_RECORDS 64u
#define P4L_CANDIDATES 256u
#define P4L_PINS 2u
#define P4L_AUTO_SLOT 0xffffffffu
#define P4L_OFF_SLOT 16u
#define P4L_SELECTION_ABI 2u
typedef struct { int16_t delta[8]; uint16_t strength,reserved; } p6_settings;
int32_t p6_settings_valid(const p6_settings *);
void p6_settings_reset(p6_settings *);
#define P4L_INTERNAL_DIR "/setting/clut/looks"
#define P4L_CARD_DIR ":/PRIVATE/M4ROOT/GENERAL/LUT/"
enum { P4L_OK=0,P4L_NOOP=1,P4L_ARGUMENT=-1401,P4L_BUSY=-1402,
 P4L_IO=-1403,P4L_FORMAT=-1404,P4L_CHANGED=-1405,P4L_LIMIT=-1406,
 P4L_CONFLICT=-1407,P4L_DOWNGRADE=-1408,P4L_FULL=-1409,
 P4L_CANCELED=-1410,P4L_NOTFOUND=-1411,P4L_UNCERTAIN=-1412,
 P4L_UNSUPPORTED=-1413 };
enum {P4L_READ=0,P4L_EXCLUSIVE=1,P4L_REPLACE=2};
enum {P4L_IDLE,P4L_RECOVER,P4L_SCAN,P4L_REREAD,P4L_RECORD,
 P4L_VERIFY,P4L_INDEX,P4L_DONE,P4L_FAILED};
typedef struct {
 uint8_t uuid[16]; uint32_t revision;
 uint8_t content_sha256[32],file_sha256[32]; char name[64];
} p4l_identity;
typedef struct {p4l_identity id;uint32_t record,bytes;} p4l_entry;
typedef struct {char filename[64];p4l_identity id;uint32_t bytes;} p4l_candidate;
typedef struct {
 uint32_t generation,mask; p4l_entry slot[P4L_SLOTS];
 uint32_t pending_mask; p4l_entry pending[P4L_SLOTS];
 uint32_t pin_mask; p4l_entry pin[P4L_PINS];
 uint32_t committed_slot; p4l_identity committed;
 p6_settings settings[P4L_SLOTS];
} p4l_snapshot;
/* All callbacks return0 on success except list(1=entry,0=end).
 * read/write report actual counts; size is bounded by cap, EOF must be checked.
 * list enumerates every entry, including directories, without opening files.
 * card model snapshot must run the ORIGINAL FULL guard/getter/release chain;
 * no filesystem callback may run while that guard is held.
 * Internal open supports read, O_EXCL creation, and replacement ONLY of the
 * non-current index. sync must reach original fsync; dirsync must fsync dir.
 * IO errors are never fabricated as success. Native ports may block inside an
 * original call; cancel() prevents the next operation and always closes handles.
 */
typedef struct {
 void *opaque;
 int32_t (*snapshot)(void *,uint8_t row[112]);
 int32_t (*list)(void *,const char *directory,uint32_t ordinal,char name[64],uint32_t *regular);
 int32_t (*open)(void *,const char *,uint32_t mode,uint64_t *);
 int32_t (*read)(void *,uint64_t,void *,uint32_t,uint32_t *);
 int32_t (*write)(void *,uint64_t,const void *,uint32_t,uint32_t *);
 int32_t (*sync)(void *,uint64_t);
 int32_t (*close)(void *,uint64_t);
 int32_t (*remove)(void *,const char *);
 int32_t (*prepare)(void *); /* mkdir chain and verify local/internal backend */
 int32_t (*dirsync)(void *);
 int32_t (*canceled)(void *);
} p4l_ports;
typedef struct {
 p4l_ports io;uint32_t busy,cancel,stage,ready,candidate_count,scan_valid;
 int32_t error;uint32_t selected_index,index_valid[2];
 p4l_snapshot current,index[2];uint8_t card_row[112];
 p4l_candidate candidates[P4L_CANDIDATES];
 uint8_t json[P4_JSON_MAX_BYTES],parser[P4_JSON_WORKSPACE_BYTES];
 p4_json_result compiled;uint8_t wire[6144],scratch[4096];
} p4l_context;
/* Static or heap allocation belongs to the worker owner, never UI stack. */
uint32_t p4_library_context_bytes(void);
int32_t p4_library_init(p4l_context *,const p4l_ports *);
int32_t p4_library_recover(p4l_context *);
int32_t p4_library_scan(p4l_context *);
int32_t p4_library_import(p4l_context *,uint32_t candidate,uint32_t target_slot);
/* Fails BUSY while old slot identity is protected. Caller first leaves it at
 * an acknowledged safe boundary and changes protections. No effect commands. */
int32_t p4_library_publish_pending(p4l_context *,uint32_t slot);
int32_t p4_library_snapshot(p4l_context *,p4l_snapshot *);
/* Copies a stable candidate page under the same worker lock; max16 rows. */
int32_t p4_library_candidates(p4l_context *,uint32_t first,uint32_t count,
                            p4l_candidate *output,uint32_t *total);
/* After the owner has verified CP receipt + native completion, atomically
 * publish exact selection and pin0 in the same dual-index transaction. Off
 * uses P4L_OFF_SLOT and identity=NULL. Active identity must be the published
 * slot identity. Success clears preview pin1; no CP/GUI commands are sent.
 * Any failure preserves current RAM selection/pins; UNCERTAIN additionally
 * disables ready until recover selects a complete old or complete new index.
 */
int32_t p4_library_commit_selection(p4l_context *,uint32_t slot,
                                    const p4l_identity *identity);
int32_t p6_library_commit(p4l_context *,uint32_t slot,
                         const p4l_identity *,const p6_settings *);
/* Requires an acknowledged selection/preview outside the removed slots. */
int32_t p6_library_delete(p4l_context *,uint32_t slot_mask);
/* Preview lifetime only; NULL releases pin1. Pin0 always belongs to the
 * durable committed selection and cannot be cleared by this function. */
int32_t p4_library_set_preview(p4l_context *,const p4l_identity *identity);
/* Compatibility helper: active committed selection is implicit and immutable.
 * If active, ids[0] must equal it; ids[1] optionally sets preview. n=0 only
 * releases preview, never committed. If Off, a single id sets preview.
 * Prefer set_preview for new integration. Import persists preview protection
 * with the next index commit, and never applies CP/UI state itself. */
int32_t p4_library_protect(p4l_context *,const p4l_identity *,uint32_t count);
int32_t p4_library_load(p4l_context *,const p4l_identity *,p4_json_result *);
void p4_library_cancel(p4l_context *);
/* New worker request only, after prior request has returned. */
int32_t p4_library_resume(p4l_context *);
#endif
