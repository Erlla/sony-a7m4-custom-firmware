ENTRY(aspect_capture_clone_copy)
SECTIONS {
 .text 0x11b700 : { *(.text*) *(.rodata*) }
 ASSERT(. <= 0x11c000, "Aspect clone exceeds its mapped zero area")
 .data : { *(.data*) }
 .bss (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(SIZEOF(.bss) == 0 && SIZEOF(.data) == 0, "No additional state")
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
