/* Preserve the native quiescence contract; a completed Stop opcode is not
 * a pending Start. Actor/reservation/transition fields still own retirement. */
#include <stdint.h>
typedef uint32_t u32;
#define W(a) (*(volatile const u32 *)(a))
#define B(a) (*(volatile const uint8_t *)(a))

u32 sound_resource_busy(void) {
    static const u32 fields[] = {
        0xfc6aec, 0xfc6af0, 0xfc6b20, 0xfc6b38,
        0xf57bad, 0x14b36a5, 0x121f118, 0x121f130,
        0xf57b4d, 0x121f195, 0x121f135
    };
    u32 state=W(0x121f118), active=W(0x121f130), mask=0;
    __asm__ volatile("dmb sy" ::: "memory");
    for (u32 i=0; i<11; i++) {
        u32 address=fields[i];
        u32 value=(address&1) ? B(address&~1u) : W(address);
        if (i==4 && value==2) value=0;
        if (value) mask|=1u<<i;
    }
    __asm__ volatile("dmb sy" ::: "memory");
    if (W(0x121f118)!=state || W(0x121f130)!=active) mask|=0x80000000u;
    *(volatile u32 *)0x15648b8=mask;
    return mask;
}
