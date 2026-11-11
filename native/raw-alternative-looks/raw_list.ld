ENTRY(raw_list_construct)
SECTIONS {
  .raw_constructor 0xba4960 : { *(.raw_constructor) }
  .raw_mapping 0x9ff8a4 : { *(.raw_mapping) }
  .raw_quantity 0x9ff8e0 : { *(.raw_quantity) }
  /DISCARD/ : { *(.comment*) *(.ARM.exidx*) *(.ARM.extab*) *(.note*) }
}
