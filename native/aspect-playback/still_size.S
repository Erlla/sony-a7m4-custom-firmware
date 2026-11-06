// Extend native STILL size recognition, before publication and zoom exclusions.
// All original arguments, stack arguments and native fallback are preserved.
.text
.balign 16
.global aspect_native_still_size
aspect_native_still_size:
    ldr w8, [x0]
    cbnz w8, .Lnative
    ldr w8, [x0, #0xb84]
    ldr w9, [x0, #0xb88]
    adr x10, .Lpairs
    mov w11, #12
.Lnext:
    ldp w12, w13, [x10], #8
    cmp w8, w12
    ccmp w9, w13, #0, eq
    b.eq .Lrecognized
    subs w11, w11, #1
    b.ne .Lnext
.Lnative:
    stp x29, x30, [sp, #-16]!
    b native_still_size_body
.Lrecognized:
    mov w0, #1
    ret
.balign 8
.Lpairs:
    .include "dimensions.inc"
