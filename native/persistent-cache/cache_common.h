#ifndef M4_PERSISTENT_CACHE_COMMON_H
#define M4_PERSISTENT_CACHE_COMMON_H
#include <stdint.h>
#include <stddef.h>
static inline void cache_copy(void*d,const void*s,uint32_t n){uint8_t*a=d;const uint8_t*b=s;while(n--)*a++=*b++;}
static inline int cache_equal(const void*a,const void*b,uint32_t n){const uint8_t*p=a,*q=b;while(n--)if(*p++!=*q++)return 0;return 1;}
static inline uint32_t cache_crc_update(uint32_t v,const void*p,uint32_t n){const uint8_t*b=p;while(n--){v^=*b++;for(unsigned k=0;k<8;k++)v=(v>>1)^(0xedb88320u&(0u-(v&1u)));}return v;}
static inline uint32_t cache_crc_pair(const void*h,uint32_t hn,const void*p,uint32_t pn){return ~cache_crc_update(cache_crc_update(~0u,h,hn),p,pn);}
#endif
