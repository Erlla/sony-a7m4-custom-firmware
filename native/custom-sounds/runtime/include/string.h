#ifndef CSND_FREESTANDING_STRING_H
#define CSND_FREESTANDING_STRING_H
#include <stddef.h>
void *memcpy(void *,const void *,size_t);
void *memset(void *,int,size_t);
int memcmp(const void *,const void *,size_t);
#endif
