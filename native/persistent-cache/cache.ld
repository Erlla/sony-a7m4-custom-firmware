ENTRY(lut_read_cached)
PHDRS { rx PT_LOAD FLAGS(5); }
SECTIONS {
 . = 0x9048000;
 cache_anchor = .;
 .text : { *(.text*) } :rx
 .rodata : { *(.rodata*) } :rx
 ASSERT(. <= 0x9050000,"cache module exceeds existing RX reservation")
 .data : { *(.data*) } :rx
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } :rx
 ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0,"cache must not add mutable global state")
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
