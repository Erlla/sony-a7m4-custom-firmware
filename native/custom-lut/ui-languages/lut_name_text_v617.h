#ifndef LUT_NAME_TEXT_V617_H
#define LUT_NAME_TEXT_V617_H
#include <stdint.h>
#define LUT_NAME_V617_RECORD_BYTES 64u
#define LUT_NAME_V617_MAX_BYTES 63u
#define LUT_TEXT_V617_PARAM_BYTES 0x658u
#define LUT_TEXT_V617_RESOURCE 0x0200a0b3u
enum { LUT_TEXT_V617_OK=0, LUT_TEXT_V617_EINVAL=-1,
       LUT_TEXT_V617_ENOTERM=-2, LUT_TEXT_V617_EUTF8=-3,
       LUT_TEXT_V617_ENOSPACE=-4, LUT_TEXT_V617_EALIAS=-5 };
typedef struct { uint32_t bytes, codepoints, utf16_units; } lut_name_v617_info;
/* Original appFw 1856CFC uses kind1, 129-byte char buffer, BYTE length +88,
 * active +90; the complete block is five 94-byte slots and count +2E4.
 * These are UTF8 input bytes, never UTF16 bytes stuffed into a char argument. */
typedef struct { uint32_t resource; uint8_t arguments[0x2e8]; } lut_text_v617_tokens;
/* Caller supplies one original 64-byte catalog record captured under the
 * original model lock. No getter/PROP/mapping/filename reconstruction occurs.
 * Valid import records have NUL at or before byte63. No truncation is allowed.
 * On failure output and optional info remain unchanged. */
int32_t lut_name_v617_copy(const char *record, char *output,
                         uint32_t capacity, lut_name_v617_info *info);
/* text_bytes bounds the entire NUL-terminated input, at most129 bytes.
 * Strict modern UTF8 is accepted; malformed, overlong, surrogate and >10FFFF
 * input is rejected before any output mutation. Caller still owns widget,
 * model lock, MID/scene/epoch/request gate and lifetime. */
int32_t lut_text_v617_tokens_make(uint32_t resource, const char *text,
                                uint32_t text_bytes, lut_text_v617_tokens *out);
/* Only private native type2 PARAM: writes +2C active,+30 resource,+58 arguments.
 * Full native param capacity >=658 is mandatory; no stock style/PROP write.
 * The native rendering resource's encoding must select original UTF8 mode2;
 * this module neither sets font nor proves glyphs/paint on camera. */
int32_t lut_text_v617_bind(void *param, uint32_t param_bytes,
                         const char *text, uint32_t text_bytes, uint32_t resource);
const char *lut_text_v617_title(uint32_t *bytes_including_nul);
const char *lut_text_v617_strength_title(uint32_t *bytes_including_nul);
#endif
