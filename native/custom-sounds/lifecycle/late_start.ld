csnd_cp_owner = 0x1564840;
SECTIONS {
 .text 0x11fcc0 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x120000,"sound page padding exceeded")
 .bss (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(SIZEOF(.bss)==0,"no additional sound state")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
