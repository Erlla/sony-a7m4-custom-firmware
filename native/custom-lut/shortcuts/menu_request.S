// Keep the target on the native request itself. The menu controller must
// be fully initialized before its regular confirm handler is invoked.
.text
.balign 4
.Lbase:
.equ base, 0x8fba100
.global key_request
key_request:
    ldr w8, [x1, #8]
    mov w9, #0xfc
    movk w9, #0x216, lsl #16
    sub w8, w8, w9
    cmp w8, #3
    b.hi .Loriginal
    add w9, w8, #1

    stp x29, x30, [sp, #-48]!
    mov x29, sp
    stp x19, x20, [sp, #16]
    ldr x19, [x0, #8]
    ldr x20, [x19, #0x1c8]
    str w9, [sp, #32]
    mov w8, #0x2d6
    str w8, [sp, #36]
    mov w8, #0x351
    str w8, [sp, #40]
    add x2, sp, #40
    add x1, sp, #36
    bl .Lbase + (0x1b8ec90-base)
    ldr x8, [x19, #0x1c8]
    cmp x8, x20
    b.eq 3f
    ldr w9, [sp, #32]
    strb w9, [x20, #0x12]
3:  ldp x19, x20, [sp, #16]
    ldp x29, x30, [sp], #48
    ret
.Loriginal:
    stp x29, x30, [sp, #-128]!
    b .Lbase + (0x1bd43a0-base)

// Each ordinary enqueue writes zero into the padding byte immediately
// following its two boolean fields. This variant works on either deque path.
.global write_flag
write_flag:
    sturh w1, [x0, #17]
    ret

.global dequeue
dequeue:
    ldrb w8, [x1, #0x12]
    sub sp, sp, #16
    str w8, [sp, #8]
    ldr w3, [x1]
    b .Lbase + (0x1f05f24-base)

.global opened
opened:
    ldr w8, [sp, #8]
    add sp, sp, #16
    cbz w8, .Lnext
    cmp w8, #4
    b.hi .Lnext
    ldr w9, [x27]
    cmp w9, #0x2d6
    b.ne .Lnext
    add x9, x19, #0x398
    mov w10, #4
.Lslot:
    ldr x0, [x9], #8
    cbz x0, 4f
    ldr w11, [x0, #0x178]
    cmp w11, #0x2d6
    b.ne 4f
    ldr x11, [x0, #0x180]
    cmp x11, x19
    b.eq .Lactivate
4:  subs w10, w10, #1
    b.ne .Lslot
.Lnext:
    b .Lbase + (0x1f05f10-base)
.Lactivate:
    stp x19, x30, [sp, #-16]!
    adr x9, .Lmids
    sub w8, w8, #1
    ldr w19, [x9, w8, uxtw #2]
    bl .Lbase + (0x2217fd4-base)
.Lkey_return:
    ldp x19, x30, [sp], #16
    b .Lnext
.Lmids:
    .word 33,1589,1592,1595

// The normal confirm handler saves its caller's x19 (the bound MID) and LR.
// Its inner model update must use the same MID as the outer validation.
.global selected_mid
selected_mid:
    ldr x9, [x29, #8]
    adr x10, .Lkey_return
    cmp x9, x10
    b.ne .Lgrid
    ldr w0, [x29, #16]
    ret
.global model_mid
model_mid:
    ldr x9, [x29, #8]
    adr x10, .Lbase
    mov w11, #0x813c
    movk w11, #0x221, lsl #16
    mov w12, #0xa100
    movk w12, #0x8fb, lsl #16
    sub x10, x10, x12
    add x11, x10, x11
    cmp x9, x11
    b.ne .Lgrid
    ldr x9, [x29]
    ldr x11, [x9, #8]
    adr x10, .Lkey_return
    cmp x11, x10
    b.ne .Lgrid
    ldr w0, [x9, #16]
    ret
.Lgrid:
    b .Lbase + (0x2215810-base)
