#include <stddef.h>
void *memcpy(void*d,const void*s,size_t n){unsigned char*p=d;const unsigned char*q=s;while(n--)*p++=*q++;return d;}
void *memset(void*d,int v,size_t n){unsigned char*p=d;while(n--)*p++=(unsigned char)v;return d;}
