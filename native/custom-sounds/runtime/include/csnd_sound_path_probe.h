#ifndef CSND_SOUND_PATH_PROBE_H
#define CSND_SOUND_PATH_PROBE_H
#include <stdint.h>
/* X0: original media[0x150]; W1: card0/1; X2: caller-owned4096B scratch;
 * X3: output16B footer. No handle/iterator/pointer retained, no writes.
 * Footer[u32]: tag0x39504653("SFP9"), mappedPRIVATEstatus,mappedSONYstatus,
 * attemptedmask(bit0PRIVATE,bit1SONY). Unattemptedstatus=0xffffffff.
 * Uses original3724718 status mapping (raw2->mapped4). Return0 means two
 * queries issued; it does not mean either file exists or audio is usable. */
int csnd_probe_sound_paths(const uint8_t *media,uint32_t card,void *scratch4096,uint32_t footer[4]);
#endif
