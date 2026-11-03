.syntax unified
.arch armv7-a
.thumb
.text
.global gain_acquire_hook
.thumb_func
gain_acquire_hook:
 push {r1-r3,lr}
 mov r0,r3
 bl gain_reader_acquire
 mov r7,r0
 cmp r0,#1
 pop {r1-r3,pc}

.global gain_release_hook
.thumb_func
gain_release_hook:
 push {r0-r3,r12,lr}
 add.w r0,r3,#0x840
 bl gain_reader_release
 pop {r0-r3,r12,pc}
