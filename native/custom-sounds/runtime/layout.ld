csnd_original_card_ctor = 0x8f90a00;
csnd_original_file_ctor = 0x8f90a08;
csnd_original_confirm_ctor = 0x8f90a10;
csnd_original_wait_ctor = 0x8f90a18;
csnd_original_card_dtor = 0x8f90a20;
csnd_original_file_dtor = 0x8f90a28;
csnd_original_confirm_dtor = 0x8f90a30;
csnd_original_wait_dtor = 0x8f90a38;
csnd_original_card_confirm = 0x8f90a40;
csnd_original_card_cancel = 0x8f90a48;
csnd_original_file_init = 0x8f90a50;
csnd_original_file_confirm = 0x8f90a58;
csnd_original_file_cancel = 0x8f90a60;
csnd_original_confirm = 0x8f90a68;
csnd_original_confirm_cancel = 0x8f90a70;
csnd_original_wait_tick = 0x8f90a78;
csnd_original_file_previous = 0x8f90a80;
csnd_original_file_next = 0x8f90a88;
csnd_original_row_event = 0x8f90a90;
csnd_original_file_snapshot = 0x8f90a98;
csnd_original_file_rec_notify = 0x8f90aa0;
csnd_original_file_half_press = 0x8f90aa8;
csnd_original_file_half_release = 0x8f90ab0;
csnd_original_file_aux_property = 0x8f90ab8;
csnd_original_confirm_rec_notify = 0x8f90ac0;
csnd_original_confirm_half_press = 0x8f90ac8;
csnd_original_confirm_half_release = 0x8f90ad0;
csnd_original_wait_rec_notify = 0x8f90ad8;
csnd_original_wait_half_press = 0x8f90ae0;
csnd_original_wait_half_release = 0x8f90ae8;
csnd_original_wait_cancel_command = 0x8f90af0;
csnd_original_wait_command_result = 0x8f90af8;
csnd_original_wait_media_result = 0x8f90b00;
csnd_original_wait_aux_status = 0x8f90b08;
csnd_original_wait_finish = 0x8f90b10;
csnd_original_wait_stop_command = 0x8f90b18;
csnd_original_wait_return_list = 0x8f90b20;
csnd_original_wait_return_request = 0x8f90b28;
csnd_pthread_self = 0x1718660;
csnd_native_media_get = 0x28ecd30;
csnd_native_controller_state = 0x1b302f8;
csnd_native_controller_set_state = 0x1b32de4;
csnd_native_manager_get = 0x3241cf0;
csnd_native_controller_arena = 0x7614430;
csnd_native_presenter_slots = 0x7614400;
csnd_native_file_presenter_vtable = 0x59984d8;
csnd_native_confirm_presenter_vtable = 0x5998530;
csnd_native_menu_mid = 0x28f18f0;
csnd_original_menu_route = 0x221c8d4;
csnd_native_submenu_presenter_vtable = 0x598c508;
csnd_original_submenu_render = 0x221e654;
csnd_native_menu_body = 0x1c023cc;
csnd_native_text_item = 0x1873510;
csnd_native_assign_text = 0x1856cfc;
csnd_native_dlsym = 0x17166a0;
csnd_sound_config_changed = 0x8f9c000;
csnd_sound_startup = 0x8f9c080;
csnd_original_menu_blocked = 0x8f91200;

csnd_pthread_self = 0x1718660;
csnd_native_media_get = 0x28ecd30;
csnd_native_controller_state = 0x1b302f8;
csnd_native_controller_set_state = 0x1b32de4;
csnd_native_manager_get = 0x3241cf0;
csnd_native_register = 0x3305084;

csnd_native_base_construct = 0x3158278;
csnd_native_base_destroy = 0x3156dd4;
csnd_native_sized_delete = 0x1716b60;
csnd_native_sequence_rtti = 0x59c1cc0;
csnd_native_empty_cancel = 0x3156acc;
csnd_native_empty_finish = 0x3156ad0;
ENTRY(csnd_ap_load_once)
/* No dynamic linking: source-bound imports are PC-relative direct branches.
 * The root builder installs RX bytes and zero-initializes the RW region.
 */
csnd_open = 0x1715170;
csnd_read = 0x1715270;
csnd_write = 0x17163c0;
csnd_close = 0x17173f0;
csnd_fsync = 0x17175b0;
csnd_rename = 0x1714e50;
csnd_mkdir = 0x1717fa0;
csnd_remove = 0x1716910;
csnd_errno = 0x1716f70;
csnd_malloc = 0x17152c0;
csnd_free = 0x1717810;
csnd_find_first = 0x3724718;
csnd_find_next = 0x3724748;
csnd_fsys_open = 0x3724654;
csnd_fsys_read = 0x3724688;
csnd_fsys_close = 0x3724674;
csnd_native_silent_get = 0x1c7328c;
csnd_native_audio_get = 0x1c4ce0c;
csnd_native_focus_get = 0x1c62774;
csnd_native_shutter_60a_get = 0x1c39f10;
csnd_native_shutter_60b_get = 0x1c39f88;
SECTIONS {
  . = 0x8f92000;
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  ASSERT(. <= 0x8f9c000, "AP runtime RX overlaps root exposure module")
  . = 0x8fc8000;
  .data : { *(.data .data.*) }
  .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
  ASSERT(. <= 0x8fc8800, "AP runtime metadata overlaps root exposure state")
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
