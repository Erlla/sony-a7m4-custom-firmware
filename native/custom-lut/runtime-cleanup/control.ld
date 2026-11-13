ENTRY(lut_widget_route)
PHDRS { code PT_LOAD FLAGS(5); state PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x9000000;
  lut_widget_module_anchor = .;
  .text : { KEEP(*(.text.lut_factory_entries)) *(.text*) } :code
  .rodata : { *(.rodata*) } :code
  ASSERT(. <= 0x9010000,"P3 AP RX overlaps aspect")
  . = 0x8f73000;
  .data : { *(.data*) } :state
  .bss : { *(.bss*) *(COMMON) *(.p4_control_state) } :state
  ASSERT(. <= 0x8f80000,"P3 AP state exceeds reserved RW")
  /DISCARD/ : { *(.comment*) *(.note*) *(.eh_frame*) }
}

native_app_owner_init = 0x1840398;
native_leaf_invalid = 0x35e62c8;
native_color_continue = 0x35f550c;
native_job_continue = 0x351a73c;
native_manager_continue = 0x1f05820;

factory_current_array = 0x802ce08;

factory_still_array = 0x802d120;

factory_movie_array = 0x802d438;

EXTERN(p3_factory_look_current p3_factory_look_still p3_factory_look_movie)

p4_runtime_submit = 0x9031000;
p4_runtime_poll = 0x9031004;
p4_runtime_snapshot = 0x9031008;
p4_runtime_candidates = 0x903100c;
p4_runtime_cancel = 0x9031010;
p4_runtime_owner_online = 0x9031014;
p4_runtime_desired_sequence = 0x9031018;
p4_runtime_owner_take_intent = 0x903101c;
p4_runtime_owner_request_load = 0x9031020;
p4_runtime_owner_take_lease = 0x9031024;
p4_runtime_owner_release_lease = 0x9031028;
p4_runtime_owner_complete = 0x903102c;
p4_runtime_owner_pause = 0x9031030;
p4_runtime_io_step = 0x9031034;
p4_runtime_signal_shutdown = 0x9031038;
p4_runtime_context_bytes = 0x903103c;
p4_gui_catalog = 0x9031040;
p4_gui_state_init = 0x9031044;
p4_gui_open = 0x9031048;
p4_gui_dispatch = 0x903104c;
p4_gui_exit = 0x9031050;
p4_gui_power = 0x9031054;
p4_gui_capture_begin = 0x9031058;
p4_gui_capture_existing = 0x903105c;
p4_gui_capture_end = 0x9031060;
p4_gui_before_view_destroy = 0x9031064;
p4_gui_after_view_create = 0x9031068;
p4_gui_render = 0x903106c;
p4_gui_render_overlay = 0x9031070;
p4_gui_status = 0x9031074;
p4_gui_text_factory = 0x9031078;
p4_gui_context_bytes = 0x903107c;

p4_gui_native_wait_progress = 0x9031080;
p4_gui_native_main_loop_continue = 0x1840cec;
lut_import_filename_original_text = 0x18c4788;

EXTERN(lut_widget_import_mode lut_widget_bias lut_widget_runtime_state lut_widget_refresh lut_ui_init lut_native_init lut_native_key lut_text_v617_bind lut_stock_numeric_resource)

EXTERN(p4_gui_native_loop_tail lut_import_filename_tail)
