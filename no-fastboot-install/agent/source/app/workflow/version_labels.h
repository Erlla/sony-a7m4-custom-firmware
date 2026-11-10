/* Only encoding and agreement are checked; no release number is selected. */
static int m4_versions_consistent(u64 bcd,u64 api) {
    if(!bcd || bcd>0x9999 || api>0xffffffffUL)return 0;
    u64 a=(bcd>>12)&15,b=(bcd>>8)&15,c=(bcd>>4)&15,d=bcd&15;
    if(a>9 || b>9 || c>9 || d>9)return 0;
    return api==(((a*10+b)<<16)|(c*10+d));
}
