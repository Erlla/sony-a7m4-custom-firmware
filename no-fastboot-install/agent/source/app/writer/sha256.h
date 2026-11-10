/* SHA-256, FIPS 180-4. No platform or library dependencies. */
struct Sha256 {u32 h[8];u64 bytes;u32 used;u8 block[64];};
static const u32 sha_k[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
static u32 rr(u32 x,u32 n){return (x>>n)|(x<<(32-n));}
static void sha_block(struct Sha256*s,const u8*b){
    u32 w[64];for(u32 i=0;i<16;i++)w[i]=((u32)b[i*4]<<24)|((u32)b[i*4+1]<<16)|((u32)b[i*4+2]<<8)|b[i*4+3];
    for(u32 i=16;i<64;i++){u32 x=w[i-15],y=w[i-2];w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));}
    u32 a=s->h[0],c=s->h[2],b0=s->h[1],d=s->h[3],e=s->h[4],f=s->h[5],g=s->h[6],h=s->h[7];
    for(u32 i=0;i<64;i++){u32 t=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+sha_k[i]+w[i];
        u32 z=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b0)^(a&c)^(b0&c));h=g;g=f;f=e;e=d+t;d=c;c=b0;b0=a;a=t+z;}
    s->h[0]+=a;s->h[1]+=b0;s->h[2]+=c;s->h[3]+=d;s->h[4]+=e;s->h[5]+=f;s->h[6]+=g;s->h[7]+=h;
}
static void sha_init(struct Sha256*s){
    const u32 initial[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    for(u32 i=0;i<8;i++)s->h[i]=initial[i];s->bytes=0;s->used=0;
}
static void sha_update(struct Sha256*s,const u8*b,u64 n){
    s->bytes+=n;while(n){u32 k=64-s->used;if(n<k)k=(u32)n;for(u32 i=0;i<k;i++)s->block[s->used+i]=b[i];
        s->used+=k;b+=k;n-=k;if(s->used==64){sha_block(s,s->block);s->used=0;}}
}
static void sha_final(struct Sha256*s,u8*out){
    u64 bits=s->bytes*8;s->block[s->used++]=0x80;
    if(s->used>56){while(s->used<64)s->block[s->used++]=0;sha_block(s,s->block);s->used=0;}
    while(s->used<56)s->block[s->used++]=0;for(u32 i=0;i<8;i++)s->block[56+i]=(u8)(bits>>(56-8*i));sha_block(s,s->block);
    for(u32 i=0;i<8;i++)for(u32 j=0;j<4;j++)out[i*4+j]=(u8)(s->h[i]>>(24-8*j));
}
__attribute__((noinline,visibility("default"))) void digest_bytes(const u8*b,u64 n,u8*out){
    struct Sha256 s;sha_init(&s);sha_update(&s,b,n);sha_final(&s,out);
}
