#ifndef CSND_PRIVATE_SELECTOR_H
#define CSND_PRIVATE_SELECTOR_H
#include "private_worker.h"
enum csnd_selector_phase { CSND_UI_SCANNING=1,CSND_UI_LIST=2,CSND_UI_CONFIRM=3,CSND_UI_SAVING=4,CSND_UI_DONE=5,CSND_UI_CANCELED=6 };
typedef struct {
    uint32_t magic,generation,slot,card,phase,status,row,name_bytes;
    void *manager,*presenter;
    csnd_private_session *session;
    char selected_name[256];
    csnd_picker_list list;
    char display_names[CSND_PICKER_CAPACITY][129];
} csnd_selector;
csnd_selector *csnd_selector_create(void *manager,uint32_t generation,uint32_t slot,const uint8_t *media,uint32_t card);
int csnd_selector_poll(csnd_selector *);
int csnd_selector_select(csnd_selector *,uint32_t generation,uint32_t row);
int csnd_selector_confirm(csnd_selector *,uint32_t generation,uint32_t yes);
int csnd_selector_close(csnd_selector *);
int csnd_selector_model(csnd_selector *,void *presenter,size_t presenter_bytes);
const char *csnd_selector_row_name(const void *presenter,uint32_t row);
const char *csnd_selector_full_name(const csnd_selector *,uint32_t row);
int csnd_selector_copy_row_name(const void *presenter,uint32_t row,char out[129]);
/* Input is already validated core/picker metadata with n<=255 UTF8 bytes. */
void csnd_selector_project_name(char out[129],const char *name,size_t n);
#endif
