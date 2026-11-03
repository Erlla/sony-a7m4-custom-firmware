PHDRS { rx PT_LOAD FLAGS(5); } SECTIONS { .text 0x9049000 : { *(.text*) *(.rodata*) } :rx ASSERT(. <= 0x9050000,"RX limit") .data : { *(.data*) } :rx .bss (NOLOAD) : { *(.bss*) *(COMMON) } :rx ASSERT(SIZEOF(.bss)==0 && SIZEOF(.data)==0,"no new state") /DISCARD/ : { *(.eh_frame*) *(.comment*) } }
meta_original = 0x8fb0fd4;
matches_original = 0x8fb1070;
phase_original = 0x8fb27f4;
unready_original = 0x8fb4ef0;
