SECTIONS { .text 0x8fb8000 : { *(.text*) *(.rodata*) } .data 0x8fff000 : { *(.data*) } .bss (NOLOAD) : { *(.bss*) } /DISCARD/ : { *(.eh_frame*) *(.comment*) *(.note*) } }
csnd_open = 0x1715170;
csnd_read = 0x1715270;
csnd_write = 0x17163c0;
csnd_close = 0x17173f0;
csnd_fsync = 0x17175b0;
csnd_rename = 0x1714e50;
csnd_mkdir = 0x1717fa0;
csnd_remove = 0x1716910;
csnd_errno = 0x1716f70;
ss_crc32 = 0x8f9902c;
csnd_ap_import_available = 0x8f927f8;
csnd_previous_menu_blocked = 0x8f983f0;
