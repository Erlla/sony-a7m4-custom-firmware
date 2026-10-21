/* Private GUI-owned selector, backed exclusively by private native jobs.
 * No original CLUT parameter/name/list/cache is written. Native UI lifecycle
 * hook installation is a distinct gate; this never sets picker_ready. */
#include "private_selector.h"
extern void *csnd_malloc(size_t);
extern void csnd_free(void *);
extern void *memcpy(void *,const void *,size_t);
extern void *memset(void *,int,size_t);
static csnd_selector *model_owner;
static uint32_t model_gate;
static const char default_name[]="默认";
static int valid(const csnd_selector *c){return c && c->magic==0x53475549 && c->session && c->generation==c->session->generation;}
static void model_enter(void) {
    uint32_t expected;
    do {expected=0;} while(!__atomic_compare_exchange_n(&model_gate,&expected,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED));
}
static void model_leave(void){__atomic_store_n(&model_gate,0,__ATOMIC_RELEASE);}
void csnd_selector_project_name(char out[129],const char *name,size_t n) {
    size_t cut=n;
    memset(out,0,129);
    if(n>128){cut=125;while(cut && (((uint8_t)name[cut]&0xc0)==0x80))--cut;}
    memcpy(out,name,cut);
    if(n>128)memcpy(out+cut,"...",3);
}
csnd_selector *csnd_selector_create(void *manager,uint32_t generation,uint32_t slot,const uint8_t *media,uint32_t card) {
    csnd_selector *c;int status;
    if(!manager || !generation || slot>1 || card>1 || !media || !csnd_ap_enabled(slot))return 0;
    c=csnd_malloc(sizeof(*c));if(!c)return 0;memset(c,0,sizeof(*c));
    c->session=csnd_private_session_create(generation,slot,media,card);
    if(!c->session){csnd_free(c);return 0;}
    c->magic=0x53475549;c->generation=generation;c->slot=slot;c->card=card;c->manager=manager;c->row=0xffffffffu;
    status=csnd_private_submit(manager,c->session,CSND_SCAN,0,0,0);
    if(status!=SS_OK){csnd_private_session_release(c->session);csnd_free(c);return 0;}
    c->phase=CSND_UI_SCANNING;c->status=CSND_AP_BUSY;return c;
}
int csnd_selector_poll(csnd_selector *c) {
    int status;
    if(!valid(c))return SS_INVALID;
    if(c->phase==CSND_UI_SCANNING) {
        status=csnd_private_list_copy(c->session,c->generation,&c->list);
        if(status==CSND_AP_BUSY)return status;
        c->status=(uint32_t)status;
        if(status==SS_OK) {
            uint32_t row;
            for(row=0;row<c->list.count;row++) {
                csnd_picker_entry *e=&c->list.entries[row];
                csnd_selector_project_name(c->display_names[row],e->kind==1 ? default_name:e->name,e->kind==1 ? sizeof(default_name)-1:e->name_bytes);
            }
            c->phase=CSND_UI_LIST;
        }
        return status;
    }
    if(c->phase==CSND_UI_SAVING) {
        if(__atomic_load_n(&c->session->phase,__ATOMIC_ACQUIRE)!=CSND_COMPLETE)return CSND_AP_BUSY;
        c->status=c->session->status;
        /* A failed storage transaction retains previous sound and stays a
         * visible failure. It is never called a successful import. */
        c->phase=c->status==SS_OK ? CSND_UI_DONE : CSND_UI_LIST;
        return (int)c->status;
    }
    return (int)c->status;
}
int csnd_selector_select(csnd_selector *c,uint32_t generation,uint32_t row) {
    csnd_picker_entry *e;
    if(!valid(c) || c->generation!=generation || c->phase!=CSND_UI_LIST || row>=c->list.count)return SS_INVALID;
    e=&c->list.entries[row];if(e->kind!=1 && e->kind!=2)return SS_INVALID;
    if(e->kind==1 && c->slot!=SS_FOCUS)return SS_INVALID;
    c->row=row;c->name_bytes=e->name_bytes;memset(c->selected_name,0,sizeof(c->selected_name));
    if(e->kind==1){memcpy(c->selected_name,default_name,sizeof(default_name));c->name_bytes=sizeof(default_name)-1;}
    else memcpy(c->selected_name,e->name,e->name_bytes);
    c->phase=CSND_UI_CONFIRM;return SS_OK;
}
int csnd_selector_confirm(csnd_selector *c,uint32_t generation,uint32_t yes) {
    int status;uint32_t operation;
    if(!valid(c) || c->generation!=generation || c->phase!=CSND_UI_CONFIRM || yes>1)return SS_INVALID;
    if(!yes){c->phase=CSND_UI_LIST;c->row=0xffffffffu;return SS_OK;}
    operation=c->list.entries[c->row].kind==1 ? CSND_DEFAULT : CSND_IMPORT;
    status=csnd_private_submit(c->manager,c->session,operation,c->row,0,0);
    if(status==SS_OK){c->phase=CSND_UI_SAVING;c->status=CSND_AP_BUSY;}
    return status;
}
int csnd_selector_close(csnd_selector *c) {
    int status;
    if(!valid(c))return SS_INVALID;
    status=csnd_private_cancel(c->session,c->generation);
    /* A running job owns its session reference and never borrows this GUI
     * context. A late worker completion therefore cannot address a freed GUI. */
    model_enter();if(model_owner==c)model_owner=0;model_leave();
    csnd_private_session_release(c->session);c->session=0;c->magic=0;csnd_free(c);return status;
}
int csnd_selector_model(csnd_selector *c,void *presenter,size_t bytes) {
    uint8_t *p=presenter;uint32_t row;
    if(!valid(c) || !presenter || bytes<0x3a84 || (c->phase!=CSND_UI_LIST && c->phase!=CSND_UI_CONFIRM))return SS_INVALID;
    /* Actual16B presenter consumption: count+1048,60x88-byte records+1068,
     * source+3A80. Complete5296B native copy range, never a short buffer. */
    memset(p+0x1068,0,0x14a0);
    for(row=0;row<c->list.count;row++) {
        const csnd_picker_entry *e=&c->list.entries[row];const char *name=e->kind==1 ? default_name:e->name;
        size_t n=e->kind==1 ? sizeof(default_name)-1:e->name_bytes;
        if(n>63){n=63;while(n && (((uint8_t)name[n]&0xc0)==0x80))--n;}
        memcpy(p+0x1068+row*0x58,name,n);
    }
    memcpy(p+0x1048,&c->list.count,4);memset(p+0x3a80,0,4);
    model_enter();c->presenter=presenter;model_owner=c;model_leave();return SS_OK;
}
const char *csnd_selector_row_name(const void *presenter,uint32_t row) {
    csnd_selector *c=model_owner;
    if(!valid(c) || c->presenter!=presenter || (c->phase!=CSND_UI_LIST && c->phase!=CSND_UI_CONFIRM) || row>=c->list.count)return 0;
    /* Actual text field stores129B and snprintf return length. It must never
     * receive a longer name whose reported length crosses native fields. */
    return c->display_names[row];
}
const char *csnd_selector_full_name(const csnd_selector *c,uint32_t row) {
    if(!valid(c) || row>=c->list.count)return 0;
    return c->list.entries[row].kind==1 ? default_name:c->list.entries[row].name;
}
int csnd_selector_copy_row_name(const void *presenter,uint32_t row,char out[129]) {
    csnd_selector *c;int result=0;
    if(!out)return 0;memset(out,0,129);
    /* The native renderer receives its own stack copy. Closing a GUI context
     * after this return cannot free the text that1856CFC is about to consume.
     * This bounded129B model gate is never held across IO/native callbacks. */
    model_enter();c=model_owner;
    if(valid(c) && c->presenter==presenter && row<c->list.count) {
        memcpy(out,c->display_names[row],129);result=1;
    }
    model_leave();return result;
}
