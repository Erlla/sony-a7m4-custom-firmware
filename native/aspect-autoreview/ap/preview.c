/* T14 source: ensure a real recording-guide widget and scoped capability.
 * No model pointer is retained. All read-side state is scalar, and no helper
 * in begin/finish/guide loads settings, locks models, logs, or reads files.
 * Creation registration alone may call the one-time canonical initializer.
 * The original GUI callback lifetime/order remains a required precondition.
 */
#include <stdint.h>
#include <stddef.h>

/* Canonical, completed publication only: ready bit4, native id0/custom4..9,
 * publication epoch bits31:5. Implementation must be an acquire read only.
 * Old sidecar.loaded/current are deliberately not consulted by this module. */
extern uint32_t aspect_ap_completed_selection_read(void);
/* Creation-time I/O boundary only; production initializer performs its own
 * atomic one-time claim, restores a local validated record, and publishes last.
 * Must not call any native model getter/lock. Never used by begin/finish/guide. */
extern void aspect_preview_initialize(void);

typedef struct {
    uintptr_t param;
    uint32_t generation, reserved;
    uint64_t memo;
} aspect_preview_owner;
aspect_preview_owner aspect_preview_owners[12];
#define LOAD(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define STORE(p, value) __atomic_store_n((p), (value), __ATOMIC_RELEASE)
#define HIDE UINT32_MAX

/* One weak CAS, no retry loop or lock. A contested/spurious failure hides this
 * pass. Every successful producer and owner mutation advances the same epoch;
 * a late same-owner/same-selection producer cannot publish a current memo. */
static uint32_t advance_pass(aspect_preview_owner *slot)
{
    uint32_t old = LOAD(&slot->generation);
    if (old >= 0x7ffffffeu) return 0;
    uint32_t next = old + 1;
    return __atomic_compare_exchange_n(&slot->generation, &old, next, 1,
                                       __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE) ? next : 0;
}

/* Creation/destruction are outside the rendering readers. Strong CAS retries
 * reservation failure, so a spurious LL/SC failure cannot permanently omit a
 * newly created owner. Contested generation values are reloaded and monotonic.
 * This is not a framework widget lifetime lock. */
