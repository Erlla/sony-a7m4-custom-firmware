/* Scalar freestanding compiler lowering for fixed-size struct copies. */
#include <stdint.h>
#include <stddef.h>
void *memcpy(void *restrict dst,const void *restrict src,size_t bytes){
 uint8_t *d=dst;const uint8_t*s=src;
 for(size_t i=0;i<bytes;i++)d[i]=s[i];
 return dst;
}
