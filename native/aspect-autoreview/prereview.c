/* CP packets1005/1012 own the YC used for automatic review. Adapt only the
 * formatter's stack-argument copy, using this native task's frozen choice.
 * Task geometry, buffer addresses, canvas, formats and native aspect stay
 * unchanged. The original PIN constructor executes after this adapter.
 */
#include <stdint.h>
#include "cp/crop_core.h"
extern uint32_t aspect_task_id(uintptr_t);

void aspect_prereview_arguments(uint32_t *args, uintptr_t task)
{
    uint32_t id = aspect_task_id(task);
    if (!id) return;
    aspect_geometry g = {
        (uint16_t)args[6], (uint16_t)(args[6] >> 16),
        (uint16_t)args[7], (uint16_t)(args[7] >> 16),
        (uint16_t)args[8], (uint16_t)(args[8] >> 16)
    };
    if (!aspect_crop_geometry(&g, id | ASPECT_GEOMETRY_AUX, 0, &g)) return;
    args[5] = args[7] = args[9] = (uint32_t)g.width | ((uint32_t)g.height << 16);
    args[8] = (uint32_t)g.x | ((uint32_t)g.y << 16);
}
