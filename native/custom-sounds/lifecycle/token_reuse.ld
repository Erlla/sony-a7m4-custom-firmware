PHDRS { rx PT_LOAD FLAGS(5); }
SECTIONS {
 .text 0x904b000 : { *(.text*) *(.rodata*) } :rx
 ASSERT(. <= 0x9050000,"sound RX reservation exceeded")
 .data : { *(.data*) } :rx
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } :rx
 ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0,"no new persistent state")
 /DISCARD/ : { *(.eh_frame*) *(.comment*) }
}
private_parts_resume = 0x8fb5b88;
