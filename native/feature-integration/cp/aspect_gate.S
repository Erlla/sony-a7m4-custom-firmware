.syntax unified
.arch armv7-a
.thumb
.section .aspect_gate,"ax",%progbits
.balign 4
.global aspect_resident_gate
.type aspect_resident_gate,%function
.thumb_func
aspect_resident_gate:
    /* Twelve replaced sites identify themselves by LR. Preserve all live
     * registers and APSR; select reviewed prefix code only after its RAM CRC
     * and executable mapping have been accepted by the existing resident guard.
     */
    sub sp,#8
    push.w {r0-r3,r12,lr}
    mrs r0,apsr
    push {r0,r4}
    ldr r1,[sp,#28]
    adr r2,.Ltargets
    movs r3,#12
1:  ldr r0,[r2]
    cmp r0,r1
    beq 2f
    adds r2,#12
    subs r3,#1
    bne 1b
    /* A foreign call cannot execute arbitrary prefix memory. Return safely. */
    mov r2,r1
    b 4f
2:  movw r0,#0x5f0c
    movt r0,#0x156
    ldr r0,[r0]
    cmp r0,#1
    bne 3f
    dmb ish
    ldr r2,[r2,#4]
    b 4f
3:  ldr r2,[r2,#8]
4:  str r2,[sp,#32]
    pop {r0,r4}
    msr apsr_nzcvqg,r0
    pop.w {r0-r3,r12,lr}
    ldr.w pc,[sp],#8
.balign 4
.Ltargets:
    .word 0x3061cf,aspect_cp_select_hook,aspect_cold_selector
    .word 0xa049b5,aspect_freeze_copy,0x585fb8
    .word 0xa03147,aspect_capture_copy,0x3ed2b9
    .word 0x40511f,aspect_jpeg_copy_hook,0x585fb8
    .word 0xa0d017,aspect_notify_primary_hook,0x41d62d
    .word 0xa0d061,aspect_notify_secondary_hook,0x41d62d
    .word 0xa0d25f,aspect_notify_release_hook,aspect_cold_release
    .word 0xa0d0ed,aspect_heif_packet_hook,0x5861f8
    .word 0x404637,aspect_jpeg_copy_hook,0x585fb8
    .word 0x400e2b,aspect_thumbnail_clear_hook,0x5866ac
    .word 0xa06189,aspect_pool_release,0xa0623d
    .word 0x3f4a4d,aspect_pool_reset_hook,aspect_cold_pool_reset
.size aspect_resident_gate,.-aspect_resident_gate

.type aspect_cold_selector,%function
.thumb_func
aspect_cold_selector:
    push {r0,r2}
    mrs r2,apsr
    subs r0,r1,#5
    cmp r0,#3
    ite ls
    movls r0,#2
    movhi r0,r1
    str.w r0,[r5,#0xa8]
    msr apsr_nzcvqg,r2
    pop {r0,r2}
    bx lr

.type aspect_cold_release,%function
.thumb_func
aspect_cold_release:
    mov.w r5,#0x5480
    bx lr

.type aspect_cold_pool_reset,%function
.thumb_func
aspect_cold_pool_reset:
    movs r2,#0
    str r2,[r0]
    bx lr
