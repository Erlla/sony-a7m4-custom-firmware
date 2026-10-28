.syntax unified
.arch armv7-a
.thumb
.section .gates,"ax"
.macro gate name,target,stock
.global \name
.thumb_func
\name:
 push {r0,lr}
 ldr r0,=0x1565f08
 ldr r0,[r0]
 cmp r0,#1
 pop {r0,lr}
 bne 1f
 b.w \target
1:b.w \stock
.endm
gate admission_gate,admission_hook,admission_original
gate begin_gate,begin_hook,begin_original
gate app_admission_gate,app_admission_hook,app_admission_original
.global admission_original,begin_original,app_admission_original
.thumb_func
admission_original:
 push {r4,r5,r6,r7,lr}
 add r7,sp,#12
 b.w 0x5ddc28
.thumb_func
begin_original:
 push {r4,r5,r6,r7,lr}
 add r7,sp,#12
 b.w 0x5ddd0c
.thumb_func
app_admission_original:
 push {r4,r5,r6,r7,lr}
 add r7,sp,#12
 b.w 0x5dec78
.ltorg

.section .hooks,"ax"
.macro hook name,begin,stock
.global \name
.thumb_func
\name:
 push {r0-r3,ip,lr}
 movs r3,#\begin
 bl sound_handoff_admit
 cmp r0,#0
 pop {r0-r3,ip,lr}
 bne 1f
 b.w \stock
1:movs r0,#0
 bx lr
.endm
hook admission_hook,0,admission_original
hook begin_hook,1,begin_original
hook app_admission_hook,2,app_admission_original
