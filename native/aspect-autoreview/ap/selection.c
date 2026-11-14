/* scr7036_0009 only. No saved widget/model pointers, allocation, file access,
 * image-resource changes or changes to the native 98-row descriptor layout.
 * Called after original policy and view update, on the current presenter. */
#include <stdint.h>
#include <stddef.h>
extern const uint16_t aspect_native_alloc_units[0x8d][2];
extern uint32_t aspect_ap_completed_selection_read(void);
typedef struct { int32_t x,y,w,h; } rect;
typedef struct { rect bars[2]; } mask;
#define U32(p,o) (*(const uint32_t *)((const uint8_t *)(p)+(o)))
#define PTR(p,o) (*(uint8_t *const *)((const uint8_t *)(p)+(o)))

void aspect_selection_prepare(const uint8_t *view,const uint8_t *layout,
                              uint32_t count,uint8_t *flags)
{
    if (!view || !layout || !flags || count!=98 || U32(layout,0)!=0x3a ||
        U32(layout,4*52)!=0) return;
    flags[4]=1;
    uint32_t capacity=U32(view,0x3ea0),total=0;
    for (uint32_t i=0;i<count;++i) {
        uint32_t type=U32(layout,i*52);
        if (type>=sizeof(aspect_native_alloc_units)/sizeof(aspect_native_alloc_units[0])) return;
        uint32_t n=(uint32_t)aspect_native_alloc_units[type][i!=4 && flags[i]!=0]*128;
        if (!n || n>=capacity-total) return;
        total+=n;
    }
    flags[4]=0;
}

/* Return only an actual current row4 image with an unused Sprite. A native
 * active image, queued/loaded image, other leaf/selection or dummy fails closed.
 * Native view update has already hidden the prior mask on every such path.
 * Source ratio correction matches native186CFE8 constants (4:3,3:2,16:9,4:3).
 * Round positive half widths/heights like native FCVTAS; no floating helper. */
