ENTRY(aspect_jpeg_layout)
SECTIONS { .text 0x470400 : { *(.text*) } /DISCARD/ : { *(.eh_frame*) *(.comment*) } }
native_jpeg_ana_resume = 0x272134;
