SECTIONS {
 .text 0x901f000 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x9020000,"Review fit exceeds existing RX reservation")
 /DISCARD/ : { *(.eh_frame*) *(.comment*) *(.note*) }
}
native_review_layout = 0x35994dc;
