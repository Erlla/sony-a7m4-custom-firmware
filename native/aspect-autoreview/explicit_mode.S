.text
.p2align 2
.global aspect_review_explicit_mode
.type aspect_review_explicit_mode,%function
aspect_review_explicit_mode:
    /* Replace R3's LDRB W10,[X10,#4] at901F0F0. This is the temporary
     * geometry entry's auto/manual field. Only R3's custom-image fit reaches
     * here. MOV preserves NZCV for the following native compiler CSELs.
     */
    mov w10,wzr
.size aspect_review_explicit_mode,.-aspect_review_explicit_mode
