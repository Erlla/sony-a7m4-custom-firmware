.syntax unified
.arch armv7-a
.thumb
.section .text.fallback,"ax"
.global owner_start_fallback
.thumb_func
owner_start_fallback:
 push {r3,r4,r5,r6,r7,lr}
 mov r6,r0
 b.w 0x11e888
