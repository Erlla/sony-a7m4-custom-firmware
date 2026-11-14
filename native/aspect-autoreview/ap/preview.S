.arch armv8-a+fp
.text
.balign 4
/* All C read helpers must be built with -mgeneral-regs-only and no outline
 * atomics; canonical read must also preserve SIMD. No new lock/file/getter.
 * SAVE/RESTORE preserves every caller-saved integer and NZCV around helpers.
 * Callee-saved integer/SIMD values follow the original AAPCS64 contract. */
.macro SAVE_VOLATILE base
    stp x0,x1,[sp,#\base]
    stp x2,x3,[sp,#(\base+16)]
    stp x4,x5,[sp,#(\base+32)]
    stp x6,x7,[sp,#(\base+48)]
    stp x8,x9,[sp,#(\base+64)]
    stp x10,x11,[sp,#(\base+80)]
    stp x12,x13,[sp,#(\base+96)]
    stp x14,x15,[sp,#(\base+112)]
    stp x16,x17,[sp,#(\base+128)]
    str x18,[sp,#(\base+144)]
    mrs x9,nzcv
    str x9,[sp,#(\base+152)]
.endm
.macro RESTORE_VOLATILE base
    ldr x9,[sp,#(\base+152)]
    msr nzcv,x9
    ldp x0,x1,[sp,#\base]
    ldp x2,x3,[sp,#(\base+16)]
    ldp x4,x5,[sp,#(\base+32)]
    ldp x6,x7,[sp,#(\base+48)]
    ldp x8,x9,[sp,#(\base+64)]
    ldp x10,x11,[sp,#(\base+80)]
    ldp x12,x13,[sp,#(\base+96)]
    ldp x14,x15,[sp,#(\base+112)]
    ldp x16,x17,[sp,#(\base+128)]
    ldr x18,[sp,#(\base+144)]
.endm

/* BL wrappers at 1DDACC4 and 1E56C68 only. Shared 244CFAC stays native RET.
 * 244D1B4 is the complete native body/prologue, not the earlier 244CFB0.
 * Preserve all original integer arguments, return registers and post-native
 * volatile/NZCV state across the extra pure calls. Frame is 192 aligned bytes. */
.global aspect_preview_producer_wrapper
.type aspect_preview_producer_wrapper,%function
aspect_preview_producer_wrapper:
    stp x29,x30,[sp,#-192]!
    mov x29,sp
    stp x19,x20,[sp,#16]
    SAVE_VOLATILE 32
    mov x19,x1
    mov x0,x1
    mov x1,x3
    bl aspect_preview_producer_begin
    mov x20,x0
    RESTORE_VOLATILE 32
    tbz x20,#32,1f
    bl native_guide_producer_body
.global aspect_preview_producer_custom_return
aspect_preview_producer_custom_return:
    b 2f
1:  bl native_guide_producer
2:  SAVE_VOLATILE 32
    mov x0,x19
    mov x1,x20
    bl aspect_preview_producer_finish
    RESTORE_VOLATILE 32
    ldp x19,x20,[sp,#16]
    ldp x29,x30,[sp],#192
    ret


/* Source-bound replacement of native CBNZ W0 at 244D2E0. Native ON=0
 * is unchanged. Only named OFF=1 and this exact custom-wrapper invocation
 * bypass the optional guide-display setting. Native producer prologue saves
 * caller LR at FP+8 and caller X20 (our cookie) at FP+18h before X20=param.
 * Preserve X16/X17, SP and NZCV; no calls, model writes or pointer retention.
 */
.global aspect_preview_still_display_gate
.type aspect_preview_still_display_gate,%function
aspect_preview_still_display_gate:
    cbz w0,3f
    stp x16,x17,[sp,#-16]!
    sub w16,w0,#1
    cbnz w16,2f
    ldr x16,[x29,#8]
    adr x17,aspect_preview_producer_custom_return
    eor x16,x16,x17
    cbnz x16,2f
    ldr x16,[x29,#0x18]
    tbz x16,#32,2f
    ldp x16,x17,[sp],#16
3:  b native_still_display_allow
2:  ldp x16,x17,[sp],#16
    b native_still_display_deny

/* Original create_screen uses flags[row] to choose a real Widget or a dummy
 * parameter-only allocation. Capacity-check the full layout, then clear only the guide flag for the
 * two recording families, restore it after the call, then register the result.
 * The native fixed-capacity arena and all other row flags remain authoritative.
 * Save every argument/volatile before and after the displaced original BLR. */
.global aspect_preview_bind_first
.type aspect_preview_bind_first,%function
aspect_preview_bind_first:
    stp x29,x30,[sp,#-192]!
    mov x29,sp
    SAVE_VOLATILE 16
    str x5,[sp,#176]
    ldrb w16,[x5,#4]
    strb w16,[sp,#184]
    mov x1,x2
    mov w2,w3
    mov x3,x5
    mov w4,#0
    bl aspect_preview_prepare_create
    RESTORE_VOLATILE 16
    blr x8
    SAVE_VOLATILE 16
    ldr x16,[sp,#176]
    ldrb w17,[sp,#184]
    strb w17,[x16,#4]
    mov x0,x19
    mov w1,w21
    bl aspect_preview_register_first
    RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#192
    ret
.global aspect_preview_bind_second
.type aspect_preview_bind_second,%function
aspect_preview_bind_second:
    stp x29,x30,[sp,#-192]!
    mov x29,sp
    SAVE_VOLATILE 16
    str x5,[sp,#176]
    ldrb w16,[x5,#3]
    strb w16,[sp,#184]
    mov x1,x2
    mov w2,w3
    mov x3,x5
    mov w4,#1
    bl aspect_preview_prepare_create
    RESTORE_VOLATILE 16
    blr x8
    SAVE_VOLATILE 16
    ldr x16,[sp,#176]
    ldrb w17,[sp,#184]
    strb w17,[x16,#3]
    mov x0,x19
    mov w1,w21
    bl aspect_preview_register_second
    RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#192
    ret

/* Entry186D2AC: revoke all matching aliases before native child/base cleanup.
 * Replay the original displaced STP and tail186D2B0 with entry state intact. */
.global aspect_preview_guide_destructor
.type aspect_preview_guide_destructor,%function
aspect_preview_guide_destructor:
    stp x29,x30,[sp,#-176]!
    SAVE_VOLATILE 16
    add x0,x0,#0x1d8
    bl aspect_preview_unbind
    RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#176
    stp x29,x30,[sp,#-32]!
    b native_guide_destructor_body

/* Both guide paths are getter-free. Custom geometry uses a private 16B rect;
 * native viewport remains unchanged even after repeated portrait refreshes. */
.global aspect_preview_guide_update
.type aspect_preview_guide_update,%function
aspect_preview_guide_update:
    stp x29,x30,[sp,#-64]!
    mov x29,sp
    stp x19,x20,[sp,#16]
    str x21,[sp,#32]
    mov x19,x0
    bl aspect_preview_guide_read
    cbz w0,3f
    cmn w0,#1
    b.eq 4f
    mov w21,w0
    ldr x0,[x19,#0x208]
    ldr x1,[x19,#0x210]
    stp x0,x1,[sp,#48]
    ldr x2,[x19]
    mov x0,x19
    ldr x2,[x2,#0x30]
    mov w1,#2
    blr x2
    ldrb w0,[x19,#0x21d]
    cbz w0,1f
    mov x0,x19
    add x1,sp,#48
    bl native_guide_portrait
1:  ldr w20,[x19,#0x224]
    mov w0,#15
    str w0,[x19,#0x224]
    sub w0,w21,#4
    adr x1,aspect_preview_ratios
    ldr d0,[x1,w0,uxtw #3]
    ldrb w0,[x19,#0x21d]
    cbz w0,2f
    fmov d1,#1.0
    fdiv d0,d1,d0
2:  mov x0,x19
    add x1,sp,#48
    bl native_guide_fit
    str w20,[x19,#0x224]
5:  ldr x21,[sp,#32]
    ldp x19,x20,[sp,#16]
    ldp x29,x30,[sp],#64
    ret
3:  mov x0,x19
    ldr x21,[sp,#32]
    ldp x19,x20,[sp,#16]
    ldp x29,x30,[sp],#64
    stp x29,x30,[sp,#-32]!
    b native_guide_update_body
4:  ldr x2,[x19]
    mov x0,x19
    ldr x2,[x2,#0x30]
    mov w1,#3
    blr x2
    b 5b
.balign 8
aspect_preview_ratios:
    .double 2.8333333333333333333,2.7083333333333333333,1.25,1.1666666666666666667,2.3333333333333333333,2.35

/* Source-bound device-capability predicates. Native prologue is one ADD;
 * replay that instruction and tail to +4 when no scoped override is requested.
 * Preserve original arguments/GPR/NZCV. Only W0=1 is returned for custom guide.
 */
.macro CAPABILITY_WRAPPER name, family, page, target
.global \name
.type \name,%function
\name:
    stp x29,x30,[sp,#-176]!
    mov x29,sp
    SAVE_VOLATILE 16
    mov w2,#\family
    bl aspect_preview_custom_capability
    cbz w0,1f
    RESTORE_VOLATILE 16
    mov w0,#1
    ldp x29,x30,[sp],#176
    ret
1:  RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#176
    add x0,x0,#\page,lsl #12
    b \target
.endm
CAPABILITY_WRAPPER aspect_preview_capability_first, 0, 0x50, native_capability_first_body
CAPABILITY_WRAPPER aspect_preview_capability_second, 1, 0x47, native_capability_second_body

/* scr7036_0009 initial/rotation create. Same native 98 rows, only row4's
 * real/dummy flag is capacity checked; no ownership or extra model allocation. */
.global aspect_selection_create
.type aspect_selection_create,%function
aspect_selection_create:
    stp x29,x30,[sp,#-192]!
    mov x29,sp
    SAVE_VOLATILE 16
    str x5,[sp,#176]
    ldrb w16,[x5,#4]
    strb w16,[sp,#184]
    mov x1,x2
    mov w2,w3
    mov x3,x5
    bl aspect_selection_prepare
    RESTORE_VOLATILE 16
    blr x8
    SAVE_VOLATILE 16
    ldr x16,[sp,#176]
    ldrb w17,[sp,#184]
    strb w17,[x16,#4]
    RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#192
    ret

/* Native orientation setters rebuild the same recording view after its old
 * widgets have been destroyed. These are distinct from constructor callsites.
 * At 1D54898/1D547B0 X19 is presenter, X5 flags, W4 the new orientation;
 * X21 is NOT a layer. Read the native layer field for post-create registration.
 * Keep clear->create->policy->activation order, every original BLR argument,
 * return GPR/NZCV and the original guide flag. Capacity guard runs for both
 * incoming flag states, including capability policy's already-enabled guide.
 */
.macro ROTATION_BIND name, family, row, layer, register
.global \name
.type \name,%function
\name:
    stp x29,x30,[sp,#-192]!
    mov x29,sp
    SAVE_VOLATILE 16
    str x5,[sp,#176]
    ldrb w16,[x5,#\row]
    strb w16,[sp,#184]
    mov x1,x2
    mov w2,w3
    mov x3,x5
    mov w4,#\family
    bl aspect_preview_prepare_create
    RESTORE_VOLATILE 16
    blr x8
    SAVE_VOLATILE 16
    ldr x16,[sp,#176]
    ldrb w17,[sp,#184]
    strb w17,[x16,#\row]
    mov x0,x19
    ldr w1,[x19,#\layer]
    bl \register
    RESTORE_VOLATILE 16
    ldp x29,x30,[sp],#192
    ret
.endm
ROTATION_BIND aspect_preview_rotation_first, 0, 4, 0x278, aspect_preview_register_first
ROTATION_BIND aspect_preview_rotation_second, 1, 3, 0x1e8, aspect_preview_register_second
