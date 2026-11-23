ENTRY(pad_shutter)
PHDRS { rx PT_LOAD FLAGS(5); }
SECTIONS {
 . = 0x9048e00;
 pad_anchor = .;
 .text : { *(.text*) *(.rodata*) } :rx
 ASSERT(. <= 0x9049000, "shutter padding exceeds mapped RX gap")
 .data : { *(.data*) } :rx
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } :rx
 ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0, "no global storage")
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
original = 0x8fb5d7c;
