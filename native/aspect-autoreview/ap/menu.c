#include <stdint.h>
#include <stddef.h>
extern uint8_t aspect_option_table[10][128];
extern void native_option_register(void *, const void *, const void *);
extern void native_option_parent_register(void *, const void *, const void *);
extern void native_option_alias_register(void *, const void *, const void *);
extern void aspect_ap_list_original(uintptr_t, void *, const uint32_t *);

void aspect_register_options(void *manager)
{
    struct entry { uint32_t id, reserved; void *row; } entries[6];
    for (unsigned i = 0; i < 6; ++i)
        entries[i] = (struct entry){5632 + i, 0, aspect_option_table[4 + i]};
    native_option_register(manager, entries, entries + 6);
}

void aspect_register_parents(void *manager)
{
    uint32_t entries[6][2];
    for (unsigned i = 0; i < 6; ++i) {
        entries[i][0] = 5632 + i;
        entries[i][1] = 33;
    }
    native_option_parent_register(manager, entries, entries + 6);
}

void aspect_register_aliases(void *manager)
{
    uint32_t entries[7][2] = {{5631, 5592}};
    for (unsigned i = 0; i < 6; ++i) {
        entries[i + 1][0] = 5632 + i;
        entries[i + 1][1] = 5632 + i;
    }
    native_option_alias_register(manager, entries, entries + 7);
}

void aspect_ap_list_text_hook(uintptr_t context, void *view, const uint32_t *args)
{
    aspect_ap_list_original(context, view, args);
    if (args[2] != 33 || args[1] >= 99) return;
    struct row { uint32_t kind, reserved; uint32_t *model; };
    struct row *row = (struct row *)view + args[1];
    if (row->kind != 28 || !row->model || row->model[0xd30 / 4] != 10) return;
    for (unsigned i = 0; i < 10; ++i) {
        row->model[0x30 / 4 + i] = 0xffffffff;
        row->model[0x430 / 4 + i] = 0xffffffff;
        row->model[0x830 / 4 + i] = ((const uint32_t *)aspect_option_table[i])[2];
    }
}
