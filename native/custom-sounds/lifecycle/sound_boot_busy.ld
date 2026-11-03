SECTIONS {
 .text 0x11fc00 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x120000,"sound page padding exceeded")
 .bss (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(SIZEOF(.bss) == 0,"no additional sound state")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
