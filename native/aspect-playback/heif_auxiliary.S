// The native HEIF item association walker has already selected the ISPE
// of a thmb reference to the primary. Check only CP-produced dimensions.
.text
.balign 4
.Lbase:
.global auxiliary
auxiliary:
    cmp w0, #1080
    b.eq .Lscreen
    cmp w1, #1920
    b.eq .Lscreen
    adr x9, .Lsizes
    mov w10, #6
.Lloop:
    ldp w11, w12, [x9], #8
    cmp w1, w11
    ccmp w0, w12, #0, eq
    b.eq .Lscreen
    subs w10, w10, #1
    b.ne .Lloop
    // Four wide ratios retain the native 320-pixel thumbnail test.
    // Narrow ratios also crop the 320 x 212 thumbnail canvas.
    cmp w0, #208
    b.ne .Lunknown
    cmp w1, #256
    b.eq .Lthumb
    cmp w1, #240
    b.eq .Lthumb
.Lunknown:
    b .Lbase + (0x2683d0 - 0x470600)
.Lthumb:
    b .Lbase + (0x268380 - 0x470600)
.Lscreen:
    b .Lbase + (0x2683bc - 0x470600)
.Lsizes:
    .word 1616,568, 1616,600, 1344,1080, 1264,1080, 1616,696, 1616,688
