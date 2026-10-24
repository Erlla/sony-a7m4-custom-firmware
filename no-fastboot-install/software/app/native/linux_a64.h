/* Fixed AArch64 Linux ABI helpers. No libc or external symbol dependencies. */
typedef unsigned long u64;
typedef long i64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
/* arm64 overrides these four asm-generic flags (Linux UAPI asm/fcntl.h).
 * Octal spellings deliberately match the architecture header. */
enum { A64_O_DIRECTORY=040000, A64_O_NOFOLLOW=0100000, A64_O_DIRECT=0200000,
       A64_O_LARGEFILE=0400000, A64_O_CLOEXEC=02000000,
       A64_READ=A64_O_CLOEXEC|A64_O_NOFOLLOW,
       A64_DIRECTORY=A64_READ|A64_O_DIRECTORY,
       A64_CREATE=A64_READ|000001|000100|000200 };
_Static_assert(A64_READ==0x88000 && A64_DIRECTORY==0x8c000 && A64_CREATE==0x880c1,"AArch64 open flags");
static i64 sc(i64 no,i64 a,i64 b,i64 c,i64 d,i64 e,i64 f) {
    register i64 x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
    register i64 x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f,x8 __asm__("x8")=no;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8) : "memory","cc");
    return x0;
}
static i64 op(const char*p,i64 flags,i64 mode) {return sc(56,-100,(i64)p,flags,mode,0,0);}
static i64 cl(i64 fd) {return sc(57,fd,0,0,0,0,0);}
static i64 unlink(const char*p) {return sc(35,-100,(i64)p,0,0,0,0);}
static i64 write_all(i64 fd,const void*data,u64 n) {
    u64 done=0;u32 calls=0;
    while(done<n && ++calls<=256) {
        i64 r=sc(64,fd,(i64)((const u8*)data+done),n-done,0,0,0);
        if(r==-4)continue;
        if(r<=0 || (u64)r>n-done)return r<0?r:-5;
        done+=(u64)r;
    }
    return done==n?0:-11;
}
static i64 save_new(const char*p,const void*data,u64 n,i64 mode) {
    i64 fd=op(p,A64_CREATE,mode);if(fd<0)return fd;
    i64 r=write_all(fd,data,n),c=cl(fd);return r?r:c;
}
static i64 read_all(const char*p,u8*out,u64 capacity) {
    i64 fd=op(p,A64_READ,0);if(fd<0)return fd;
    u64 done=0;u32 calls=0;i64 result=-75;
    while(done<capacity && ++calls<=256) {
        i64 r=sc(63,fd,(i64)(out+done),capacity-done,0,0,0);
        if(r==-4)continue;
        if(r<0) {result=r;break;}
        if(!r) {result=(i64)done;break;}
        if((u64)r>capacity-done) {result=-5;break;}
        done+=(u64)r;
    }
    i64 c=cl(fd);return c?c:result;
}
static int same(const u8*a,const u8*b,u64 n) {for(u64 i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static int contains(const u8*buf,u64 n,const char*needle,u64 length) {
    for(u64 i=0;i+length<=n;i++)if(same(buf+i,(const u8*)needle,length))return 1;
    return 0;
}
static u32 decimal(char*out,u64 number) {
    char rev[24];u32 n=0;
    do {rev[n++]=(char)('0'+number%10);number/=10;} while(number && n<sizeof(rev));
    for(u32 i=0;i<n;i++)out[i]=rev[n-1-i];out[n]=0;return n;
}
struct Fs {i64 type,bsize,blocks,bfree,bavail,files,ffree;u64 fsid; i64 namelen,frsize,flags,spare[4];};
_Static_assert(sizeof(struct Fs)==120,"AArch64 statfs ABI");
static i64 tmpfs(struct Fs*fs) {
    i64 r=sc(43,(i64)"/tmp_wbshd",(i64)fs,0,0,0,0);
    if(r)return r;
    if(fs->type!=0x1021994 || fs->bsize<=0 || fs->bsize>1048576 ||
       fs->bavail<0 || fs->bavail>(1L<<43) || (fs->flags&8))return -22;
    if((u64)fs->bsize*(u64)fs->bavail<8*1024*1024)return -28;
    return 0;
}
static void exit_child(i64 code) {sc(94,code,0,0,0,0,0);for(;;){} }
