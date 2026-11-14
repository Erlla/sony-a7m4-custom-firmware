/* Fit masks in raw YUV coordinates, then use the native guide's UI-rectangle
 * transform. A zero local Sprite angle does not remove screen rotation. */
#include <stdint.h>
extern uint32_t aspect_ap_completed_selection_read(void);
extern void native_model_lock(void), native_model_unlock(void);
extern const volatile uint32_t *native_yuv_x(void), *native_yuv_y(void);
extern const volatile uint32_t *native_yuv_w(void), *native_yuv_h(void);
extern const volatile uint32_t *native_output(void), *native_panel_aspect(void);
extern const volatile uint32_t *native_mode(void), *native_still_aspect(void);
extern const volatile uint32_t *native_orientation(void), *native_display_mapping(void);
#define U32(p,o) (*(const uint32_t *)((const uint8_t *)(p)+(o)))
#define PTR(p,o) (*(uint8_t *const *)((const uint8_t *)(p)+(o)))
typedef struct { int32_t x,y,w,h; } rect;
typedef struct { rect bars[2]; } mask;

static uint8_t *geometry(const uint8_t *p,mask *out,uint32_t fn38)
{
    if (!p || !out || U32(p,8)>2) return 0;
    uint32_t token=aspect_ap_completed_selection_read(),id=token&15;
    if (!(token&16) || id<4 || id>9) return 0;
    const uint8_t *view=PTR(p,fn38?0x40:0x68),*table=PTR(p,fn38?0x48:0x70);
    if (!view || !table || U32(view,0x3e90)!=(fn38?38u:76u) || U32(table,96)!=0) return 0;
    if (fn38) {
        if (U32(table,0)!=1 || U32(table,48)!=0x6a || U32(table,64)!=0x6b) return 0;
    } else if (U32(table,0)!=0x6a || U32(table,16)!=0x6b) return 0;
    uint8_t *widget=PTR(view,0x3ec8+6*8),*param=PTR(table,104);
    if (!widget || !param || param!=widget+0x1d8 ||
        (param[0x2c] && U32(param,0x3c)!=UINT32_MAX)) return 0;
    const uint8_t *sprite=widget+0x248;
    if (!PTR(sprite,0xd0) || U32(sprite,0xd8)!=0x00090009 ||
        PTR(sprite,0x78) || U32(sprite,0x80)!=UINT32_MAX) return 0;
    native_model_lock();
    int32_t x=(int32_t)*native_yuv_x(),y=(int32_t)*native_yuv_y();
    int32_t w=(int32_t)*native_yuv_w(),h=(int32_t)*native_yuv_h();
    uint32_t route=*native_output(),format=*native_panel_aspect();
    uint32_t mode=*native_mode(),native=*native_still_aspect();
    uint32_t direction=*native_orientation(),mapping=*native_display_mapping();
    native_model_unlock();
    if (token!=aspect_ap_completed_selection_read() || mode!=2 || native!=0 ||
        direction!=U32(p,8) || direction!=U32(p,fn38?0x1388:0x13c0) ||
        route!=U32(p,fn38?0x3258:0x5380)) return 0;
    uint32_t source;
    if (route==0) source=3;
    else if (route==1 && format>=1 && format<=3) {
        static const uint8_t map[3]={0,2,1};source=map[format-1];
    } else return 0;
    /* Retain the native portrait-layout check. This checks the widget contract,
     * not the coordinate system of the raw YUV area or blank Sprite rects. */
    if (U32(param,0x20)!=(direction?480u:640u) ||
        U32(param,0x24)!=(direction?640u:480u)) return 0;
    /* Same physical display bounds in all three UI orientations. Validate
     * before addition; no guessed rotation, clipping or fallback viewport. */
    if (x<0 || y<0 || w<=0 || h<=0 || x>640 || y>480 ||
        w>640-x || h>480-y) return 0;
    static const uint16_t num[6]={17,65,5,7,7,47},den[6]={6,24,4,6,3,20};
    static const uint16_t sn[4]={1,9,4,1},sd[4]={1,8,3,1};
    uint32_t n=num[id-4]*sd[source],d=den[id-4]*sn[source];
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
    /* Native guide 0x186CB28 converts raw rectangles to the rotated UI plane.
     * Its +0x21e flag is snapshot(0x28EFAF4)==4. Translate the full rectangle,
     * including offsets and opposite edge; swapping only width/height is wrong. */
    if (direction) for (uint32_t i=0;i<2;i++) {
        rect r=out->bars[i];
        if ((direction==1)!=(mapping==4))
            out->bars[i]=(rect){480-r.y-r.h,r.x,r.h,r.w};
        else
            out->bars[i]=(rect){r.y,640-r.x-r.w,r.h,r.w};
    }
    return widget;
}
uint8_t *aspect_fn38_ui_geometry(const uint8_t *p,mask *out) { return geometry(p,out,1); }
uint8_t *aspect_fn76_ui_geometry(const uint8_t *p,mask *out) { return geometry(p,out,0); }
