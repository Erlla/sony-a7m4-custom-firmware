/* Native A03612 copies a Capture task without running A03142. Carry its
 * already frozen aspect with that copy, rather than reading today's menu.
 * Addresses belong to the pinned integrated CP and its existing aspect module.
 */
#include <stdint.h>

void *aspect_capture_clone_copy(void *destination, const void *source,
                                uint32_t length)
{
    void *result = ((void *(*)(void *, const void *, uint32_t))0x585fb8)
        (destination, source, length);
    if (length != 0x1e8) return result;

    uintptr_t task = (uintptr_t)destination - 0x20;
    uint32_t index = ((uint32_t (*)(uintptr_t))0x11b1f9)(task);
    if (index < 490) {
        uint32_t id = ((uint32_t (*)(uintptr_t))0x11b261)
            ((uintptr_t)source - 0x20);
        if (*(const uint32_t *)((uintptr_t)destination + 4) != 2) id = 0;
        ((uint8_t *)0x11d00c)[index] = (uint8_t)id;
        __asm__ volatile ("dmb ish" ::: "memory");
    }
    return result;
}
