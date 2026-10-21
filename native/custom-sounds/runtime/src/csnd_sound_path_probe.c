/* Optional read-only mount-namespace diagnostic for an independently reviewed
 * future exporter. This file does not alter the frozen6.18/internal candidates. */
#include "csnd_sound_path_probe.h"
#include <stddef.h>
extern int csnd_find_first(const char *,void *);
extern void *memset(void *,int,size_t);
extern void *memcpy(void *,const void *,size_t);
int csnd_probe_sound_paths(const uint8_t *media,uint32_t card,void *scratch,uint32_t footer[4]) {
    static const char private_path[]="A:/PRIVATE/SONY/PRO/SOUNDS/CSND619.WAV";
    static const char sony_path[]="A:/SONY/PRO/SOUNDS/CSND619.WAV";
    char path[sizeof(private_path)];char letter;
    if(!footer)return 1;
    footer[0]=0x39504653;footer[1]=footer[2]=0xffffffffu;footer[3]=0;
    if(!media || card>1 || !scratch)return 1;
    letter=(char)media[card*0x70+0x19];
    if(letter<'A' || letter>'Z')return 10;
    memcpy(path,private_path,sizeof(private_path));path[0]=letter;
    memset(scratch,0,4096);footer[3]|=1;
    footer[1]=(uint32_t)csnd_find_first(path,scratch);
    memcpy(path,sony_path,sizeof(sony_path));path[0]=letter;
    memset(scratch,0,4096);footer[3]|=2;
    footer[2]=(uint32_t)csnd_find_first(path,scratch);
    return 0;
}
