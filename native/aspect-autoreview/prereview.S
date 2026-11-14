.syntax unified
.arch armv7-a
.thumb
.text
.balign 4
.global aspect_prereview_formatter
.type aspect_prereview_formatter,%function
.thumb_func
aspect_prereview_formatter:
    /* Both replaced instructions were BL424018. Stack arguments retain their
     * original position for the tail call and LR retains the native return.
     * Main review keeps task in R10; SCN review keeps task in R4.
     */
    push {r0-r3,r12,lr}
    mov r1,r10
    ldr r2,[sp,#20]
    ldr r3,=0x40d40b
    cmp r2,r3
    it eq
    moveq r1,r4
    add r0,sp,#24
    bl aspect_prereview_arguments
    pop {r0-r3,r12,lr}
    ldr.w pc,=0x424019
.size aspect_prereview_formatter,.-aspect_prereview_formatter
.ltorg

.section .resident,"ax",%progbits
.balign 4
.global aspect_prereview_resident
.type aspect_prereview_resident,%function
.thumb_func
aspect_prereview_resident:
    /* Reuse the existing release-published P3 CRC/mapping readiness. */
    push {r0,r1}
    ldr r0,=0x1565f0c
    ldr r0,[r0]
    cmp r0,#1
    pop {r0,r1}
    bne 1f
    dmb ish
    b.w aspect_prereview_formatter
1:  ldr.w pc,=0x424019
.size aspect_prereview_resident,.-aspect_prereview_resident
.ltorg
