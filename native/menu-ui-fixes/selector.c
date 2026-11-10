/* Stock type1C selection notification (020F0001) reports an absolute row,
 * including row zero (Off). 03010000 is touch-begin and has no row payload.
 * Keep preview/commit/cancel owned by the existing GUI transaction code. */
#include "abi.h"

extern p4_gui_context *existing_context __attribute__((visibility("hidden")));
extern void existing_queue(uint32_t action);
extern void existing_refresh(void);
extern int32_t existing_dispatch(uint64_t c, uint64_t message, uint32_t event);

int32_t lut_selector_touch_dispatch(uint64_t c, uint64_t message, uint32_t event) {
    lut_stock_runtime *g = &lut_widget_runtime_state;
    p4_gui_context *q = existing_context;
    if (g->scene != 0xd9 || event != 0x20f0001u || !q || q->mode != G_NORMAL)
        return existing_dispatch(c, message, event);
    if (!message) return 0;
    const uint32_t *m = (const uint32_t *)(uintptr_t)message;
    if (m[0] != 4 || m[2] != event || m[3] != 0 || m[4] != 9 || m[5] != 0xd9 || m[6] > 16)
        return 0;
    if (g->transition || !q->timer.active) return 1;
    if ((q->token || q->next_action) &&
        !(q->action == A_PREVIEW && !q->commit_after_preview)) {
        existing_refresh();
        return 1;
    }
    uint32_t slot = m[6] ? m[6] - 1 : P4R_OFF;
    q->perf_active = 0;
    if (slot != q->focus) {
        q->focus = g->state.focused_slot = slot;
        q->commit_after_preview = 0;
        q->reserved &= ~(GUI_IDENTITY_RETRIED | GUI_IDENTITY_REFRESH);
        existing_queue(A_PREVIEW);
    }
    existing_refresh();
    return 1;
}
