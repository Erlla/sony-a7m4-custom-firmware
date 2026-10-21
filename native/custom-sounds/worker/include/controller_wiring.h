#ifndef CSND_CONTROLLER_WIRING_H
#define CSND_CONTROLLER_WIRING_H
#include "private_selector.h"
/* These objects belong to the GUI event thread. Jobs retain only Session,
 * never a native controller or presenter. An immutable generation survives
 * outgoing-controller destruction before the next scene is constructed. */
int csnd_controller_prepare(void *manager,uint32_t generation,uint32_t slot);
int csnd_controller_after_construct(void *controller,uint32_t scene);
void csnd_controller_before_destroy(void *controller);
int csnd_controller_card_confirm(void *controller);
int csnd_controller_file_init(void *controller);
int csnd_controller_file_confirm(void *controller);
int csnd_controller_file_cancel(void *controller);
int csnd_controller_card_cancel(void *controller);
int csnd_controller_file_previous(void *controller);
int csnd_controller_file_next(void *controller);
int csnd_controller_row_event(void *controller,const void *message);
int csnd_controller_confirm(void *controller);
int csnd_controller_confirm_cancel(void *controller);
int csnd_controller_wait_tick(void *controller);
int csnd_controller_row(void *controller,uint32_t generation,uint32_t row);
int csnd_controller_bind_presenter(void *controller,void *presenter,size_t bytes);
/* Actual original file presenter slot and snapshot ABI, not a model handoff. */
int csnd_controller_refresh_native_presenter(void *presenter);
uintptr_t csnd_controller_snapshot_thunk(uintptr_t presenter);
/* Actual2D7 route consumer after the unchanged original CLUT-aware launch. */
uintptr_t csnd_controller_menu_route(void *controller,const uint32_t *scene,
                                     const uint32_t *secondary,const uint32_t *third);
int csnd_controller_copy_confirmation_name(const void *presenter,char out[129]);
uintptr_t csnd_controller_submenu_render(uintptr_t presenter);
/* Diagnostics are copied values. No borrowed owner pointer is exported. */
typedef struct {uint32_t generation,slot,scene,expected_scene,phase,status,row,references;} csnd_controller_view;
int csnd_controller_view_copy(void *controller,csnd_controller_view *out);
/* Constructor wrappers replay all eight original arguments and return. */
uintptr_t csnd_controller_ctor_card(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
uintptr_t csnd_controller_ctor_file(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
uintptr_t csnd_controller_ctor_confirm(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
uintptr_t csnd_controller_ctor_wait(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
void csnd_controller_dtor_card(void *);
void csnd_controller_dtor_file(void *);
void csnd_controller_dtor_confirm(void *);
void csnd_controller_dtor_wait(void *);
#endif
