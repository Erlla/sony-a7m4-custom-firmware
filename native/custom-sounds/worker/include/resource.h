#ifndef CSND_NATIVE_SOUND_RESOURCE_H
#define CSND_NATIVE_SOUND_RESOURCE_H
#include <stdint.h>
int csnd_resource_tick(uint64_t base,uint32_t revision);
uint32_t csnd_resource_focus_mode(void);
int csnd_resource_dispatch(uint64_t base,uint32_t slot,uint32_t generation,uint32_t revision);
void csnd_resource_snapshot(uint32_t out[32]);
void csnd_resource_cp_snapshot(uint32_t out[16]);
#endif
