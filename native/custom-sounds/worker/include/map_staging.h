#ifndef CSND_NATIVE_STAGING_MAP_H
#define CSND_NATIVE_STAGING_MAP_H
#include <stdint.h>
/* No lease allocation occurs here. The resource manager must first own each
 * complete native 51200-byte unit covering [physical,physical+capacity).
 * Mapping never authorizes CP sample writes or active-owner retirement. */
typedef struct {
    uint64_t cpu, mapping;
    uint32_t bytes, fd, active, uncertain;
} csnd_staging_map;
int csnd_staging_map_open(uint64_t base,uint64_t physical,uint32_t capacity,
                           csnd_staging_map *out);
int csnd_staging_map_close(uint64_t base,csnd_staging_map *out);
#endif
