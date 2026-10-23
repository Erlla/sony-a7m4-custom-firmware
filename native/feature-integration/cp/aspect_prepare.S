
.syntax unified
.arch armv7-a
.thumb
.section .aspect_prepare,"ax",%progbits
.global aspect_boot_zero
.type aspect_boot_zero,%function
.thumb_func
aspect_boot_zero:
 movw r0,#0xd000
 movt r0,#0x11
 movw r1,#0x400
 ldr r2,=0x5866ac
 bx r2
.size aspect_boot_zero,.-aspect_boot_zero
.global aspect_boot_map
.type aspect_boot_map,%function
.thumb_func
aspect_boot_map:
 push {r4,lr}
 sub sp,#16
 ldr r4,=0x1565ef0
 ldr r1,[r4]
 cmp r1,#1
 bne 1f
 movw r1,#0xb000
 movt r1,#0x11
 movw r2,#0x2000
 mov r3,r1
 movs r4,#15
 str r4,[sp]
 movs r4,#0
 str r4,[sp,#4]
 mvn r4,#0
 str r4,[sp,#8]
 ldr r4,=0x5821c8
 blx r4
 cmp r0,#0
 bne 1f
 ldr r4,=0x1565f0c
 movs r0,#1
 dmb ish
 str r0,[r4]
 dmb ish
1:
 add sp,#16
 pop {r4,pc}
.size aspect_boot_map,.-aspect_boot_map
.ltorg
