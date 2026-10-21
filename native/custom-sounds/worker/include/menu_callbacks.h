#ifndef CSND_MENU_CALLBACKS_H
#define CSND_MENU_CALLBACKS_H
#include "private_worker.h"
uint32_t csnd_menu_electronic_getter(void);
uint32_t csnd_menu_focus_getter(void);
void csnd_menu_electronic_setter(uint32_t raw);
void csnd_menu_focus_setter(uint32_t raw);
int csnd_menu_electronic_commit(uint32_t alias);
int csnd_menu_focus_commit(uint32_t alias);
int csnd_menu_electronic_available(void);
int csnd_menu_focus_available(void);
/* Canonical native MID exclusion facade returns1 when the row is blocked. */
uint32_t csnd_menu_import_blocked(uint32_t mid);
uint32_t csnd_menu_zero(void);
int csnd_menu_no_direct_import(uint32_t unused);
/* Pointer-free diagnostics only. GUI callback gate is try-only. */
int csnd_menu_request_status(uint32_t slot,uint32_t *queued,uint32_t *status);
#endif
