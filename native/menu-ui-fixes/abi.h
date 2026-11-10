#ifndef A7M4_MENU_UI_ABI_H
#define A7M4_MENU_UI_ABI_H
#include <stdint.h>
#include <stddef.h>

/* Partial views of the exact component ABI. Opaque bytes are never accessed
 * or allocated here; the original GUI owns both objects and their lifetime. */
enum { G_NORMAL=0, A_PREVIEW=1, P4R_OFF=16,
       GUI_IDENTITY_RETRIED=8, GUI_IDENTITY_REFRESH=16 };
typedef struct {
    uint8_t opaque_0000[0x1fd0];
    struct { uint8_t opaque[0x34]; uint32_t active; } timer;
    uint8_t opaque_2008[0x21e8-0x2008];
    uint64_t token;
    uint32_t mode,action,next_action,focus;
    uint8_t opaque_2200[0x2214-0x2200];
    uint32_t commit_after_preview;
    uint8_t opaque_2218[0x2230-0x2218];
    uint32_t reserved;
    uint8_t opaque_2234[0x3160-0x2234];
    uint32_t perf_active;
} p4_gui_context;
typedef struct {
    uint8_t opaque_0000[0x30];
    uint32_t scene,transition;
    uint8_t opaque_0038[0x48-0x38];
    struct { uint8_t opaque[0x10]; uint32_t focused_slot; } state;
} lut_stock_runtime;
extern lut_stock_runtime lut_widget_runtime_state;
_Static_assert(offsetof(p4_gui_context,timer.active)==0x2004,"timer ABI");
_Static_assert(offsetof(p4_gui_context,token)==0x21e8,"token ABI");
_Static_assert(offsetof(p4_gui_context,focus)==0x21fc,"focus ABI");
_Static_assert(offsetof(p4_gui_context,commit_after_preview)==0x2214,"commit ABI");
_Static_assert(offsetof(p4_gui_context,reserved)==0x2230,"flags ABI");
_Static_assert(offsetof(p4_gui_context,perf_active)==0x3160,"diagnostic ABI");
_Static_assert(offsetof(lut_stock_runtime,state.focused_slot)==0x58,"GUI state ABI");
#endif
