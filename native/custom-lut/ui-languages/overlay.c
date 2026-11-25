#include "p4_gui.h"
#include "p4_import_layout.h"
#include "p4_completion_detail.h"
#include "lut_name_text_v617.h"
#include "lut_stock_numeric_list.h"
enum {G_NORMAL,G_BROWSER,G_CLOSED,G_CARD,G_DELETE,G_CONFIRM};
/* Existing phase bits retain their reserved word; source/card fields add 8 bytes; deferred cleanup adds a further 16 bytes. */
enum {GUI_POLL_DUE=1u,GUI_VISIBLE=2u,GUI_TAIL_ACTIVE=4u,GUI_IDENTITY_RETRIED=8u,GUI_IDENTITY_REFRESH=16u};
enum {A_NONE,A_PREVIEW,A_COMMIT,A_RESTORE_BROWSER,A_RESTORE_NORMAL,A_RESTORE_EXIT,A_RESTORE_PEER,A_SCAN,A_PAGE,A_IMPORT,A_RESTORE_CARD,A_DELETE};
typedef struct {
 p4r_snapshot snapshot;p4r_candidates page;p4r_completion completion;
 lut_ui_state render_state;lut_native_adapter render_adapter;
 p4_gui_timer_gate timer;uint64_t text_vtable[56],original_timer;
 uint64_t anchor,token;uint32_t mode,action,next_action,focus,target,cursor,page_first;
 uint32_t capture,scene,commit_after_preview,close_peer,power_off,closed;
 uint32_t auto_close,catalog_ready,last_slot,reserved;
 uint64_t applied_sequence;p4l_identity applied_identity;
 char status[96];
 /* Read-only diagnostic storage never replaces the in-flight
  * catalog/identity snapshot and never uses the small GUI stack. */
 uint32_t diagnostic_timer_calls,diagnostic_poll_calls;
 p4r_snapshot diagnostic_snapshot;
 /* Appended fields preserve all prior diagnostic offsets. */
 uint32_t source_card,list_top;
 /* Process-lifetime cleanup; never contains a presenter/view pointer. */
 uint32_t deferred_restore,cleanup_reserved;uint64_t cleanup_thread;
 p6_settings draft;uint32_t edit_field,delete_mask;int16_t author_defaults[8];
} p4_gui_context;
extern p4_gui_context *lut_existing_gui_context;
#define context lut_existing_gui_context
#include "lut_ui_text.h"
static uint64_t addr(uint64_t v){return lut_widget_bias()+v;}

static uint64_t r64(uint64_t p){return *(volatile uint64_t*)(uintptr_t)p;}

static uint32_t r32(uint64_t p){return *(volatile uint32_t*)(uintptr_t)p;}

static void copy(void*d,const void*s,uint32_t n){uint8_t*p=d;const uint8_t*q=s;while(n--)*p++=*q++;}

static uint32_t length(const char*s){uint32_t n=0;while(s[n])n++;return n+1;}

static uint8_t*param(lut_stock_entry*m,uint32_t i){return m[i].type==2&&m[i].param?(uint8_t*)(uintptr_t)m[i].param:0;}

static void text(uint8_t*p,const char*s){if(p)lut_ui_bind_label(p,0x658,s,length(s),LUT_TEXT_V617_RESOURCE);}

static uint32_t decimal(char*p,uint32_t n){if(n>=10){p[0]=(char)('0'+n/10);p[1]=(char)('0'+n%10);return 2;}p[0]=(char)('0'+n);return 1;}

static uint8_t*typed(lut_stock_entry*m,uint32_t i,uint32_t type){return m[i].type==type&&m[i].param?(uint8_t*)(uintptr_t)m[i].param:0;}

static void pw32(uint8_t*p,uint32_t off,uint32_t x){*(uint32_t*)(p+off)=x;}

static void option_values(uint8_t*p,const p6_settings*s,const int16_t*defaults,uint32_t edit){
 if(!p)return;pw32(p,0x30,edit);pw32(p,0x94,0);pw32(p,0x98,0xffffffffu);
 for(unsigned i=0;i<8;i++){pw32(p,0x34+12*i,i);pw32(p,0x38+12*i,(uint32_t)(defaults[i]+s->delta[i]));p[0x3c+12*i]=0;}
}

