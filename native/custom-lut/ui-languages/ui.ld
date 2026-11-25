ENTRY(lut_localized_stock_bind)
PHDRS { code PT_LOAD FLAGS(5); }
SECTIONS {
  . = 0x904d000;
  .text : { *(.text*) *(.rodata*) } :code
  /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
lut_widget_bias = 0x9002a80;
lut_widget_runtime_state = 0x8f73000;
lut_text_v617_bind = 0x9000d54;
lut_gauge_parameter_bind = 0x900084c;
lut_stock_numeric_list_bind = 0x90008c0;
lut_name_v617_copy = 0x90009e0;
lut_text_v617_title = 0x9000e48;
lut_text_v617_strength_title = 0x9000e60;
p4_gui_status = 0x9031074;
lut_existing_gui_context = 0x9050098;
