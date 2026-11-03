#include <stdint.h>
typedef uint32_t u32;
#define W(a) (*(volatile const u32 *)(a))
#define B(a) (*(volatile const uint8_t *)(a))
#define RESERVE __attribute__((section(".reservation")))
extern u32 preparing(void);
extern u32 reserve_original(void *,u32);

RESERVE u32 reserve_guard(void *object,u32 kind) {
    if(kind!=4)return reserve_original(object,kind);
    volatile u32 *gate=(volatile u32 *)0x1564840;
    if(!((u32 (*)(volatile u32 *))0x11fe01)(gate))return 0;
    u32 result=preparing()?0:reserve_original(object,kind);
    ((void (*)(volatile u32 *))0x11fe3f)(gate);
    return result;
}

/* The native PIN cancellation retires its reservation and property callback.
 * A playback Stop on an empty player does not perform this operation. */
RESERVE void release_focus_reservation(void) {
    if(!preparing() || W(0x121f118)!=1 || W(0x121f130) ||
       W(0xfc6aec) || W(0xfc6af0) || W(0xfc6b20) || W(0xfc6b38) ||
       B(0x14b36a6)!=4)return;
    ((void (*)(void *))0x5df43f)((void *)0x106a614);
}
