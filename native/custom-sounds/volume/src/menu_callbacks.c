#include <stdint.h>
extern uint32_t csnd_volume_get(uint32_t);
extern int csnd_volume_enqueue(uint32_t,uint32_t),csnd_volume_blocked(uint32_t);
extern uint32_t csnd_previous_menu_blocked(uint32_t);
static uint32_t staged[2]; /* zero=committed, 1..10=setter's staged step */
static uint32_t getter(uint32_t s){uint32_t v=__atomic_load_n(staged+s,__ATOMIC_ACQUIRE);return (v?v:csnd_volume_get(s))-1;}
static void setter(uint32_t s,uint32_t raw){if(raw<10)__atomic_store_n(staged+s,raw+1,__ATOMIC_RELEASE);}
static int commit(uint32_t s,uint32_t alias){
 uint32_t base=5611+10*s;int result=1;
 if(alias>=base&&alias<base+10)result=csnd_volume_enqueue(s,alias-base+1);
 __atomic_store_n(staged+s,0,__ATOMIC_RELEASE);return result;
}
uint32_t csnd_volume_electronic_getter(void){return getter(0);}
uint32_t csnd_volume_focus_getter(void){return getter(1);}
void csnd_volume_electronic_setter(uint32_t raw){setter(0,raw);}
void csnd_volume_focus_setter(uint32_t raw){setter(1,raw);}
int csnd_volume_electronic_commit(uint32_t alias){return commit(0,alias);}
int csnd_volume_focus_commit(uint32_t alias){return commit(1,alias);}
int csnd_volume_electronic_available(void){return csnd_volume_blocked(0);}
int csnd_volume_focus_available(void){return csnd_volume_blocked(1);}
uint32_t csnd_volume_menu_blocked(uint32_t mid){if(mid==1598||mid==1599)return (uint32_t)csnd_volume_blocked(mid-1598);return csnd_previous_menu_blocked(mid);}
