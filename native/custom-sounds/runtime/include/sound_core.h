#ifndef SONY_CUSTOM_SOUND_CORE_H
#define SONY_CUSTOM_SOUND_CORE_H
#include <stddef.h>
#include <stdint.h>

/* Generic offline profile, not an assertion about the camera's audio ABI. */
#define SS_MAX_WAV_BYTES (1024u * 1024u)
#define SS_MAX_SECONDS 5u
#define SS_NAME_BYTES 256u
#define SS_SLOT_COUNT 2u
#define SS_SNAPSHOT_FIXED (32u + 304u * SS_SLOT_COUNT)

enum ss_status { SS_OK=0, SS_INVALID=1, SS_WAV_INVALID=2, SS_LIMIT=3,
    SS_STORAGE=4, SS_INCOMPATIBLE=5, SS_DISABLED=6, SS_CORRUPT=7 };
enum ss_slot_id { SS_ELECTRONIC=0, SS_FOCUS=1 };
enum ss_shutter { SS_SHUTTER_ELECTRONIC=0, SS_SHUTTER_MECHANICAL=1, SS_SHUTTER_EFCS=2 };
enum ss_focus { SS_AFS=0, SS_AFA=1, SS_AFC=2, SS_MF=3 };
enum ss_event { SS_ELECTRONIC_EXPOSURE=0, SS_FOCUS_CONFIRMED=1 };
enum ss_route { SS_SUPPRESS=0, SS_NATIVE_FOCUS=1, SS_PLAY_ELECTRONIC=2, SS_PLAY_FOCUS=3 };

typedef struct {
    uint32_t channels, sample_rate, bits_per_sample, block_align;
    uint32_t data_offset, data_bytes, frames;
} ss_format;

typedef struct {
    uint32_t enabled, custom, wav_bytes, name_bytes;
    uint8_t sha256[32];
    char name[SS_NAME_BYTES];
    const uint8_t *wav;
    ss_format format;
} ss_slot;

typedef struct { uint32_t generation; ss_slot slots[SS_SLOT_COUNT]; } ss_state;
typedef struct { uint32_t silent, audio_signals, shutter, focus; } ss_native;
typedef struct {
    uint32_t route;
    const uint8_t *pcm;
    ss_format format;
} ss_playback;

enum ss_selection { SS_SELECTION_EMPTY=0, SS_SELECTION_DEFAULT=1, SS_SELECTION_CUSTOM=2 };
/* Fixed 288-byte, pointer-free menu result on ARM32 and AArch64. This structure
 * is an in-process view, not the persisted snapshot and not an RPC encoding.
 * If transported, encode each u32 little-endian explicitly; UTF-8 bytes follow.
 * selection names contain at most 255 UTF-8 bytes and have zero-filled suffix.
 */
typedef struct {
    uint32_t schema, generation, slot, enabled, import_selectable;
    uint32_t can_select_default, selection, name_bytes;
    char name[SS_NAME_BYTES];
} ss_menu_view;

/* Caller owns WAV/snapshot bytes; keep them alive until slot replacement AND
 * completion of every outstanding playback borrowing that slot's old bytes.
 * ss_plan returns a borrowed buffer, not a DMA lease: a native asynchronous
 * adapter MUST pin a generation/reference or copy the PCM before replacement,
 * and release it only on verified completion/cancel. Serialize core calls;
 * that serialization alone does not prove asynchronous playback completion.
 * commit must atomically and durably persist ALL metadata and waveform bytes;
 * zero means success. A failed callback leaves state untouched. No callback
 * may mutate state, WAV bytes or call back into the core. Serialize all calls.
 */
typedef int (*ss_commit_fn)(void *context, const ss_state *candidate);

void ss_init(ss_state *state);
int ss_valid_name(const char *name, size_t length);
int ss_parse_wav(const uint8_t *wav, size_t length, ss_format *format);
/* Random-access offline verification only; reparses for each invocation. */
int ss_decode_q31(const uint8_t *wav, size_t length, const ss_format *format,
                  uint32_t frame, uint32_t channel, int32_t *sample);
/* Parse once, bounds-check the entire range, then linear interleaved Q31
 * decode. Output and WAV buffers must not overlap. No format resampling.
 * Input/output format and sample buffer stay untouched on validation failure.
 */
int ss_decode_frames_q31(const uint8_t *wav, size_t length, uint32_t first_frame,
                         uint32_t frames, int32_t *samples, size_t capacity_samples,
                         ss_format *format);
int ss_set_enabled(ss_state *state, uint32_t slot, uint32_t enabled,
                   uint32_t shutter, ss_commit_fn commit, void *context);
int ss_import(ss_state *state, uint32_t slot, const char *name, size_t name_bytes,
              const uint8_t *wav, size_t wav_bytes, ss_commit_fn commit, void *context);
int ss_focus_default(ss_state *state, ss_commit_fn commit, void *context);
int ss_native_shutter_changed(ss_state *state, uint32_t shutter,
                              ss_commit_fn commit, void *context);
int ss_menu_import_enabled(const ss_state *state, uint32_t slot);
/* Reads core-owned state; bounded metadata work, no WAV hash/parse or IO.
 * Non-null output is cleared before any validation failure. Check the status.
 * All mutations still go through transactional core APIs; no pointers in view.
 */
int ss_get_menu_view(const ss_state *state, uint32_t slot, ss_menu_view *view);
/* Constant-work event routing; state must be initialized and core-owned.
 * No parsing/hashing, IO, allocation, blocking or playback in this function.
 */
int ss_plan(const ss_state *state, const ss_native *native, uint32_t event,
             ss_playback *playback);
size_t ss_snapshot_size(const ss_state *state);
/* Output must be disjoint from state and all WAV/input buffers. */
int ss_snapshot_write(const ss_state *state, uint8_t *output, size_t capacity,
                      size_t *written);
/* Zero-copy restore: input must remain alive and be disjoint from state;
 * failed restore leaves state intact. See outstanding playback lifetime above.
 */
int ss_snapshot_restore(ss_state *state, const uint8_t *input, size_t length);
void ss_sha256(const uint8_t *bytes, size_t length, uint8_t digest[32]);
uint32_t ss_crc32(const uint8_t *bytes, size_t length);
#endif
