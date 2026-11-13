ENTRY(p4x_submit)
PHDRS { rx PT_LOAD FLAGS(5); rw PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x9030000;
  .p4_phdr : { BYTE(0); . = 0x9031000; } :rx
  .p4_exports : { KEEP(*(.p4_exports)) } :rx
  ASSERT(SIZEOF(.p4_exports) == 132, "P4 stable ABI export table changed")
  .text : { *(.text .text.*) } :rx
  .rodata : { *(.rodata .rodata.*) } :rx
  ASSERT(. <= 0x9050000, "P4 RX exceeds explicit 128KiB reservation")
  . = 0x9050000;
  .data : { *(.data .data.*) } :rw
  .bss (NOLOAD) : { *(.bss .bss.* COMMON) } :rw
  ASSERT(. <= 0x9051000, "P4 fixed RW exceeds 4KiB; contexts belong on proven heap")
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) *(.ARM.exidx*) }
}

lut_widget_import_mode = 0x9002a98;
lut_widget_bias = 0x9002a80;
lut_widget_runtime_state = 0x8f73000;
lut_widget_refresh = 0x9003af4;
lut_ui_init = 0x90019fc;
lut_native_init = 0x9000e78;
lut_native_key = 0x9001074;
lut_text_v617_bind = 0x9000d54;
lut_stock_numeric_resource = 0x90008a0;
