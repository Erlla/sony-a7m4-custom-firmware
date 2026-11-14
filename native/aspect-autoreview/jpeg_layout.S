/* JPEG read metadata: provide the native base layout for known custom sizes.
 * Preserve exact pixel dimensions; do not rewrite EXIF, RAW or capture data.
 * This hook runs only after libjpeg's real metadata parser has finished.
 */
.text
.balign 16
.global aspect_jpeg_layout
aspect_jpeg_layout:
    ldr x8, [x19, #8]
    cbz x8, .Loriginal
    ldrb w9, [x8, #0xc]
    cbnz w9, .Loriginal
    ldrb w9, [x8]
    cbz w9, .Loriginal
    ldp w9, w10, [x8, #4]
    adr x11, .Lpairs
    mov w12, #18
.Lnext:
    ldp w13, w14, [x11], #8
    cmp w9, w13
    ccmp w10, w14, #0, eq
    b.eq .Llayout
    subs w12, w12, #1
    b.ne .Lnext
    b .Loriginal
.Llayout:
    mov w9, #1
    strb w9, [x8, #0xc]
    str wzr, [x8, #0x10]
.Loriginal:
    mov w0, #2
    b native_jpeg_ana_resume
.balign 8
.Lpairs:
    .include "dimensions.inc"
