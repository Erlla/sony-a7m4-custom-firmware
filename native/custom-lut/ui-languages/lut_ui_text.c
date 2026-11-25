#include "lut_ui_text.h"
#include "lut_name_text_v617.h"

/* Inline bytes keep this table position-independent without dynamic relocations. */
typedef struct { char source[40]; uint32_t bytes, resource; } label;
static const label labels[] = {
#include "labels.inc"
};

int32_t lut_ui_bind_label(void *param, uint32_t param_bytes, const char *text,
                          uint32_t text_bytes, uint32_t fallback_resource) {
    if (!param || ((uintptr_t)param & 7u) || param_bytes < LUT_TEXT_V617_PARAM_BYTES ||
        !text || !text_bytes || text_bytes > 129u)
        return LUT_TEXT_V617_EINVAL;
    for (uint32_t i = 0; i < sizeof(labels) / sizeof(labels[0]); i++) {
        if (labels[i].bytes != text_bytes) continue;
        uint32_t j = 0;
        while (j < text_bytes && text[j] == labels[i].source[j]) j++;
        if (j != text_bytes) continue;
        uint8_t *p = param;
        *(uint32_t *)(void *)(p + 0x30) = labels[i].resource;
        /* A native localized record needs no ${v1} argument. Clear stale args. */
        for (j = 0; j < 0x2e8; j++) p[0x58 + j] = 0;
        p[0x2c] = 1;
        return 0;
    }
    /* Percentages, page counts and empty text remain ordinary dynamic text. */
    return lut_text_v617_bind(param, param_bytes, text, text_bytes, fallback_resource);
}
