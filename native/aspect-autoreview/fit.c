/* AutoReview alone uses these three layout calls. The YC PIN already contains
 * the frozen capture crop from R2; reading the current menu would race it.
 * Preserve the native per-device 3:2 layout, then fit the cropped content inside
 * it. Native VDF's explicit destination rectangle handles scale and black bars.
 */
#include <stdint.h>
extern void native_review_layout(const void *, void *);

static uint16_t halfword(const uint8_t *p) { return p[0] | (uint16_t)p[1]<<8; }

void aspect_review_layout(const uint64_t *args, void *result, const uint8_t *seq)
{
    const uint8_t *pin=seq+0x13c;
    uint32_t w=halfword(pin+0x36), h=halfword(pin+0x38);
    /* Native3:2 has alignment padding (e.g.1616x1080). All six added ratios
     * are separated from3:2 by much more than this four-pixel tolerance.
     */
    if (pin[0x1e]!=1 || !w || !h ||
        (2*w<=3*h+12 && 3*h<=2*w+12) ||
        (uint32_t)args[0]!=2 || (uint32_t)(args[0]>>32)!=0) {
        native_review_layout(args,result);
        return;
    }
    const uint32_t *words=(const uint32_t *)args;
    uint32_t device=words[3];
    uint32_t selector=device==1 ? 0x5c : device==2 ? 0x6a : 0x78;
    const uint8_t *selectors=(const uint8_t *)(uintptr_t)args[5];
    const uint8_t *entry=(const uint8_t *)(uintptr_t)args[4]+12*selectors[selector];
    uint32_t x=halfword(entry+8), y=halfword(entry+10);
    uint32_t bw=halfword(entry+12), bh=halfword(entry+14), nw=bw, nh=bh;
    /* VDF rounds destination X to two pixels and W to four. Supply an
     * already-aligned width so it does not truncate the fit a second time.
     */
    if (2*w<3*h) nw=(bw*2*w/(3*h)+2)&~3u;
    else nh=(bh*3*h/(2*w)+1)&~1u;
    x+=(bw-nw)/2; y+=(bh-nh)/2;
    uint16_t geometry[8]={0,0,entry[4],0,x,y,nw,nh};
    uint8_t choices[0x86]={0};
    uint64_t local[6];
    for (unsigned i=0;i<6;i++) local[i]=args[i];
    local[4]=(uintptr_t)geometry;
    local[5]=(uintptr_t)choices;
    native_review_layout(local,result);
}
