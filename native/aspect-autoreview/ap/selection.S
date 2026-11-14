.arch armv8-a+fp
.text
.balign 4
/* No global image update hook. Preserve post-original integer, SIMD, flags,
 * FPCR/FPSR. The native image stays inactive in the parameter model. */
.global aspect_selection_refresh
.type aspect_selection_refresh,%function
aspect_selection_refresh:
    stp x29,x30,[sp,#-16]!
    blr x2
    sub sp,sp,#720
    stp x0,x1,[sp,#0]
    stp x2,x3,[sp,#16]
    stp x4,x5,[sp,#32]
    stp x6,x7,[sp,#48]
    stp x8,x9,[sp,#64]
    stp x10,x11,[sp,#80]
    stp x12,x13,[sp,#96]
    stp x14,x15,[sp,#112]
    stp x16,x17,[sp,#128]
    str x18,[sp,#144]
    mrs x9,nzcv
    str x9,[sp,#152]
    stp q0,q1,[sp,#160]
    stp q2,q3,[sp,#192]
    stp q4,q5,[sp,#224]
    stp q6,q7,[sp,#256]
    stp q8,q9,[sp,#288]
    stp q10,q11,[sp,#320]
    stp q12,q13,[sp,#352]
    stp q14,q15,[sp,#384]
    stp q16,q17,[sp,#416]
    stp q18,q19,[sp,#448]
    stp q20,q21,[sp,#480]
    stp q22,q23,[sp,#512]
    stp q24,q25,[sp,#544]
    stp q26,q27,[sp,#576]
    stp q28,q29,[sp,#608]
    stp q30,q31,[sp,#640]
    mrs x9,fpcr
    mrs x10,fpsr
    str x9,[sp,#672]
    str x10,[sp,#680]
    mov x0,x19
    bl aspect_selection_draw
    ldr x9,[sp,#672]
    ldr x10,[sp,#680]
    msr fpcr,x9
    msr fpsr,x10
    ldp q0,q1,[sp,#160]
    ldp q2,q3,[sp,#192]
    ldp q4,q5,[sp,#224]
    ldp q6,q7,[sp,#256]
    ldp q8,q9,[sp,#288]
    ldp q10,q11,[sp,#320]
    ldp q12,q13,[sp,#352]
    ldp q14,q15,[sp,#384]
    ldp q16,q17,[sp,#416]
    ldp q18,q19,[sp,#448]
    ldp q20,q21,[sp,#480]
    ldp q22,q23,[sp,#512]
    ldp q24,q25,[sp,#544]
    ldp q26,q27,[sp,#576]
    ldp q28,q29,[sp,#608]
    ldp q30,q31,[sp,#640]
    ldr x9,[sp,#152]
    msr nzcv,x9
    ldp x0,x1,[sp,#0]
    ldp x2,x3,[sp,#16]
    ldp x4,x5,[sp,#32]
    ldp x6,x7,[sp,#48]
    ldp x8,x9,[sp,#64]
    ldp x10,x11,[sp,#80]
    ldp x12,x13,[sp,#96]
    ldp x14,x15,[sp,#112]
    ldp x16,x17,[sp,#128]
    ldr x18,[sp,#144]
    add sp,sp,#720
    ldp x29,x30,[sp],#16
    ret

/* Two opaque bars in an existing image's native nine-rect Sprite; seven
 * unused rects are zero-sized. No resources, count changes or allocations.
 * Leave Widget inactive parameter untouched so native next refresh hides it
 * on cancelled/native/other-menu selections. */
.global aspect_selection_draw
.type aspect_selection_draw,%function
aspect_selection_draw:
    stp x29,x30,[sp,#-112]!
    stp x19,x20,[sp,#16]
    stp x21,x22,[sp,#32]
    mov x29,sp
    add x1,sp,#64
    bl aspect_selection_geometry
    cbz x0,4f
    mov x19,x0
    add x20,x0,#0x248
    str xzr,[sp,#48]
    add x1,sp,#48
    bl native_selection_widget_position
    mov w21,#0
1:  fmov s0,wzr
    fmov s1,wzr
    cmp w21,#2
    b.hs 2f
    add x22,sp,#64
    add x22,x22,x21,lsl #4
    ldp w0,w1,[x22]
    scvtf s0,w0
    scvtf s1,w1
2:  stp s0,s1,[sp,#48]
    mov x0,x20
    mov w1,w21
    add x2,sp,#48
    bl native_selection_rect_position
    fmov s0,wzr
    fmov s1,wzr
    cmp w21,#2
    b.hs 3f
    ldp w0,w1,[x22,#8]
    scvtf s0,w0
    scvtf s1,w1
3:  mov x0,x20
    mov w1,w21
    bl native_selection_rect_size
    mov w0,#0xff000000
    str w0,[sp,#48]
    mov x0,x20
    mov w1,w21
    add x2,sp,#48
    bl native_selection_rect_color
    add w21,w21,#1
    cmp w21,#9
    b.ne 1b
    mov x0,x19
    mov w1,#1
    bl native_selection_widget_mode
4:  ldp x19,x20,[sp,#16]
    ldp x21,x22,[sp,#32]
    ldp x29,x30,[sp],#112
    ret
