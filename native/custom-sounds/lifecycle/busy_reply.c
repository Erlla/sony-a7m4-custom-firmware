/* Diagnostic PREPARE/BUSY payload only. The AP ignores these five words for
 * BUSY and retains them in its existing control mailbox for SSH readback. */
#include <stdint.h>
typedef uint32_t u32;
#define W(a) (*(volatile const u32 *)(a))
#define B(a) (*(volatile const uint8_t *)(a))

#define original_reply ((u32 (*)(const u32 *, u32 *))0x11f97du)

u32 sound_busy_reply(const u32 *request, u32 *reply) {
    u32 result = original_reply(request, reply);
    if (result != 2 || request[1] != 2 || reply[4] != 1)
        return result;
    reply[5] = 0xd1000000u | W(0x15648b8);
    reply[6] = W(0x1564840);
    reply[7] = W(0xfc6aec) | W(0xfc6af0) << 8 |
               W(0xfc6b20) << 16 | W(0xfc6b38) << 24;
    reply[8] = B(0xf57bac) | (u32)B(0xf57b4c) << 8 |
               (u32)B(0x121f194) << 16 | (u32)B(0x121f134) << 24;
    reply[9] = W(0x121f118) | W(0x121f130) << 16 |
               (u32)B(0x14b36a4) << 24;
    return result;
}
