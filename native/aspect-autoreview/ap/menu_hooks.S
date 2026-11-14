.text
.p2align 2
.global aspect_ap_list_original
.type aspect_ap_list_original,%function
aspect_ap_list_original:
    /* Replay the list builder's displaced first instruction, then execute its
     * original complete stack frame and native option/model generation. */
    sub sp,sp,#0x830
    b native_list_body
.size aspect_ap_list_original,.-aspect_ap_list_original

.global aspect_ap_size_alias
.type aspect_ap_size_alias,%function
aspect_ap_size_alias:
    /* Native size-display users have four-entry tables. Custom choices use
     * the 3:2 backing image's resource; never index those tables with 4..7.
     * Preserve the original assertion for every other invalid alias. */
    mov w1,#5632
    sub w1,w0,w1
    cmp w1,#5
    b.hi 1f
    mov w0,#126
1:
    sub w0,w0,#126
    b native_size_alias_body
.size aspect_ap_size_alias,.-aspect_ap_size_alias

.global aspect_ap_option_apply
.type aspect_ap_option_apply,%function
aspect_ap_option_apply:
    stp x29,x30,[sp,#-32]!
    mov x29,sp
    str x19,[sp,#16]
    mov x19,x0
    mov w0,w1
    bl aspect_ap_before_apply
    mov w1,w0
    mov x0,x19
    ldr x19,[sp,#16]
    ldp x29,x30,[sp],#32
    /* Replay the displaced native prologue and tail-enter its unchanged body. */
    stp x29,x30,[sp,#-32]!
    b native_option_apply_body
.size aspect_ap_option_apply,.-aspect_ap_option_apply

.global aspect_ap_native_domain
.type aspect_ap_native_domain,%function
aspect_ap_native_domain:
    /* At the original accessor's RET, X0 already points to PRM_052B. This
     * covers old persisted 4..7 values before native readers dereference it.
     * Metadata/loading may write again later, so validate on every access. */
    /* The original leaf accessor leaves every other GPR and NZCV intact.
     * Preserve that stronger contract, including callers optimized locally. */
    stp x9,x10,[sp,#-16]!
    mrs x10,nzcv
    ldr w9,[x0]
    sub w9,w9,#4
    cmp w9,#5
    b.hi 1f
    str wzr,[x0]
1:  msr nzcv,x10
    ldp x9,x10,[sp],#16
    ret
.size aspect_ap_native_domain,.-aspect_ap_native_domain

.global aspect_ap_serializer_hook
.type aspect_ap_serializer_hook,%function
aspect_ap_serializer_hook:
    /* Replace only LDR W1,[X19,#8] at 35F9764. Preserve every other live
     * volatile integer register; the following CMP replaces NZCV. */
    sub sp,sp,#160
    stp x0,x1,[sp,#0]
    stp x2,x3,[sp,#16]
    stp x4,x5,[sp,#32]
    stp x6,x7,[sp,#48]
    stp x8,x9,[sp,#64]
    stp x10,x11,[sp,#80]
    stp x12,x13,[sp,#96]
    stp x14,x15,[sp,#112]
    stp x16,x17,[sp,#128]
    stp x18,x30,[sp,#144]
    ldr w0,[x19,#8]
    /* Native W1 must remain in0..3 through validation and logging. Freeze the
     * effective private choice in this invocation's unused frame slot instead
     * of leaking it into the native packet at the early switch. */
    str x0,[sp,#8]
    bl aspect_ap_effective
    str w0,[x29,#0x60]
    ldp x0,x1,[sp,#0]
    ldp x2,x3,[sp,#16]
    ldp x4,x5,[sp,#32]
    ldp x6,x7,[sp,#48]
    ldp x8,x9,[sp,#64]
    ldp x10,x11,[sp,#80]
    ldp x12,x13,[sp,#96]
    ldp x14,x15,[sp,#112]
    ldp x16,x17,[sp,#128]
    ldp x18,x30,[sp,#144]
    add sp,sp,#160
    ret
.size aspect_ap_serializer_hook,.-aspect_ap_serializer_hook

.global aspect_ap_serializer_send
.type aspect_ap_serializer_send,%function
aspect_ap_serializer_send:
    /* Only the final transport sees extended wire values. All native checks,
     * table lookups and packet logs have completed. No global reread here. */
    stp x9,x10,[sp,#-32]!
    mrs x10,nzcv
    ldr w9,[x29,#0x60]
    sub w9,w9,#4
    cmp w9,#5
    b.hi 1f
    add w9,w9,#5
    strb w9,[x1,#8]
1:
    msr nzcv,x10
    ldp x9,x10,[sp],#32
    /* The native BL still supplies its original LR; no probe frame remains. */
    b native_still_format_send
.size aspect_ap_serializer_send,.-aspect_ap_serializer_send

.global aspect_ap_option_register
.type aspect_ap_option_register,%function
aspect_ap_option_register:
    stp x29,x30,[sp,#-16]!
    mov x29,sp
    bl previous_option_register
    mov x0,x20
    bl aspect_register_options
    ldp x29,x30,[sp],#16
    ret
.size aspect_ap_option_register,.-aspect_ap_option_register

.global aspect_ap_option_parent_register
.type aspect_ap_option_parent_register,%function
aspect_ap_option_parent_register:
    stp x29,x30,[sp,#-16]!
    mov x29,sp
    bl previous_option_parent_register
    /* At173210C the real constructor retains this map in X20. */
    mov x0,x20
    bl aspect_register_parents
    ldp x29,x30,[sp],#16
    ret
.size aspect_ap_option_parent_register,.-aspect_ap_option_parent_register

.global aspect_ap_option_alias_register
.type aspect_ap_option_alias_register,%function
aspect_ap_option_alias_register:
    stp x29,x30,[sp,#-16]!
    mov x29,sp
    bl native_option_alias_register
    /* At1737974 this separate constructor retains its map in X19. */
    mov x0,x19
    bl aspect_register_aliases
    ldp x29,x30,[sp],#16
    ret
.size aspect_ap_option_alias_register,.-aspect_ap_option_alias_register

.global aspect_ap_option_gate
.type aspect_ap_option_gate,%function
aspect_ap_option_gate:
    mov w16,#5632
    sub w16,w0,w16
    cmp w16,#5
    b.ls 1f
    b previous_option_gate
1:
    mov w0,#1
    ret
.size aspect_ap_option_gate,.-aspect_ap_option_gate
