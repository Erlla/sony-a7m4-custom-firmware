#include <stdint.h>
struct info {
    uint32_t schema, source_rate, source_frames, pcm_frames;
    uint32_t encoded_bytes, padded_frames, source_peak, gain_denominator;
};
extern const uint8_t pad_anchor[];
extern int original(const uint8_t *, uint32_t, const void *, uint8_t *,
                    uint32_t, struct info *, uint32_t);

/* The existing converter zeroes all unused staging bytes. Keep short shutter
 * resources alive for 200 ms with digital silence so the next exposure can
 * reuse the native DMA lease. Slot 1 retains its normal resource length. */
int pad_shutter(const uint8_t *pcm, uint32_t count, const void *format,
                uint8_t *output, uint32_t capacity, struct info *info, uint32_t volume) {
    int result = original(pcm, count, format, output, capacity, info, volume);
    uintptr_t bias = (uintptr_t)pad_anchor - 0x9048e00u;
    volatile const uint32_t *slot = (const void *)(bias + 0x8ff77c8u + 712u);
    const uint32_t blocks = (4800u + 30u) / 31u;
    if (result == 0 && *slot == 0 && info->encoded_bytes <= 78u * 32u &&
        capacity >= blocks * 32u + 64u) {
        info->encoded_bytes = blocks * 32u;
        info->padded_frames = blocks * 31u - info->pcm_frames;
    }
    return result;
}
