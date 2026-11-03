PHDRS { rx PT_LOAD FLAGS(5); } SECTIONS { .text 0x904a000 : { *(.text*) *(.rodata*) } :rx ASSERT(. <= 0x9050000,"RX limit") .data : { *(.data*) } :rx .bss (NOLOAD) : { *(.bss*) *(COMMON) } :rx ASSERT(SIZEOF(.bss)==0 && SIZEOF(.data)==0,"no new state") /DISCARD/ : { *(.eh_frame*) *(.comment*) } }
stop_barrier_original = 0x8fb51dc;
cp_start_original = 0x8fb4dfc;
cp_reply_original = 0x8fb4b18;
stop_async_original = 0x8fb6624;
hold_original = 0x8fb4048;
phase_original = 0x8fb27f4;
