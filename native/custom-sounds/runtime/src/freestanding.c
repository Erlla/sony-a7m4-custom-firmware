#include <stddef.h>
#include "sound_core.h"
void *memcpy(void *dst, const void *src, size_t n) {
    unsigned char *d=dst; const unsigned char *s=src; size_t i;
    for(i=0;i<n;i++) d[i]=s[i];
    return dst;
}
void *memset(void *dst, int value, size_t n) {
    unsigned char *d=dst; size_t i; for(i=0;i<n;i++) d[i]=(unsigned char)value; return dst;
}
int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *p=a,*q=b; size_t i;
    for(i=0;i<n;i++) if(p[i]!=q[i]) return (int)p[i]-(int)q[i];
    return 0;
}
size_t ss_sizeof_state(void) { return sizeof(ss_state); }
size_t ss_sizeof_playback(void) { return sizeof(ss_playback); }
/* ARM EABI division support without linking a platform runtime. */
uint64_t __aeabi_uidivmod(uint32_t numerator, uint32_t denominator) {
    uint64_t remainder=0; uint32_t quotient=0; int bit;
    if (!denominator) return 0;
    for(bit=31;bit>=0;bit--) {
        remainder=(remainder<<1)|((numerator>>(unsigned)bit)&1u);
        if(remainder>=denominator) { remainder-=denominator; quotient|=1u<<(unsigned)bit; }
    }
    return (remainder<<32)|quotient;
}
uint32_t __aeabi_uidiv(uint32_t numerator, uint32_t denominator) {
    return (uint32_t)__aeabi_uidivmod(numerator,denominator);
}
