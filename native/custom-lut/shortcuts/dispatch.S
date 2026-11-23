// New events use the stock dedicated-screen controller and its modal policy.
// The complete code travels with each event so simultaneous bindings stay distinct.
.text
.balign 4
.Lbase:
.equ base_va, 0x08fba000

.global dispatch_index
dispatch_index:
    mov w9, #0xfc
    movk w9, #0x216, lsl #16
    sub w9, w0, w9
    cmp w9, #3
    b.hi 1f
    mov w0, #0xb3
    ret
1:  and w1, w0, #0xff000000
    b .Lbase + (0x01b68494 - base_va)

.global filter_press
filter_press:
    ldr w10, [x1, #8]
    mov w9, #0xfc
    movk w9, #0x216, lsl #16
    sub w9, w10, w9
    cmp w9, #3
    b.ls 1f
    b .Lbase + (0x01841364 - base_va)
1:  stp x29, x30, [sp, #-32]!
    mov x29, sp
    str x1, [sp, #16]
    str w10, [sp, #24]
    mov w9, #0xb3
    movk w9, #0x216, lsl #16
    str w9, [x1, #8]
    bl .Lbase + (0x01841364 - base_va)
    ldr x1, [sp, #16]
    ldr w10, [x1, #8]
    mov w9, #0xb3
    movk w9, #0x216, lsl #16
    cmp w10, w9
    b.ne 2f
    ldr w10, [sp, #24]
    str w10, [x1, #8]
2:  ldp x29, x30, [sp], #32
    ret
