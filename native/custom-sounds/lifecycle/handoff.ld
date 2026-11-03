SECTIONS {
 .gates 0xba55e0 : { *(.gates) }
 ASSERT(. <= 0xba5640,"resident gate reservation exceeded")
 .hooks 0x11fb00 : { *(.hooks) }
 ASSERT(. <= 0x11fc00,"optional hook reservation exceeded")
 .text 0x11ea10 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x11f000,"owner page padding exceeded")
 .resgate 0xba58c0 : { *(.resgate) }
 ASSERT(. <= 0xba5900,"resident reservation gate exceeded")
 .reservation 0x11fb54 : { *(.reservation) }
 ASSERT(. <= 0x11fc00,"reservation helper exceeded")
 .bss 0x1564a84 (NOLOAD) : { *(.bss*) }
 ASSERT(. <= 0x1565000,"sound BSS padding exceeded")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
