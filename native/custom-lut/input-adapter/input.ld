ENTRY(lut_input_dispatch)
PHDRS { code PT_LOAD FLAGS(5); }
SECTIONS {
  . = 0x904fc00;
  .text : { *(.text*) *(.rodata*) } :code
  /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
current_lut_scene = 0x8f73030;
existing_gui_dispatch = 0x903e5e0;
