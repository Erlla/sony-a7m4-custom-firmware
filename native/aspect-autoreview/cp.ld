SECTIONS {
 .text 0x11b800 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x11c000,"Aspect extension overlaps grid code")
 .resident 0xba5fd8 : { *(.resident) }
 ASSERT(. <= 0xba6000,"Resident padding exceeded")
 .bss 0x11d000 (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(. <= 0x11d400,"Aspect state reservation exceeded")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
native_prereview_formatter = 0x424019;
