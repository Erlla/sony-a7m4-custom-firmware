/* Protocol experiment: module is linked at emulator scratch addresses only.
 * Preserve native CP aspect 4 (17:9 in some consumers), assign 5..8 to the
 * four custom AP IDs 4..7. Native image processing receives full 3:2 = 2.
 * No frame latching, persistence or firmware installation is implied.
 */
#include <stdint.h>

volatile uint32_t aspect_selected_custom;

uint32_t aspect_cp_select(uint32_t cp_aspect)
{
    if (cp_aspect >= 5u && cp_aspect <= 8u) {
        aspect_selected_custom = cp_aspect - 1u;
        return 2u;
    }
    aspect_selected_custom = 0;
    return cp_aspect;
}
