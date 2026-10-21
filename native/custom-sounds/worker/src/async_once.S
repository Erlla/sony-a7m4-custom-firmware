.section .text.csnd_sysnd_async_once,"ax"
.global csnd_sysnd_async_once
csnd_sysnd_async_once:
// Offline candidate, not installed. w0 is an owned and registered Sysnd kind.
// Caller: dedicated sound worker, after fresh silent/shutter/focus policy checks.
// This function does not allocate or register resources, own a graph, or wait
// for playback completion. The native enqueue function still uses OS services.
// Result 1 means only that the native asynchronous request function returned.
// It does NOT mean accepted, played, completed, or safe to release a buffer.
cmp w0, #255
b.hi invalid
cbz w0, invalid
stp x29, x30, [sp, #-48]!
mov x29, sp
str w0, [sp, #32]
str wzr, [sp, #36]
str wzr, [sp, #40]
mov w8, #-1
str w8, [sp, #28]
add x0, sp, #32
add x1, sp, #28
bl csnd_native_sysnd_start
mov w0, #1
ldp x29, x30, [sp], #48
ret
invalid:
mov w0, #-3
ret
