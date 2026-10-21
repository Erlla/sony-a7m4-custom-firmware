csnd_cp_clean_buffer = 0x56ded8;
SECTIONS { .text 0xba5c80 : { *(.text*) *(.rodata*) } .bss 0x1564840 (NOLOAD) : { *(.bss*) } /DISCARD/ : { *(.comment*) *(.ARM.exidx*) *(.ARM.attributes*) } }
