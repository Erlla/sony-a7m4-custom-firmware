.text
.global private_parts_original
.type private_parts_original,%function
private_parts_original:
 sub sp,sp,#0x80
 b private_parts_resume
.size private_parts_original,.-private_parts_original
