#ifndef CSND_AP_NATIVE_POLICY_H
#define CSND_AP_NATIVE_POLICY_H
#include "ap_runtime.h"

/* Exact source menu scalars. The schema is explicitly selected by a verified
 * model/profile owner; it is not inferred from two values that happen to agree.
 * AUTO requires the actual successful exposure mechanism, never a save event.
 */
typedef struct {
    uint32_t silent_raw, audio_raw, focus_raw, shutter_parameter, shutter_raw;
    uint32_t effective_known, effective_shutter;
} csnd_native_inputs;
int csnd_ap_normalize_native(const csnd_native_inputs *,ss_native *);
/* Worker-only original getter snapshot. Original getter locks still execute;
 * no claim that these may be called from an interrupt/audio event thread. */
int csnd_ap_read_native(uint32_t shutter_parameter,uint32_t effective_known,
                        uint32_t effective_shutter,ss_native *);
#endif
