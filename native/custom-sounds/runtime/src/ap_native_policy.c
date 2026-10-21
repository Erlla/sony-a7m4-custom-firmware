#include "ap_native_policy.h"
extern uint32_t csnd_native_silent_get(void);
extern uint32_t csnd_native_audio_get(void);
extern uint32_t csnd_native_focus_get(void);
extern uint32_t csnd_native_shutter_60a_get(void);
extern uint32_t csnd_native_shutter_60b_get(void);
int csnd_ap_normalize_native(const csnd_native_inputs *in,ss_native *out) {
    ss_native result={1,0,SS_SHUTTER_MECHANICAL,SS_MF};
    if(!out)return SS_INVALID;
    *out=result;
    if(!in || in->effective_known>1)return SS_INVALID;
    if(in->silent_raw==0)result.silent=1;
    else if(in->silent_raw==1)result.silent=0;
    else return SS_INVALID;
    /* This field gates focus only in ss_plan. The new electronic tone has
     * its own custom switch and follows silent/shutter; do not apply the
     * stock electronic-audio permission bit to both custom sounds. */
    switch(in->audio_raw) {
    case 0:case 3:result.audio_signals=1;break;
    case 2:case 5:result.audio_signals=0;break;
    default:return SS_INVALID;
    }
    switch(in->focus_raw) {
    case 0:result.focus=SS_AFS;break;
    case 1:result.focus=SS_AFA;break;
    case 2:case 3:case 4:case 5:result.focus=SS_AFC;break;
    case 6:result.focus=SS_MF;break;
    default:return SS_INVALID;
    }
    if(in->shutter_parameter==0x60a) {
        if(in->shutter_raw==0)result.shutter=SS_SHUTTER_MECHANICAL;
        else if(in->shutter_raw==1)result.shutter=SS_SHUTTER_ELECTRONIC;
        else return SS_INVALID;
    } else if(in->shutter_parameter==0x60b) {
        switch(in->shutter_raw) {
        case 0:
            if(!in->effective_known || in->effective_shutter>SS_SHUTTER_EFCS)return SS_INVALID;
            result.shutter=in->effective_shutter;break;
        case 1:result.shutter=SS_SHUTTER_MECHANICAL;break;
        case 2:result.shutter=SS_SHUTTER_ELECTRONIC;break;
        default:return SS_INVALID;
        }
    } else return SS_INVALID;
    /* A mechanical request that has not yet reached a storage worker blocks
     * electronic playback immediately and cannot be reinterpreted as AUTO. */
    if(csnd_ap_mechanical_pending())result.shutter=SS_SHUTTER_MECHANICAL;
    *out=result;return SS_OK;
}
int csnd_ap_read_native(uint32_t parameter,uint32_t known,uint32_t effective,ss_native *out) {
    csnd_native_inputs in;
    if(!out)return SS_INVALID;
    *out=(ss_native){1,0,SS_SHUTTER_MECHANICAL,SS_MF};
    if(parameter!=0x60a && parameter!=0x60b)return SS_INVALID;
    in.silent_raw=csnd_native_silent_get();
    in.audio_raw=csnd_native_audio_get();
    in.focus_raw=csnd_native_focus_get();
    in.shutter_parameter=parameter;
    in.shutter_raw=parameter==0x60a?csnd_native_shutter_60a_get():csnd_native_shutter_60b_get();
    in.effective_known=known;in.effective_shutter=effective;
    return csnd_ap_normalize_native(&in,out);
}
