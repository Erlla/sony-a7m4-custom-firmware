// libheif::get has filled get_if_t with HEIF primary dimensions and CamMetaInfo.
// Reconcile the output record before the saved x19/x20 are restored.
.text
.p2align 2
.Lstart:
    ldr     x8, [x19, #8]
    cbz     x8, .Lreturn
    ldrb    w9, [x8]
    cbz     w9, .Lreturn
    add     x9, x19, #0x3b4
    ldr     x9, [x9]                   // width and height, two native u32s
    adr     x10, .Lpairs
    mov     w11, #18
.Lnext:
    ldr     x12, [x10], #8
    cmp     x9, x12
    b.eq    .Lknown
    subs    w11, w11, #1
    b.ne    .Lnext
    b       .Lreturn
.Lknown:
    ldur    x12, [x8, #4]
    cmp     x9, x12
    b.eq    .Llayout
    // The existing dimension table is sorted in three six-entry groups (S, M, L).
    // Only replace metadata bearing the corresponding uncut source size.
    mov     w13, #0
    cmp     w11, #12
    cinc    w13, w13, ls
    cmp     w11, #6
    cinc    w13, w13, ls
    adr     x14, .Luncut
    ldr     x14, [x14, w13, uxtw #3]
    cmp     x14, x12
    b.ne    .Lreturn
    stur    x9, [x8, #4]
.Llayout:
    ldrb    w10, [x8, #0xc]
    cbnz    w10, .Lreturn
    mov     w10, #1
    strb    w10, [x8, #0xc]
    str     wzr, [x8, #0x10]           // Project's existing basic still layout
.Lreturn:
    ldp     x19, x20, [sp, #0x10]      // displaced epilogue instruction
    b       .Lresume
.p2align 3
.Luncut:
    .word 3504, 2336, 4608, 3072, 7008, 4672
.set .Lpairs, .Lstart - 0x90            // existing JPEG dimension table
.set .Lresume, .Lstart + 0x270288 - 0x4704e8
