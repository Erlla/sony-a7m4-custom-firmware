/* Normalize the camera's named input events at the owned LUT entry.
 * Keep preview/coalescing, commit, cancel and touch in the existing dispatcher.
 * The event record is borrowed: do not rewrite it for other native consumers. */
#include <stdint.h>

extern const uint32_t current_lut_scene __attribute__((visibility("hidden")));
extern int32_t existing_gui_dispatch(uint64_t controller, uint64_t message,
                                     uint32_t event);

int32_t lut_input_dispatch(uint64_t controller, uint64_t message, uint32_t event) {
    if (current_lut_scene == 0xd9u || current_lut_scene == 0xdau) {
        switch (event) {
        case 0x2010011u: case 0x2010013u: /* multi-selector up, repeat */
            event = 0x2010000u; break;
        case 0x2010014u: case 0x2010016u: /* down, repeat */
            event = 0x2010003u; break;
        case 0x2010017u: case 0x2010019u: /* left, repeat */
            event = 0x2010006u; break;
        case 0x201001au: case 0x201001cu: /* right, repeat */
            event = 0x2010009u; break;
        case 0x201001du: /* center press, not release or hold-repeat */
            event = 0x201000cu; break;
        case 0x2050000u: case 0x2050002u:
        case 0x2050004u: case 0x2050006u: /* wheel right */
            event = current_lut_scene == 0xdau ? 0x2010000u : 0x2010003u;
            break;
        case 0x2050001u: case 0x2050003u:
        case 0x2050005u: case 0x2050007u: /* wheel left */
            event = current_lut_scene == 0xdau ? 0x2010003u : 0x2010000u;
            break;
        }
    }
    return existing_gui_dispatch(controller, message, event);
}
