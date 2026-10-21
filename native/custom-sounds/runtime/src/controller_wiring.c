/* Source615 bounded controller bridge. Installation remains OFF until native
 * menu action, observer/snapshot association, wait-event delivery and startup
 * readiness are closed. No original CLUT property or shared filename is used.
 * GUI-thread ownership is a checked precondition, not an OS lock/retry claim. */
#include "controller_wiring.h"
extern void *csnd_malloc(size_t);
extern void csnd_free(void *);
extern void *memset(void *,int,size_t);
extern void *memcpy(void *,const void *,size_t);
extern uintptr_t csnd_pthread_self(void);
extern uint8_t *csnd_native_media_get(void);
extern uint32_t csnd_native_controller_state(void *);
extern void csnd_native_controller_set_state(void *,uint32_t);
extern int csnd_original_card_confirm(void *);
extern int csnd_original_card_cancel(void *);
extern int csnd_original_file_init(void *);
extern int csnd_original_file_confirm(void *);
extern int csnd_original_file_cancel(void *);
extern int csnd_original_confirm(void *);
extern int csnd_original_confirm_cancel(void *);
extern int csnd_original_wait_tick(void *);
extern int csnd_original_file_previous(void *);
extern int csnd_original_file_next(void *);
extern int csnd_original_row_event(void *,const void *);
extern uintptr_t csnd_original_card_ctor(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern uintptr_t csnd_original_file_ctor(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern uintptr_t csnd_original_confirm_ctor(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern uintptr_t csnd_original_wait_ctor(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern void csnd_original_card_dtor(void *);
extern void csnd_original_file_dtor(void *);
extern void csnd_original_confirm_dtor(void *);
extern void csnd_original_wait_dtor(void *);
extern char csnd_native_controller_arena;
extern void *csnd_native_presenter_slots[6];
extern char csnd_native_file_presenter_vtable;
extern char csnd_native_confirm_presenter_vtable;
extern uintptr_t csnd_original_file_snapshot(uintptr_t);
extern uintptr_t csnd_original_menu_route(void *,const uint32_t *,const uint32_t *,const uint32_t *);
extern uint32_t *csnd_native_menu_mid(void);
extern void *csnd_native_manager_get(void);
extern char csnd_native_submenu_presenter_vtable;
extern uintptr_t csnd_original_submenu_render(uintptr_t);
extern void *csnd_native_menu_body(void *);
extern void *csnd_native_text_item(void *,uint32_t);
extern void csnd_native_assign_text(void *,const char *);
typedef struct {
    uint32_t references,closed,generation,slot,expected_scene,status,row,reserved;
    csnd_selector *selector;
    void *manager;
    uintptr_t gui_thread;
} flow;
typedef struct {void *controller;flow *owner;uint32_t scene,reserved;} binding;
static binding controllers[16];
static flow *active;
static int owned(binding *,uint32_t);
static uint32_t next_gui_generation=1;
static uint32_t native_slot(void *controller) {
    uintptr_t base=(uintptr_t)&csnd_native_controller_arena,at=(uintptr_t)controller;
    if(at<base || at-base>=6u*0x5000u || (at-base)%0x5000u)return 0xffffffffu;
    return (uint32_t)((at-base)/0x5000u);
}
_Static_assert(sizeof(flow)==56,"AP64 flow ABI");
_Static_assert(sizeof(binding)==24,"AP64 external binding ABI");
static void retain(flow *f){++f->references;}
static void release(flow *f) {
    if(--f->references)return;
    if(f->selector)csnd_selector_close(f->selector);
    memset(f,0,sizeof(*f));csnd_free(f);
}
static binding *lookup(void *controller) {
    uint32_t i;
    for(i=0;i<16;i++)if(controllers[i].controller==controller)return &controllers[i];
    return 0;
}
static int same_thread(flow *f){return f->gui_thread==csnd_pthread_self();}
static void finish(flow *f) {
    if(__atomic_exchange_n(&f->closed,1,__ATOMIC_ACQ_REL)==1)return;
    f->expected_scene=0;
    if(f->selector){csnd_selector_close(f->selector);f->selector=0;}
    if(active==f){active=0;release(f);} /* drop handoff/root reference */
}
static int route(binding *b,uint32_t scene) {
    uintptr_t *vtable;void *router;flow *f=b->owner;
    /* A controller/event call owns its reference. Retain additionally across
     * the virtual scene request: it may synchronously retire this controller.
     * No registry pointer is accessed after the request returns. */
    if(b->reserved || __atomic_load_n(&f->closed,__ATOMIC_ACQUIRE))return CSND_AP_NOT_READY;
    router=*(void **)((uint8_t *)b->controller+0x180);
    if(!router || !(vtable=*(uintptr_t **)router) || !vtable[0])return SS_INVALID;
    b->reserved=1;f->expected_scene=scene;retain(f);
    ((void (*)(void *,void *,const uint32_t *))vtable[0])(router,(uint8_t *)b->controller+0x178,&scene);
    release(f);return SS_OK;
}
static int back(binding *b) {
    uintptr_t *vtable;void *router;flow *f=b->owner;
    void *native_context=(uint8_t *)b->controller+0x178;
    router=*(void **)((uint8_t *)b->controller+0x180);
    if(!router || !(vtable=*(uintptr_t **)router) || !vtable[4])return SS_INVALID;
    retain(f);finish(f);
    ((void (*)(void *,void *))vtable[4])(router,native_context);
    release(f);return SS_OK;
}
int csnd_controller_prepare(void *manager,uint32_t generation,uint32_t slot) {
    flow *f;
    /* Preparation does not make picker_ready true or launch a scene. The
     * future menu action must additionally check import_available. */
    if(!manager || !generation || slot>1 || !csnd_ap_enabled(slot))return SS_INVALID;
    if(active)return CSND_AP_BUSY;
    f=csnd_malloc(sizeof(*f));if(!f)return SS_LIMIT;
    memset(f,0,sizeof(*f));f->references=1;f->generation=generation;f->slot=slot;
    f->manager=manager;f->gui_thread=csnd_pthread_self();f->expected_scene=0x15c;
    active=f;return SS_OK;
}
uintptr_t csnd_controller_menu_route(void *controller,const uint32_t *scene,
                                      const uint32_t *secondary,const uint32_t *third) {
    uint32_t mid=*csnd_native_menu_mid(),slot,generation;void *manager;
    if(mid!=1594 && mid!=1597)return csnd_original_menu_route(controller,scene,secondary,third);
    /* The imported descriptor must actually advertise15C. A mismatched old
     * experimental2DE descriptor cannot accidentally launch original CLUT IO.
     * ready remains0 until scene lifetime and scheduler producers are closed. */
    slot=mid==1594?SS_ELECTRONIC:SS_FOCUS;
    if(!controller || !scene || *scene!=0x15c || !csnd_ap_import_available(slot))return 0;
    manager=csnd_native_manager_get();if(!manager)return 0;
    generation=next_gui_generation++;
    if(!generation)generation=next_gui_generation++;
    if(csnd_controller_prepare(manager,generation,slot)!=SS_OK)return 0;
    return csnd_original_menu_route(controller,scene,secondary,third);
}
/* The remaining source member-table handlers read or mutate global CLUT
 * routing/recording parameters or send original LUT/CP sequence commands.
 * They must not execute for an externally owned sound flow. Native keyboard
 * direction/confirm/cancel and state-engine handlers remain separate. */
__attribute__((noinline)) static int auxiliary_guard(void *controller,const void *message,
        int (*original)(void *,const void *),uint32_t scene,uint32_t poll) {
    binding *b=lookup(controller);
    if(!b)return original(controller,message);
    if(owned(b,scene) && poll)return csnd_controller_wait_tick(controller);
    return 1;
}
#define AUXILIARY_GUARD(name,scene,poll) \
extern int csnd_original_##name(void *,const void *); \
int csnd_controller_##name(void *controller,const void *message) { \
    return auxiliary_guard(controller,message,csnd_original_##name,scene,poll); \
}
AUXILIARY_GUARD(file_rec_notify,0x16b,0)
AUXILIARY_GUARD(file_half_press,0x16b,0)
AUXILIARY_GUARD(file_half_release,0x16b,0)
AUXILIARY_GUARD(file_aux_property,0x16b,0)
AUXILIARY_GUARD(confirm_rec_notify,0x174,0)
AUXILIARY_GUARD(confirm_half_press,0x174,0)
AUXILIARY_GUARD(confirm_half_release,0x174,0)
AUXILIARY_GUARD(wait_rec_notify,0x2b2,0)
AUXILIARY_GUARD(wait_half_press,0x2b2,0)
AUXILIARY_GUARD(wait_half_release,0x2b2,0)
AUXILIARY_GUARD(wait_cancel_command,0x2b2,0)
AUXILIARY_GUARD(wait_command_result,0x2b2,1)
AUXILIARY_GUARD(wait_media_result,0x2b2,1)
AUXILIARY_GUARD(wait_aux_status,0x2b2,0)
AUXILIARY_GUARD(wait_finish,0x2b2,1)
AUXILIARY_GUARD(wait_stop_command,0x2b2,0)
AUXILIARY_GUARD(wait_return_list,0x2b2,1)
AUXILIARY_GUARD(wait_return_request,0x2b2,1)
#undef AUXILIARY_GUARD
int csnd_controller_after_construct(void *controller,uint32_t scene) {
    uint32_t i;flow *f=active;
    if(!controller || !f || __atomic_load_n(&f->closed,__ATOMIC_ACQUIRE) || !same_thread(f) || f->expected_scene!=scene)return CSND_AP_NOT_READY;
    if(lookup(controller))return SS_INVALID;
    for(i=0;i<16;i++)if(!controllers[i].controller) {
        controllers[i]=(binding){controller,f,scene,0};retain(f);f->expected_scene=0;
        /* Presenter may already have been constructed for this slot. Its
         * exact native vptr and slot identity are checked before touching it. */
        if(scene==0x16b) {
            uint32_t slot=native_slot(controller);
            if(slot<6)csnd_controller_refresh_native_presenter(csnd_native_presenter_slots[slot]);
        }
        return SS_OK;
    }
    /* A failed binding must not create a partially usable custom flow. The
     * native entry remains gated OFF until failure routing is also installed. */
    f->status=SS_LIMIT;return SS_LIMIT;
}
void csnd_controller_before_destroy(void *controller) {
    binding *b=lookup(controller);flow *f;
    if(!b)return;f=b->owner;
    /* Cross-thread native destruction is an unclosed integration boundary.
     * Mark this flow unusable before the original native dtor continues; do
     * not free shared private ownership from that foreign thread. A later
     * GUI-thread retirement can drain it. This is fail-closed quarantine,
     * not a proof of concurrent native controller access or OS retry. */
    if(!same_thread(f)){__atomic_store_n(&f->closed,2,__ATOMIC_RELEASE);return;}
    memset(b,0,sizeof(*b));
    if(f->references==2 && !f->expected_scene)finish(f);
    release(f);
}
static int owned(binding *b,uint32_t scene) {
    return b && !b->reserved && b->scene==scene && !__atomic_load_n(&b->owner->closed,__ATOMIC_ACQUIRE) && same_thread(b->owner);
}
int csnd_controller_card_confirm(void *controller) {
    binding *b=lookup(controller);flow *f;uint32_t state,card;
    if(!b)return csnd_original_card_confirm(controller);
    if(!owned(b,0x15c))return 1;
    f=b->owner;state=csnd_native_controller_state((uint8_t *)controller+0x1a0);
    if(state!=7 && state!=8){f->status=SS_INVALID;return 1;}
    card=state==8?0u:1u;
    if(f->selector){f->status=CSND_AP_BUSY;return 1;}
    f->selector=csnd_selector_create(f->manager,f->generation,f->slot,csnd_native_media_get(),card);
    if(!f->selector){f->status=CSND_AP_NOT_READY;return 1;}
    f->status=CSND_AP_BUSY;route(b,0x2b2);return 1;
}
int csnd_controller_file_init(void *controller) {
    binding *b=lookup(controller);flow *f;
    if(!b)return csnd_original_file_init(controller);
    if(!owned(b,0x16b))return 1;
    f=b->owner;
    if(!f->selector){f->status=CSND_AP_NOT_READY;return 1;}
    f->row=0;
    /* Returning from a successful save permits another single selection;
     * the committed filename remains in core-owned metadata. */
    if(f->selector->phase==CSND_UI_DONE)f->selector->phase=CSND_UI_LIST;
    csnd_native_controller_set_state((uint8_t *)controller+0x1a0,1);
    return 1;
}
int csnd_controller_row(void *controller,uint32_t generation,uint32_t row) {
    binding *b=lookup(controller);flow *f;
    if(!owned(b,0x16b))return SS_INVALID;f=b->owner;
    if(f->generation!=generation || !f->selector || f->selector->phase!=CSND_UI_LIST || row>=f->selector->list.count)return SS_INVALID;
    f->row=row;return SS_OK;
}
static int move_row(binding *b,uint32_t forward) {
    flow *f=b->owner;uint32_t count;
    if(!owned(b,0x16b) || !f->selector || f->selector->phase!=CSND_UI_LIST)return 1;
    count=f->selector->list.count;if(!count)return 1;
    if(forward)f->row=f->row+1u<count?f->row+1u:0u;
    else f->row=f->row?f->row-1u:count-1u;
    return 1;
}
int csnd_controller_file_previous(void *controller) {
    binding *b=lookup(controller);
    if(!b)return csnd_original_file_previous(controller);return move_row(b,0);
}
int csnd_controller_file_next(void *controller) {
    binding *b=lookup(controller);
    if(!b)return csnd_original_file_next(controller);return move_row(b,1);
}
int csnd_controller_row_event(void *controller,const void *message) {
    binding *b=lookup(controller);
    if(!b)return csnd_original_row_event(controller,message);
    if(owned(b,0x16b) && message)csnd_controller_row(controller,b->owner->generation,*(const uint32_t *)((const uint8_t *)message+0x30));
    return 1;
}
int csnd_controller_file_confirm(void *controller) {
    binding *b=lookup(controller);flow *f;int status;
    if(!b)return csnd_original_file_confirm(controller);
    if(!owned(b,0x16b))return 1;f=b->owner;
    if(!f->selector){f->status=CSND_AP_NOT_READY;return 1;}
    status=csnd_selector_select(f->selector,f->generation,f->row);f->status=(uint32_t)status;
    if(status==SS_OK)route(b,0x174);return 1;
}
int csnd_controller_file_cancel(void *controller) {
    binding *b=lookup(controller);
    if(!b)return csnd_original_file_cancel(controller);
    if(owned(b,0x16b))back(b);return 1;
}
int csnd_controller_card_cancel(void *controller) {
    binding *b=lookup(controller);
    if(!b)return csnd_original_card_cancel(controller);
    if(owned(b,0x15c))back(b);return 1;
}
int csnd_controller_confirm(void *controller) {
    binding *b=lookup(controller);flow *f;uint32_t state;int status;
    if(!b)return csnd_original_confirm(controller);
    if(!owned(b,0x174))return 1;f=b->owner;
    state=csnd_native_controller_state((uint8_t *)controller+0x1a0);
    if(!f->selector || (state!=6 && state!=7)){f->status=SS_INVALID;return 1;}
    status=csnd_selector_confirm(f->selector,f->generation,state==7);f->status=(uint32_t)status;
    if(status==SS_OK)route(b,state==7?0x2b2:0x16b);return 1;
}
int csnd_controller_confirm_cancel(void *controller) {
    binding *b=lookup(controller);flow *f;int status;
    if(!b)return csnd_original_confirm_cancel(controller);
    if(!owned(b,0x174))return 1;f=b->owner;
    if(!f->selector){f->status=SS_INVALID;return 1;}
    status=csnd_selector_confirm(f->selector,f->generation,0);f->status=(uint32_t)status;
    if(status==SS_OK)route(b,0x16b);return 1;
}
int csnd_controller_wait_tick(void *controller) {
    binding *b=lookup(controller);flow *f;int status;
    if(!b)return csnd_original_wait_tick(controller);
    if(!owned(b,0x2b2))return 1;f=b->owner;
    if(!f->selector){f->status=SS_INVALID;return 1;}
    status=csnd_selector_poll(f->selector);f->status=(uint32_t)status;
    if(status==CSND_AP_BUSY)return 1;
    if(f->selector->phase==CSND_UI_LIST || f->selector->phase==CSND_UI_DONE)route(b,0x16b);
    else if(status!=SS_OK)back(b);
    return 1;
}
int csnd_controller_bind_presenter(void *controller,void *presenter,size_t bytes) {
    binding *b=lookup(controller);
    if(!owned(b,0x16b) || !b->owner->selector)return SS_INVALID;
    return csnd_selector_model(b->owner->selector,presenter,bytes);
}
int csnd_controller_refresh_native_presenter(void *presenter) {
    uint32_t slot,i;binding *b;
    if(!presenter || *(uintptr_t *)presenter!=(uintptr_t)&csnd_native_file_presenter_vtable)return SS_INVALID;
    for(slot=0;slot<6;slot++)if(csnd_native_presenter_slots[slot]==presenter)break;
    if(slot==6)return SS_INVALID;
    b=lookup((uint8_t *)&csnd_native_controller_arena+slot*0x5000u);
    if(!owned(b,0x16b) || !b->owner->selector)return SS_INVALID;
    /* Source1D268DC setsX1=presenter+EF0 before complete2076C2C. The private
     * producer replaces only the actual local list/count/source/row fields.
     * Other native mask/snapshot fields and original observer lists remain. */
    i=(uint32_t)csnd_selector_model(b->owner->selector,presenter,0x8270);
    if(i==SS_OK)*(uint32_t *)((uint8_t *)presenter+0x3a00)=b->owner->row;
    return (int)i;
}
uintptr_t csnd_controller_snapshot_thunk(uintptr_t presenter) {
    uintptr_t result=csnd_original_file_snapshot(presenter);
    csnd_controller_refresh_native_presenter((void *)presenter);
    return result;
}
int csnd_controller_copy_confirmation_name(const void *presenter,char out[129]) {
    uint32_t slot;binding *b;csnd_selector *c;
    if(!out)return 0;memset(out,0,129);
    if(!presenter || *(const uintptr_t *)presenter!=(uintptr_t)&csnd_native_confirm_presenter_vtable)return 0;
    for(slot=0;slot<6;slot++)if(csnd_native_presenter_slots[slot]==presenter)break;
    if(slot==6)return 0;
    b=lookup((uint8_t *)&csnd_native_controller_arena+slot*0x5000u);
    if(!owned(b,0x174) || !(c=b->owner->selector) || c->phase!=CSND_UI_CONFIRM || c->row>=c->list.count)return 0;
    /* Display uses a stack-owned UTF8 projection. Confirm/import identity is
     * still the complete selected_name and immutable private job filename. */
    memcpy(out,c->display_names[c->row],129);return 1;
}
uintptr_t csnd_controller_submenu_render(uintptr_t presenter) {
    uintptr_t result=csnd_original_submenu_render(presenter);uint8_t *p=(uint8_t *)presenter,*widget;
    uint32_t mid,slot;void *cell,*body,*text;ss_menu_view view;char name[129];
    if(!p || *(uintptr_t *)p!=(uintptr_t)&csnd_native_submenu_presenter_vtable)return result;
    /* Actual2D7 snapshot200CAB4 copies PRM3B2 into p+EFC. */
    mid=*(uint32_t *)(p+0xefc);if(mid!=1594 && mid!=1597)return result;
    slot=mid==1594?SS_ELECTRONIC:SS_FOCUS;
    memset(name,0,sizeof(name));
    if(csnd_ap_menu_view(slot,&view)==SS_OK) {
        if(view.selection==SS_SELECTION_CUSTOM)csnd_selector_project_name(name,view.name,view.name_bytes);
        else if(slot==SS_FOCUS && view.selection==SS_SELECTION_DEFAULT)csnd_selector_project_name(name,"默认",6);
    }
    widget=*(uint8_t **)(p+0x30);if(!widget)return result;cell=widget+0xb0;
    /* Same source221EA34..1EAAC widget cell/type and1873510 list used for
     * original2D7 option text. Do not resize an original field or return a
     * borrowed metadata pointer into the render consumer. */
    if(*(uint32_t *)cell!=0x5b || !*(void **)((uint8_t *)cell+8))return result;
    body=csnd_native_menu_body(&cell);
    text=csnd_native_text_item((uint8_t *)body+0xd0,0);
    csnd_native_assign_text(text,name);return result;
}
int csnd_controller_view_copy(void *controller,csnd_controller_view *out) {
    binding *b=lookup(controller);flow *f;
    if(!out)return SS_INVALID;memset(out,0,sizeof(*out));
    if(!b || !same_thread(b->owner))return SS_INVALID;f=b->owner;
    *out=(csnd_controller_view){f->generation,f->slot,b->scene,f->expected_scene,f->selector?f->selector->phase:0,f->status,f->row,f->references};return SS_OK;
}
#define CTOR_WRAPPER(name,original,scene) \
uintptr_t name(uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d,uintptr_t e,uintptr_t f,uintptr_t g,uintptr_t h) { \
    uintptr_t result=original(a,b,c,d,e,f,g,h); \
    csnd_controller_after_construct((void *)a,scene);return result; \
}
CTOR_WRAPPER(csnd_controller_ctor_card,csnd_original_card_ctor,0x15c)
CTOR_WRAPPER(csnd_controller_ctor_file,csnd_original_file_ctor,0x16b)
CTOR_WRAPPER(csnd_controller_ctor_confirm,csnd_original_confirm_ctor,0x174)
CTOR_WRAPPER(csnd_controller_ctor_wait,csnd_original_wait_ctor,0x2b2)
#define DTOR_WRAPPER(name,original) \
void name(void *controller){csnd_controller_before_destroy(controller);original(controller);}
DTOR_WRAPPER(csnd_controller_dtor_card,csnd_original_card_dtor)
DTOR_WRAPPER(csnd_controller_dtor_file,csnd_original_file_dtor)
DTOR_WRAPPER(csnd_controller_dtor_confirm,csnd_original_confirm_dtor)
DTOR_WRAPPER(csnd_controller_dtor_wait,csnd_original_wait_dtor)
