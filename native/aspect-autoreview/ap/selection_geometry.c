/* scr7036_0009 row4 only. Follow the highlighted menu value and the completed
 * native snapshot, then map raw YUV bars into the rotated UI rectangle plane. */
#include <stdint.h>
#define U32(p,o) (*(const uint32_t *)((const uint8_t *)(p)+(o)))
#define PTR(p,o) (*(uint8_t *const *)((const uint8_t *)(p)+(o)))
typedef struct { int32_t x,y,w,h; } rect;
typedef struct { rect bars[2]; } mask;

uint8_t *aspect_selection_geometry(const uint8_t *presenter,mask *out)
{
    if (!presenter || !out || U32(presenter,0x5878)!=33) return 0;
    /* Preserve T16: browsing a highlight must not depend on committed state. */
    uint32_t id=U32(presenter,0x71c8)-5632;
    if (id>5) return 0;
    const uint8_t *view=PTR(presenter,0x80),*table=PTR(presenter,0x88);
    if (!view || !table || U32(view,0x3e90)!=98 || U32(table,0)!=0x3a || U32(table,64)!=0) return 0;
    uint8_t *widget=PTR(view,0x3ec8+4*8),*param=PTR(table,72),*grid=PTR(table,8);
    /* Preserve T17: active=1 with invalid image ID is a native blank image. */
    if (!widget || !param || !grid || param!=widget+0x1d8 ||
        (param[0x2c] && U32(param,0x3c)!=UINT32_MAX)) return 0;
    const uint8_t *sprite=widget+0x248;
    if (!PTR(sprite,0xd0) || U32(sprite,0xd8)!=0x00090009 ||
        PTR(sprite,0x78) || U32(sprite,0x80)!=UINT32_MAX) return 0;
    const uint8_t *model=presenter+0xf48;
    /* Actual 203CDF4 snapshot: 203E808 stores mapping at +5A60;
     * 203F2D4 stores orientation at +6378. No new live model reads. */
    uint32_t direction=U32(presenter,8),mapping=U32(model,0x5a60);
    if (direction>2 || U32(model,0x6378)!=direction ||
        U32(param,0x20)!=(direction?480u:640u) ||
        U32(param,0x24)!=(direction?640u:480u)) return 0;
    uint32_t source;
    if (U32(model,0x1e8)==0) source=3;
    else if (U32(model,0x1e8)==1) {
        uint32_t format=U32(model,0x208);
        if (format<1 || format>3) return 0;
        static const uint8_t map[3]={0,2,1};source=map[format-1];
    } else return 0;
    int32_t x=(int32_t)U32(model,0x128),y=(int32_t)U32(model,0x148);
    int32_t w=(int32_t)U32(model,0x168),h=(int32_t)U32(model,0x188);
    /* Raw YUV dimensions stay in the fixed physical plane. Validate before
     * adding; portrait 480x640 is the UI layout, not the raw YUV extent. */
    if (x<0 || y<0 || w<=0 || h<=0 || x>640 || y>480 ||
        w>640-x || h>480-y) return 0;
    static const uint16_t num[6]={17,65,5,7,7,47},den[6]={6,24,4,6,3,20};
    static const uint16_t sn[4]={1,9,4,1},sd[4]={1,8,3,1};
    uint32_t n=num[id]*sd[source],d=den[id]*sn[source];
    uint32_t a=(uint32_t)w*d,b=(uint32_t)h*n;
    if (a>b) {
        int32_t t=(int32_t)((a-b+d)/(2*d));
        if (t<=0 || 2*t>=w) return 0;
        out->bars[0]=(rect){x,y,t,h};out->bars[1]=(rect){x+w-t,y,t,h};
    } else {
        int32_t t=(int32_t)((b-a+n)/(2*n));
        if (t<=0 || 2*t>=h) return 0;
        out->bars[0]=(rect){x,y,w,t};out->bars[1]=(rect){x,y+h-t,w,t};
    }
    /* Original guide186CB28: transform origin and both edges, including the
     * same mapping==4 direction exchange used by global screen rotation. */
    if (direction) for (uint32_t i=0;i<2;i++) {
        rect r=out->bars[i];
        if ((direction==1)!=(mapping==4))
            out->bars[i]=(rect){480-r.y-r.h,r.x,r.h,r.w};
        else
            out->bars[i]=(rect){r.y,640-r.x-r.w,r.h,r.w};
    }
    return widget;
}
