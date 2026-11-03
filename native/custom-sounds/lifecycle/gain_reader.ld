SECTIONS {
 .text 0x11fe00 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x120000,"gain reader padding exceeded")
 .bss 0x1565000 (NOLOAD) : { *(.bss*) }
 ASSERT(SIZEOF(.bss)==0,"reader fix must not add state")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
