#include "lut_ui_text.h"
#include "lut_stock_layout.h"
#include "lut_gauge_parameter_bound.h"
#include "lut_stock_numeric_list.h"
#include "native_control.h"
#include "p4_gui.h"
static void clear(void *p,uint32_t n){uint8_t *b=p;while(n--)*b++=0;}
static uint32_t length(const char *s){uint32_t n=0;while(s[n])n++;return n+1;}
static uint8_t *parameter(lut_stock_entry *m,uint32_t i,uint32_t type){
    return m[i].type==type && m[i].param && !(m[i].param&7u)?(uint8_t *)(uintptr_t)m[i].param:0;
}
int32_t lut_stock_name_lines(const char *record,char out[4][65]){
    char full[64],tmp[4][65];uint32_t pos=0,row=0,col=0,chars=0,n;
    if(!out || lut_name_v617_copy(record,full,sizeof(full),0)<0)return LUT_UI_EINVAL;
    clear(tmp,sizeof(tmp));
    while(full[pos]){
        uint8_t c=(uint8_t)full[pos];n=c<0x80?1:c<0xe0?2:c<0xf0?3:4;
        if(chars==16){row++;col=0;chars=0;}
        if(row>=4 || col+n>=65)return LUT_UI_EINVAL;
        for(uint32_t j=0;j<n;j++)tmp[row][col++]=full[pos++];chars++;
    }
    for(uint32_t i=0;i<sizeof(tmp);i++)((uint8_t *)out)[i]=((uint8_t *)tmp)[i];
    return (int32_t)(row+1);
}
static void percentage(uint32_t step,char p[8]){
    uint32_t n=0;clear(p,8);if(step==10)p[n++]='1';
    p[n++]=(char)('0'+step%10);p[n++]='0';p[n]='%';
}
static int32_t bind_string(uint8_t *p,const char *text,uint32_t bytes){
    return p?lut_text_v617_bind(p,0x658,text,bytes,LUT_TEXT_V617_RESOURCE):LUT_UI_EINVAL;
}
static int32_t bind_label(uint8_t *p,const char *s,uint32_t n){
    return p?lut_ui_bind_label(p,0x658,s,n,LUT_TEXT_V617_RESOURCE):LUT_UI_EINVAL;
}
int32_t lut_localized_stock_bind(lut_stock_entry *m,uint32_t count,uint32_t scene,
                     const lut_ui_state *s,const lut_native_adapter *a,uint32_t layout){
    char lines[4][65],value[8];uint32_t indices[4],title,name,option,b,off;uint8_t *p;
    if(!m || !s || !a || s->focused_slot>LUT_UI_OFF_SLOT || !s->is_open ||
       (scene!=0xd9 && scene!=0xda) || (scene==0xda && s->focused_slot>=LUT_UI_SLOTS) || count!=(scene==0xd9?34u:107u))return LUT_UI_EINVAL;
    off=s->focused_slot==LUT_UI_OFF_SLOT;uint32_t name_is_label=off;
    if(off){
        static const char disabled[]="\xe5\x85\xb3";
        clear(lines,sizeof(lines));for(uint32_t i=0;i<sizeof(disabled);i++)lines[0][i]=disabled[i];
    }else if(lut_stock_name_lines(a->names[s->focused_slot],lines)<0){
        name_is_label=1;
        static const char invalid[]="\xe5\x90\x8d\xe7\xa7\xb0\xe6\x97\xa0\xe6\x95\x88";
        clear(lines,sizeof(lines));for(uint32_t i=0;i<sizeof(invalid);i++)lines[0][i]=invalid[i];
    }
    if(!off && !(s->valid_mask&(1u<<s->focused_slot))){
        name_is_label=1;
        static const char absent[]="\xe6\x9c\xaa\xe5\xaf\xbc\xe5\x85\xa5";
        clear(lines,sizeof(lines));for(uint32_t i=0;i<sizeof(absent);i++)lines[0][i]=absent[i];
    }
    if(off)clear(value,sizeof(value));else percentage(s->draft_step[s->focused_slot],value);
    if(scene==0xd9){
        title=12;name=11;option=13;indices[0]=11;indices[1]=16;indices[2]=17;indices[3]=18;
        p=parameter(m,9,0x1c);if(!p || lut_stock_numeric_list_bind(p,0xd68,s->focused_slot,1)<0)return LUT_UI_EINVAL;
    }else{
        title=12;name=10;option=33;indices[0]=10;indices[1]=14;indices[2]=19;indices[3]=20;
        {const char *label=lut_text_v617_strength_title(&b);
         p=parameter(m,11,2);if(bind_label(p,label,b)<0)return LUT_UI_EINVAL;}
        p=parameter(m,13,0x56);if(!p)return LUT_UI_EINVAL;
        /* Legal ten native positions. Private normal updater crops original
         * bitmap digit column without changing gauge hit geometry/cursors. */
        /* Only native param[0..3C): preserve padding and following child. */
        if(lut_gauge_parameter_bind(p,LUT_GAUGE_PARAMETER_BYTES,s->draft_step[s->focused_slot])<0)return LUT_UI_EINVAL;
        /* Exact stock touch controls: horizontal+/- use UP/DOWN; vertical
         * uses RIGHT/LEFT, translated only in the private editor scene. */
        p=parameter(m,38,0xe);if(!p)return LUT_UI_EINVAL;*(uint32_t *)(p+0x34)=0x2010000u;
        p=parameter(m,36,0xe);if(!p)return LUT_UI_EINVAL;*(uint32_t *)(p+0x34)=0x2010003u;
        p=parameter(m,35,0x13);if(!p)return LUT_UI_EINVAL;*(uint32_t *)(p+0x30)=0x2010000u;
        p=parameter(m,34,0x13);if(!p)return LUT_UI_EINVAL;*(uint32_t *)(p+0x30)=0x2010003u;
        p=parameter(m,16,0x14);if(!p)return LUT_UI_EINVAL;
        /* Type14+34/+36/+38/+3A are signed16 hit margins: native
         *18CF5A0..5B8 -> Widget::setHitMarginEssss. They are not event
         * fields; its release callback18CF6E0..740 emits3010002. */
        *(uint16_t *)(p+0x34)=0xf;*(uint16_t *)(p+0x36)=9;
        *(uint16_t *)(p+0x38)=9;*(uint16_t *)(p+0x3a)=9;
        for(uint32_t i=21;i<=22;i++){
            p=parameter(m,i,2);if(!p)return LUT_UI_EINVAL;
            if(layout==0){const char *label=i==21?"100%":"10%";
                if(bind_string(p,label,i==21?5:4)<0)return LUT_UI_EINVAL;
            }else p[0x2c]=0; /* portrait crop/axis not accepted this generation */
        }
    }
    (void)name;
    p=parameter(m,title,2);if(!p)return LUT_UI_EINVAL;
    {const char *t=lut_text_v617_title(&b);if(bind_label(p,t,b)<0)return LUT_UI_EINVAL;}
    for(uint32_t i=0;i<4;i++){
        p=parameter(m,indices[i],2);if((i==0&&name_is_label?bind_label:bind_string)(p,lines[i],length(lines[i]))<0)return LUT_UI_EINVAL;
        p[0x2c]=lines[i][0]?1:0;
    }
    p=parameter(m,option,0x5e);if(!p)return LUT_UI_EINVAL;p[0x2c]=!off;
    if(scene==0xd9){
     const char *status=p4_gui_status();
     p=parameter(m,19,2);if(bind_label(p,status,length(status))<0)return LUT_UI_EINVAL;p[0x2c]=status[0]!=0;}
    p=parameter(m,5,0x18);if(!p)return LUT_UI_EINVAL;
    /* Original resource+width table37F2D10: kindF = native OK, MENU取消,
     * trash-key重置. Event table37F41D0 yields201000C/201000F/2030000.
     * Kind8 preserves selector OK/MENU/trash-help original legend. */
    *(uint32_t *)(p+0x30)=scene==0xda?0xfu:8u;p[0x2c]=1;
    return LUT_UI_OK;
}
int32_t lut_stock_edit_begin(lut_ui_state *s,uint32_t *entry){
    int32_t r;if(!s || !entry || s->pane!=LUT_UI_SLOT_PANE || s->focused_slot>LUT_UI_OFF_SLOT)return LUT_UI_EINVAL;
    if(s->focused_slot==LUT_UI_OFF_SLOT)return LUT_UI_NO_CHANGE;
    r=lut_ui_event_apply(s,LUT_UI_RIGHT);if(r!=LUT_UI_OK)return r;
    *entry=s->draft_step[s->focused_slot];return LUT_UI_OK;
}
static int32_t set_step(lut_ui_state *s,uint32_t step){
    if(!s || !s->is_open || s->focused_slot>=16 || s->pane!=LUT_UI_STRENGTH_PANE || step<1 || step>10)return LUT_UI_EINVAL;
    while(s->draft_step[s->focused_slot]!=step){
        int32_t r=lut_ui_event_apply(s,s->draft_step[s->focused_slot]<step?LUT_UI_UP:LUT_UI_DOWN);if(r<0)return r;
    }return LUT_UI_OK;
}
int32_t lut_stock_edit_finish(lut_ui_state *s,uint32_t entry,uint32_t accept){
    int32_t r;if(accept>1 || entry<1 || entry>10)return LUT_UI_EINVAL;
    if(!accept && (r=set_step(s,entry))<0)return r;
    return lut_ui_event_apply(s,LUT_UI_LEFT);
}
int32_t lut_stock_edit_reset(lut_ui_state *s){return set_step(s,10);}
int32_t lut_stock_touch_index(lut_ui_state *s,uint32_t widget,uint32_t target,uint32_t index){
    if(widget!=13 || target!=0xda || index>9)return LUT_UI_EINVAL;
    return set_step(s,index+1);
}
