ENTRY(aspect_native_still_size)
SECTIONS { .text 0x904c000 : { *(.text*) } /DISCARD/ : { *(.eh_frame*) *(.comment*) } }
native_still_size_body = 0x2e29230;
