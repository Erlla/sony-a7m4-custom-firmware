.syntax unified
.arch armv7-a
.thumb
.text
.global csnd_driver_entry_hook,csnd_driver_exit_hook
.global csnd_cp_owner_reply_original
.thumb_func
csnd_cp_owner_reply_original:
 b.w 0xba5ebc
.thumb_func
csnd_driver_entry_hook:
 push {r0-r12,lr}
 mrs r2,apsr
 push {r2,r3}
 add r0,sp,#64
 bl csnd_driver_pre
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r12,lr}
 /* Exact displaced original prologue A56BB2..A56BB6. */
 push {r4,r6,r7,lr}
 add r7,sp,#8
 b.w 0xa56bb6
.thumb_func
csnd_driver_exit_hook:
 push {r0-r12,lr}
 mrs r2,apsr
 push {r2,r3}
 add r0,sp,#88 /* entrySP = native epilogue SP +24 */
 mov r1,r4
 bl csnd_driver_post
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r12,lr}
 /* Exact displaced A56C50..A56C54, with original pop preserved. */
 mov r0,r4
 add sp,#8
 pop {r4,r6,r7,pc}
