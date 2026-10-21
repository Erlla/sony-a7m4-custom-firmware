.syntax unified
.arch armv7-a
.thumb
.section .text.owner_hooks,"ax",%progbits
.global csnd_cp_owner_router,csnd_cp_lookup_hook
.global csnd_cp_lookup_original,csnd_cp_exists_original,csnd_cp_start_original
.global csnd_cp_receive_hook
.global csnd_cp_validate_original
.thumb_func
csnd_cp_owner_router:
 push {r0-r3,r12,lr}
 mrs r2,apsr
 push {r2,r3}
 ldr r2,[r0,#12]
 movw r3,#0x5343
 movt r3,#0x4e53
 cmp r2,r3
 beq owner_private
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r3,r12,lr}
 push {r4-r7,lr}
 sub sp,#4
 b.w 0xba4b64
owner_private:
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r3,r12,lr}
 b.w csnd_cp_owner_reply
.thumb_func
csnd_cp_lookup_hook:
 mov r3,lr
 b.w csnd_cp_lookup
.thumb_func
csnd_cp_lookup_original:
 add.w r12,r0,#0x14
 b.w 0x5dff1c
.thumb_func
csnd_cp_exists_original:
 adds r0,#0x14
 movs r2,#0
 b.w 0x5dfe8a
.thumb_func
csnd_cp_start_original:
 push {r4-r7,lr}
 add r7,sp,#12
 b.w 0x5de0d2
.thumb_func
csnd_cp_validate_original:
 push {r4,r5,r7,lr}
 add r7,sp,#8
 b.w 0x18f91c
.thumb_func
csnd_cp_receive_hook:
 push {r0-r3,r12,lr}
 mrs r2,apsr
 push {r2,r3}
 ldr r1,[sp,#48] /* original AFF9F0 sp+16: native raw payload pointer */
 mov r2,r9
 bl csnd_cp_receive_capture
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r3,r12,lr}
 b.w 0xba4d60
