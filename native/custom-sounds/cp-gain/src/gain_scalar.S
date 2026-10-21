.syntax unified
.arch armv7-a
.thumb
.text
.global csnd_custom_gain_hook
.thumb_func
csnd_custom_gain_hook:
 push {r0-r12,lr}
 mrs r2,apsr
 push {r2,r3}
 ldrb r0,[r5,#4]
 ldrb r1,[r5,#5]
 add r2,sp,#264 /* original1905B0 SP +200 == PIN/CLIP descriptor SP+0x60 */
 ldr r3,[sp,#164] /* original1905B0 saved caller LR at originalSP+100 */
 bl csnd_custom_gain_scalar
 strb r0,[sp,#68] /* displaced original STRB [originalSP,#4] */
 str r0,[sp,#8] /* original displaced LDRB result; all other registers exact */
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r12,lr}
 b.w 0x1905ea
