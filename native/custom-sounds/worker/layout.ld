SECTIONS {
 .main 0x8fb0000 : { *event.o(.text.event_start) *(.text*) *(.rodata*) }
 ASSERT(. <= 0x8fb8000, "worker exceeds its private extension; menu owns8FB8000 onward")
 . = 0x8ff7000;
 .data : { *(.data*) }
 .bss (NOLOAD) : { *(.bss*) *(COMMON) }
 ASSERT(. <= 0x8ff8000, "worker exceeds4KiB state; menu starts8FF8000")
 /DISCARD/ : { *(.comment*) *(.eh_frame*) *(.note*) }
}
csnd_original_crc32 = 0x8f9902c;
ss_crc32 = 0x8f9902c;
csnd_ap_import_available = 0x8f927f8;
csnd_native_sysnd_start = 0x359b41c;
csnd_malloc = 0x17152c0;
csnd_free = 0x1717810;
csnd_open = 0x1715170;
csnd_read = 0x1715270;
csnd_write = 0x17163c0;
csnd_close = 0x17173f0;
csnd_fsync = 0x17175b0;
csnd_rename = 0x1714e50;
csnd_remove = 0x1716910;
csnd_mkdir = 0x1717fa0;
csnd_errno = 0x1716f70;
csnd_volume_worker_tick = 0x8fb8000;
csnd_volume_get = 0x8fb84a0;
csnd_volume_blocked = 0x8fb84cc;
csnd_volume_enqueue = 0x8fb84fc;
