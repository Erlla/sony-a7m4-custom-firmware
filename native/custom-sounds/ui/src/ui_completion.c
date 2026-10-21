#include <stdint.h>
extern int csnd_old_electronic_commit(uint32_t),csnd_old_focus_commit(uint32_t);
extern int csnd_menu_request_status(uint32_t,uint32_t*,uint32_t*);
extern int csnd_original_event(void*,void*,uint32_t);
extern uint32_t *csnd_parent_parameter(void);
extern void csnd_original_profile_update(void*,uint32_t);
extern void csnd_original_parent_refresh(void*,void*);
static uint32_t pending[2]; /* GUI thread only. Does not publish playback readiness. */
int csnd_ui_electronic_commit(uint32_t alias){int r=csnd_old_electronic_commit(alias);if(!r)pending[0]=1;return r;}
int csnd_ui_focus_commit(uint32_t alias){int r=csnd_old_focus_commit(alias);if(!r)pending[1]=1;return r;}
int csnd_ui_event(void *controller,void *message,uint32_t code){
 int result=csnd_original_event(controller,message,code);
 if(code!=0x20f0000u||!controller||*(uint32_t*)((uint8_t*)controller+0x178)!=0x2d7)return result;
 uint32_t parent=*csnd_parent_parameter(),slot;
 if(parent==1592)slot=0;else if(parent==1595)slot=1;else return result;
 if(!pending[slot])return result;
 uint32_t queued=1,status=0xffffffffu;
 if(csnd_menu_request_status(slot,&queued,&status)||queued)return result;
 /* Completion is consumed on this GUI event, including a failed durable save:
  * original committed getter/availability restore the authoritative old value.
  * No setting IO, re-entrant worker, navigation request, or fake key event. */
 pending[slot]=0;
 csnd_original_profile_update(controller,parent+1);
 csnd_original_profile_update(controller,parent+2);
 csnd_original_profile_update(controller,1598+slot);
 csnd_original_parent_refresh(controller,message);
 return result;
}