static void rect(uint8_t*p,uint32_t x,uint32_t y,uint32_t w,uint32_t h){if(p){pw32(p,0x18,x);pw32(p,0x1c,y);pw32(p,0x20,w);pw32(p,0x24,h);}}

void lut_localized_render_overlay(lut_stock_entry*m,uint32_t count,uint32_t scene){
 p4_gui_context*q=context;if(!q||!m)return;
 if(scene==0xda&&count==107){
  static const char names[9][16]={"强度","对比度","高光","阴影","褪色","饱和度","锐度","锐度范围","清晰度"};
  static const uint16_t x[9]={14,84,154,224,294,364,426,488,550};
  static const uint16_t widths[9]={70,70,70,70,70,62,62,62,78};
  static const int8_t low[9]={1,-9,-9,-9,0,-9,0,1,0},high[9]={10,9,9,9,9,9,9,5,9};
  unsigned field=q->edit_field,cell=field?field-1:8;char value[8];unsigned at=0;
  int n=q->draft.strength*10;if(n==100){value[at++]='1';value[at++]='0';value[at++]='0';}else at=decimal(value,n);value[at++]='%';value[at]=0;
  text(param(m,11),q->status[0]?q->status:names[field]);text(param(m,40),value);
  option_values(typed(m,33,0x5e),&q->draft,q->author_defaults,1);
  int current=field?q->author_defaults[field-1]+q->draft.delta[field-1]:q->draft.strength;
  uint8_t*p=typed(m,13,0x56);if(p){p[0x2c]=1;pw32(p,0x30,!field?2:field==7?3:(field<=3||field==5)?0:2);pw32(p,0x34,field?(uint32_t)current:q->draft.strength-1);pw32(p,0x38,0xffffffffu);}
  lut_stock_runtime*g=&lut_widget_runtime_state;g->reserved=(g->reserved&~1u)|(!field);
  uint32_t landscape=!g->presenter||r32(g->presenter+8)==0;
  p=typed(m,23,0x11);if(p){p[0x2c]=1;p[0x30]=1;rect(p,landscape?x[cell]:352,landscape?349:12+cell*57,landscape?widths[cell]:116,landscape?56:57);}
  for(unsigned i=0;i<2;i++){p=typed(m,41+i,0);if(p){p[0x2c]=landscape&&(i?current<high[field]:current>low[field]);rect(p,x[cell]+(widths[cell]-34)/2,i?339:397,34,18);}}
  for(unsigned i=21;i<=22;i++){p=param(m,i);if(p)p[0x2c]=!field&&landscape;}
  for(unsigned i=80;i<=88;i++){p=typed(m,i,0x14);if(p){p[0x2c]=(i-80u)!=cell;for(unsigned o=0x34;o<0x3c;o+=2)*(uint16_t*)(p+o)=0;}}
  return;
 }
 if(scene!=0xd9||count!=34)return;
 if(q->mode==G_NORMAL&&q->focus<16)option_values(typed(m,13,0x5e),&q->snapshot.settings[q->focus],q->snapshot.author_defaults,0);
 if(q->mode!=G_CARD&&q->mode!=G_BROWSER&&q->mode!=G_DELETE&&q->mode!=G_CONFIRM)return;
 for(uint32_t i=0;i<34;i++)if(m[i].param)((uint8_t*)(uintptr_t)m[i].param)[0x2c]=0;
 uint32_t active=q->mode!=G_BROWSER?11u:9u;for(uint32_t i=0;i<active;i++)if(m[i].param)((uint8_t*)(uintptr_t)m[i].param)[0x2c]=1;
 if(q->mode!=G_BROWSER){
  text(param(m,4),q->mode==G_CARD?"选择存储卡":q->mode==G_DELETE?"删除滤镜":q->delete_mask==65535u?"清空全部滤镜？":"删除此滤镜？");text(param(m,6),"");text(param(m,9),q->mode==G_CARD?"存储卡2":q->mode==G_DELETE?"清空全部滤镜":"删除");text(param(m,10),q->mode==G_CARD?"存储卡1":q->mode==G_DELETE?"删除此滤镜":"取消");
  if(q->mode!=G_CARD){uint32_t width=(!lut_widget_runtime_state.presenter||r32(lut_widget_runtime_state.presenter+8)==0)?640u:480u;
   for(unsigned i=7;i<=10;i++)if(m[i].param){uint8_t*p=(uint8_t*)(uintptr_t)m[i].param;pw32(p,0x18,(width-r32((uintptr_t)p+0x20))/2u);}}
  uint8_t*p=typed(m,7,9);if(p){p[0x3c]=q->source_card==1;p[0x3f]=0;}
  p=typed(m,8,9);if(p){p[0x3c]=q->source_card==0;p[0x3f]=0;}
  p=typed(m,1,0);if(p){if(q->mode!=G_CARD)p[0x2c]=0;uint32_t display=((uint32_t(*)(void))(uintptr_t)addr(0x18568b8))();
   if(display<4){uint64_t resources=r64(addr(0x5a010b8));pw32(p,0x3c,r32(resources+(q->source_card*4u+display)*4u));}}
  p=typed(m,5,0x18);if(p)pw32(p,0x30,2);
 }else{
  text(param(m,5),"选择滤镜文件");text(param(m,6),"");text(param(m,7),"文件名");
  uint8_t*p=typed(m,1,0x50);if(p){
   uint32_t n=q->page.count<=16?q->page.count:0;
   for(uint32_t i=0;i<n;i++){
    uint32_t o=i*0x9e8u;char filename[65];copy(filename,q->page.rows[i].filename,64);filename[64]=0;
    pw32(p,o+0x950,15);pw32(p,o+0x344,0x207a029);pw32(p,o+0x630,1);
    ((void(*)(void*))(uintptr_t)addr(0x1856b5c))(p+o+0x34c);
    ((void(*)(void*,const char*))(uintptr_t)addr(0x1856cfc))(p+o+0x34c,filename);
    /* Existing filename-only renderer18C05EC uses this exact pair; no sound session. */
    pw32(p,o+0x970,0x43534e44u);pw32(p,o+0x980,0x43535602u);
    /* Row-private width contract; original1895820 copies984/988 to50C/510. */
    pw32(p,o+0x984,0x4c555457u);
    p[o+0x9ce]=1;p[o+0x9d0]=1;pw32(p,o+0x640,0x33);pw32(p,o+0x990,0x35);pw32(p,o+0x994,0x36);
   }
   pw32(p,0x30,n?q->cursor:0);pw32(p,0x34,n?q->list_top:0);pw32(p,0x22d3f8,n);pw32(p,0x22d3fc,6);
   /* Original rectangle initializers173E590 and producer23B7D30. */
   copy(p+0x22d3d8,(void*)(uintptr_t)addr(0x7f67be0),16);copy(p+0x22d3e8,(void*)(uintptr_t)addr(0x7f67bf0),16);pw32(p,0x22d400,50);
   if(lut_widget_runtime_state.presenter&&r32(lut_widget_runtime_state.presenter+8)!=0){
    pw32(p,0x22d3e0,442);pw32(p,0x22d3e4,396);pw32(p,0x22d3e8,468);pw32(p,0x22d3f0,6);pw32(p,0x22d400,66);
   }
   for(uint32_t i=0;i<n;i++)pw32(p,i*0x9e8u+0x988,r32((uintptr_t)p+0x22d3e0));
  }
  p=typed(m,4,0x18);if(p)pw32(p,0x30,2);
 }
 char page_label[16];const char*message=q->status;
 if(!message[0]&&q->mode==G_BROWSER&&q->page.total>16){uint32_t k=decimal(page_label,q->page.first/16+1);page_label[k++]='/';k+=decimal(page_label+k,(q->page.total+15)/16);page_label[k]=0;message=page_label;}
 uint8_t*p=param(m,19);text(p,message);if(p)p[0x2c]=message[0]!=0;
}