static uint32_t advance_owner(aspect_preview_owner *slot)
{
    uint32_t old = LOAD(&slot->generation);
    for (;;) {
        if (old >= 0x7ffffffeu) return 0;
        uint32_t next = old + 1;
        if (__atomic_compare_exchange_n(&slot->generation, &old, next, 0,
                                         __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) return next;
    }
}

void aspect_preview_bind(unsigned index, uintptr_t param)
{
    if (index >= 12) return;
    aspect_preview_owner *slot = &aspect_preview_owners[index];
    STORE(&slot->param, 0);
    STORE(&slot->memo, 0);
    if (!advance_owner(slot)) return; /* no generation ABA until restart */
    STORE(&slot->param, param);
}

void aspect_preview_unbind(uintptr_t param)
{
    if (!param) return;
    for (unsigned i = 0; i < 12; ++i) {
        aspect_preview_owner *slot = &aspect_preview_owners[i];
        if (LOAD(&slot->param) != param) continue;
        STORE(&slot->param, 0);
        STORE(&slot->memo, 0);
        (void)advance_owner(slot);
    }
}

/* Source-bound descriptor rows: first presenter+270 row4, second+1E0 row3.
 * The native create_screen call has returned before these helpers execute.
 * Revoke the old slot even if the replacement descriptor is unavailable. */
static void register_owner(const uint8_t *presenter, uint32_t layer, unsigned family)
{
    if (layer > 5) return;
    uintptr_t param = 0;
    const uint8_t *table = *(const uint8_t *const *)(presenter + (family ? 0x1e0 : 0x270));
    unsigned row = family ? 3 : 4;
    if (table && *(const uint32_t *)(table + row * 16) == 0x3d)
        param = *(const uintptr_t *)(table + row * 16 + 8);
    if (param) aspect_preview_initialize();
    aspect_preview_bind(family * 6 + layer, param);
}
void aspect_preview_register_first(const uint8_t *presenter, uint32_t layer)
{
    register_owner(presenter, layer, 0);
}
void aspect_preview_register_second(const uint8_t *presenter, uint32_t layer)
{
    register_owner(presenter, layer, 1);
}

static aspect_preview_owner *find(uintptr_t param)
{
    if (!param) return 0;
    for (unsigned i = 0; i < 12; ++i)
        if (LOAD(&aspect_preview_owners[i].param) == param) return &aspect_preview_owners[i];
    return 0;
}

/* Called with this invocation's actual X1 and X3; short-circuit all model
 * reads unless an owned, active, completed custom request needs the bypass.
 * Return packs generation31/custom1/token32. It does not contain a pointer. */
uint64_t aspect_preview_producer_begin(const uint8_t *param, const uint8_t *model)
{
    if (!param || !model) return 0;
    aspect_preview_owner *slot = find((uintptr_t)param);
    if (!slot) return 0;
    STORE(&slot->memo, 0); /* incomplete producer cannot display an earlier pass */
    uint32_t generation = advance_pass(slot);
    if (!generation) return 0;
    uint32_t token = aspect_ap_completed_selection_read();
    uint32_t id = token & 15;
    uint32_t custom = (token & 16) && id >= 4 && id <= 9 &&
        *(const uint32_t *)(param + 0x40) <= 3 &&
        *(const uint32_t *)(model + 0x24d8) == 2 &&
        *(const uint32_t *)(model + 0x24b0) == 0;
    if (LOAD(&slot->param) != (uintptr_t)param || LOAD(&slot->generation) != generation)
        return 0;
    return ((uint64_t)generation << 33) | ((uint64_t)custom << 32) | token;
}

void aspect_preview_producer_finish(const uint8_t *param, uint64_t cookie)
{
    if (!cookie) return;
    aspect_preview_owner *slot = find((uintptr_t)param);
    if (!slot || LOAD(&slot->generation) != (uint32_t)(cookie >> 33) ||
        LOAD(&slot->param) != (uintptr_t)param) return;
    STORE(&slot->memo, cookie);
}

/* 0 -> original update, 4..9 -> custom fit, UINT32_MAX -> hide this pass.
 * Only the current widget is dereferenced; no saved model/heap pointer exists.
 * Atomic scalar validation does not create a native widget lifetime barrier. */
uint32_t aspect_preview_guide_read(const uint8_t *widget)
{
    if (!widget) return 0;
    uintptr_t param = (uintptr_t)(widget + 0x1d8);
    aspect_preview_owner *slot = find(param);
    if (!slot) return 0;
    uint32_t generation = LOAD(&slot->generation);
    uint64_t memo = LOAD(&slot->memo);
    uint32_t token = aspect_ap_completed_selection_read();
    if (!memo || (memo >> 33) != generation || (uint32_t)memo != token ||
        LOAD(&slot->generation) != generation || LOAD(&slot->param) != param) return HIDE;
    if (!((memo >> 32) & 1)) return 0;
    uint32_t id = token & 15;
    if (!(token & 16) || id < 4 || id > 9 || !widget[0x204] || !widget[0x21c] ||
        *(const uint32_t *)(widget + 0x218) > 3 ||
        *(const int32_t *)(widget + 0x210) <= 0 ||
        *(const int32_t *)(widget + 0x214) <= 0) return HIDE;
    return id;
}

/* The native policy computes common active AFTER parameter production. Its
 * device-capability gate is separate from exposure/DISP/output-route gates.
 * Override only that gate for the named guide row in a still custom selection.
 * No native getter, I/O, lock, retained presenter or mutation is introduced.
 */
uint32_t aspect_preview_custom_capability(const uint8_t *presenter,
                                         uint32_t row, uint32_t family)
{
    if (!presenter || family > 1 || row != (family ? 3u : 4u)) return 0;
    uint32_t token = aspect_ap_completed_selection_read(), id = token & 15u;
    if (!(token & 16u) || id < 4 || id > 9) return 0;
    const uint8_t *model = presenter + (family ? 0x15f8 : 0x17c8);
    return *(const uint32_t *)(model + 0x24d8) == 2 &&
           *(const uint32_t *)(model + 0x24b0) == 0;
}

/* Every table entry is a source-bound fixed allocation delta in 128B units.
 * Native callbacks start at cursor0 and align each item to128. Their capacity
 * assertion is strict, so require the conservative aligned total < capacity.
 * Unknown count/context leaves input unchanged. In a known guide layout,
 * unknown types or insufficient capacity select the parameter-only fallback.
 * No model getters, allocator, callbacks, or settings I/O are used here. */
#include "native_widget_allocation.h"
void aspect_preview_prepare_create(const uint8_t *view, const uint8_t *layout,
                                   uint32_t count, uint8_t *flags, uint32_t family)
{
    if (!view || !layout || !flags || family > 1 ||
        count != (family ? 442u : 585u)) return;
    uint32_t row = family ? 3u : 4u;
    if (*(const uint32_t *)(layout + row * 0x34u) != 0x3du) return;
    /* Capability policy also runs before creation and may already clear this
     * flag. Always check capacity, including an incoming enabled guide. */
    flags[row] = 1;
    uint32_t capacity = *(const uint32_t *)(view + 0x3ea0u), total = 0;
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t type = *(const uint32_t *)(layout + i * 0x34u);
        if (type >= sizeof(aspect_native_alloc_units) / sizeof(aspect_native_alloc_units[0])) return;
        uint32_t alternate = i != row && flags[i] != 0;
        uint32_t bytes = (uint32_t)aspect_native_alloc_units[type][alternate] * 128u;
        if (!bytes || bytes >= capacity - total) return;
        total += bytes;
    }
    flags[row] = 0;
}
