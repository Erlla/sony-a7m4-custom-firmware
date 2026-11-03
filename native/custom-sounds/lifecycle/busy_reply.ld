SECTIONS {
 .text 0x11ff00 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x120000, "sound page limit")
 .data : { *(.data*) }
 .bss (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "no new state")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
