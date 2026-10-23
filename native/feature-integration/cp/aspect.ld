ENTRY(aspect_resident_gate)
SECTIONS {
 .aspect_rx 0x11b000 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x11d000,"Aspect RX exceeds reserved zero pages")
 .aspect_bss 0x11d000 (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(. <= 0x11d400,"Aspect RW exceeds explicit zero range")
 .aspect_prepare 0xba5284 : { *(.aspect_prepare) }
 ASSERT(. <= 0xba5300,"Prepare overlaps LUT owner")
 .aspect_gate 0xba54b0 : { *(.aspect_gate) }
 ASSERT(. <= 0xba5640,"Gate overlaps RAW/AF")
 .boot_wrapper 0xba5740 : { *(.boot_wrapper) }
 ASSERT(. <= 0xba5900,"BOOT overlaps codec")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
native_runtime_map = 0x5821c8;
