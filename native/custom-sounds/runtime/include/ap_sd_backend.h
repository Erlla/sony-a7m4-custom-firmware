#ifndef CSND_AP_SD_BACKEND_H
#define CSND_AP_SD_BACKEND_H
#include "ap_runtime.h"
#define CSND_PICKER_CAPACITY 60u
typedef struct {
    uint32_t kind, name_bytes;
    uint64_t file_bytes;
    char name[SS_NAME_BYTES];
} csnd_picker_entry;
typedef struct {
    uint32_t schema, slot, card, count;
    uint32_t status, has_default, reserved[2];
    csnd_picker_entry entries[CSND_PICKER_CAPACITY];
} csnd_picker_list;
/* media snapshot is the original two-card array, stride0x70, borrowed only
 * for this worker call. No pointers/file handles survive the call.
 */
int csnd_ap_scan_wavs(const uint8_t *media,uint32_t card,uint32_t slot,csnd_picker_list *out);
int csnd_ap_import_sd(const uint8_t *media,uint32_t card,uint32_t slot,const char *name,size_t name_bytes);
#endif
