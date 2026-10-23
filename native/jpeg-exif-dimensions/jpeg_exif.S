/* JPEG implementation only: own the ExifSrcArea until libstill destruction.
 * 2732F0 is JPEG vtable[0x18]. Its normal caller passes object+8 as add_if_t.
 * libstill::add already reserves/copies 0xBC bytes at object+0x13C0.
 * A bounded SOF0 read uses this object's encoded main JPEG, never menu state.
 * Failure and equal dimensions leave every byte and pointer unchanged.
 * This leaf prelude retains no frame during the original JPEG implementation.
 */
.text
.balign 16
.global aspect_jpeg_exif_header
.type aspect_jpeg_exif_header,%function
aspect_jpeg_exif_header:
    sub sp, sp, #96
    stp x2, x3, [sp]
    stp x4, x5, [sp, #16]
    stp x6, x7, [sp, #32]
    stp x8, x9, [sp, #48]
    str x10, [sp, #64]
    mrs x10, nzcv
    str x10, [sp, #72]
    cbz x0, .Ldone
    add x2, x0, #8
    cmp x1, x2
    b.ne .Ldone
    ldr x2, [x1]
    cbz x2, .Ldone
    ldr x3, [x1, #0x158]
    cbz x3, .Ldone
    ldr w4, [x1, #0x150]
    cmp w4, #21
    b.lo .Ldone
    mov w5, #0x800
    cmp w4, w5
    csel w4, w4, w5, lo
    mov x5, #0
/* Native reader also locates SOI or DQT in the first 256 bytes. */
.Lfind:
    add x7, x5, #2
    cmp x7, x4
    b.hi .Ldone
    ldrb w6, [x3, x5]
    cmp w6, #0xff
    b.ne .Lnext
    add x7, x3, x5
    ldrb w6, [x7, #1]
    cmp w6, #0xdb
    b.eq .Lmarker
    cmp w6, #0xd8
    b.eq .Lsoi
.Lnext:
    add x5, x5, #1
    cmp x5, #0x100
    b.lo .Lfind
    b .Ldone
.Lsoi:
    add x5, x5, #2
.Lmarker:
    add x7, x5, #4
    cmp x7, x4
    b.hi .Ldone
    add x10, x3, x5
    ldrb w6, [x10]
    cmp w6, #0xff
    b.ne .Ldone
    ldrb w6, [x10, #1]
    cmp w6, #0xc0
    b.eq .Lsof
    cmp w6, #0xda
    b.eq .Ldone
    cmp w6, #0xd9
    b.eq .Ldone
    ldrb w6, [x10, #2]
    ldrb w7, [x10, #3]
    orr w6, w7, w6, lsl #8
    cmp w6, #2
    b.lo .Ldone
    add x5, x5, x6
    add x5, x5, #2
    b .Lmarker
.Lsof:
    ldrb w6, [x10, #2]
    ldrb w7, [x10, #3]
    orr w6, w7, w6, lsl #8
    cmp w6, #17
    b.ne .Ldone
    add x7, x5, x6
    add x7, x7, #2
    cmp x7, x4
    b.hi .Ldone
    ldrb w6, [x10, #4]
    cmp w6, #8
    b.ne .Ldone
    ldrb w6, [x10, #9]
    cmp w6, #3
    b.ne .Ldone
    ldrb w8, [x10, #5]
    ldrb w6, [x10, #6]
    orr w8, w6, w8, lsl #8
    cbz w8, .Ldone
    ldrb w9, [x10, #7]
    ldrb w6, [x10, #8]
    orr w9, w6, w9, lsl #8
    cbz w9, .Ldone
    ldp w6, w7, [x2, #0x5c]
    cmp w6, w9
    b.ne .Lcopy
    cmp w7, w8
    b.eq .Ldone
.Lcopy:
    mov x10, #0x13c0
    add x10, x0, x10
    mov x6, #0
/* Exactly 0xBC bytes, including no padding outside the original owned area. */
.Lcopy8:
    ldr x7, [x2, x6]
    str x7, [x10, x6]
    add x6, x6, #8
    cmp x6, #0xb8
    b.lo .Lcopy8
    ldr w7, [x2, #0xb8]
    str w7, [x10, #0xb8]
    stp w9, w8, [x10, #0x5c]
    str x10, [x1]
.Ldone:
    ldr x10, [sp, #72]
    msr nzcv, x10
    ldp x2, x3, [sp]
    ldp x4, x5, [sp, #16]
    ldp x6, x7, [sp, #32]
    ldp x8, x9, [sp, #48]
    ldr x10, [sp, #64]
    add sp, sp, #96
    sub sp, sp, #0xe10
    b native_jpeg_header_body
.size aspect_jpeg_exif_header, .-aspect_jpeg_exif_header
