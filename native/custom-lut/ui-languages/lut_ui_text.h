#ifndef LUT_UI_TEXT_H
#define LUT_UI_TEXT_H
#include <stdint.h>
/* Only product-owned labels pass here. User names keep the original binder. */
int32_t lut_ui_bind_label(void *param, uint32_t param_bytes, const char *text,
                          uint32_t text_bytes, uint32_t fallback_resource);
#endif
