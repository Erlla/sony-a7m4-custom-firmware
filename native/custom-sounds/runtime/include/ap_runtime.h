#ifndef CSND_AP_RUNTIME_H
#define CSND_AP_RUNTIME_H
#include "sound_core.h"
#include <stdint.h>
#include <stddef.h>

/* AP64-only private ABI. No pointers are serialized or sent to ARM32 CP. */
#define CSND_AP_BUSY 8
#define CSND_AP_IO 9
#define CSND_AP_NOT_READY 10
#define CSND_AP_MAX_WAV_BYTES (512u * 1024u)
#define CSND_AP_MAX_SNAPSHOT (SS_SNAPSHOT_FIXED+SS_SLOT_COUNT*CSND_AP_MAX_WAV_BYTES)
typedef struct {
    uint32_t initialized, busy, status, rollback_failure;
    uint32_t pending[2], picker_slot, picker_ready;
    uint32_t loaded_from_backup, reserved;
    ss_state state;
    uint8_t *snapshot_owner;
    size_t snapshot_bytes;
    uint8_t *commit_owner;
    size_t commit_bytes;
    uint32_t native_silent_raw,native_audio_raw,native_focus_raw;
    uint32_t native_shutter_prm,native_shutter_raw,native_valid_mask;
    /* Monotonic request until a durable OFF commit. A native setter may run
     * while private IO is busy: never perform filesystem IO in that caller. */
    uint32_t mechanical_off_pending, mechanical_off_status;
} csnd_runtime;

extern csnd_runtime csnd_ap_state;
int csnd_ap_load_once(void);
int csnd_ap_enabled(uint32_t slot);
int csnd_ap_set_enabled(uint32_t slot,uint32_t enabled,uint32_t shutter);
int csnd_ap_native_shutter_changed(uint32_t shutter);
int csnd_ap_focus_default(void);
/* Worker-only; a copied waveform, never an SD pathname, is persisted. */
int csnd_ap_import_bytes(uint32_t slot,const char *name,size_t name_bytes,
                         const uint8_t *wav,size_t wav_bytes);
const ss_state *csnd_ap_get_state(void);
int csnd_ap_menu_view(uint32_t slot,ss_menu_view *out);
/* Bounded event observer: no WAV/PCM borrow, IO, allocation or durable drain.
 * Outputs are zero/SUPPRESS on failure. Worker must revalidate generation and
 * route; successive native getter values are not an atomic exposure tuple. */
int csnd_ap_playback_ticket(uint32_t event,uint32_t *generation,uint32_t *route);
/* Worker-owned PCM copy. dst/out/bytes must be valid, mutually disjoint and
 * disjoint from runtime/WAV/snapshot storage. Generation mismatch or a current
 * native gate suppresses custom output. Success copies only PCM: returned
 * format.data_offset is0, bytes=format.data_bytes. No borrow survives return.
 * Caller owns dst until native completion/cancel and must revalidate policy
 * before starting native playback. No filesystem IO or durable pending drain. */
int csnd_ap_copy_playback(uint32_t slot,uint32_t expected_generation,uint8_t *dst,
                         uint32_t capacity,ss_format *out,uint32_t *bytes);
/* Called AFTER the complete original setter/transaction destructor returns.
 * Original setter arguments/return are preserved by the source-bound wrapper.
 * Mechanical requests persistently disable the electronic toggle; other
 * native settings only refresh raw state for an explicit policy bridge.
 */
int csnd_ap_note_native_parameter(uint32_t parameter,uint32_t raw);
int csnd_ap_apply_pending_native(void);
int csnd_ap_mechanical_pending(void);
/* Import row must remain gray until the real native picker is registered. */
int csnd_ap_import_available(uint32_t slot);
/* Cold loader/read has no dependency on SD insertion or CP playback. */
#endif
