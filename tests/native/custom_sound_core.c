#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "sound_core.h"

static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"check failed at line %d\n",__LINE__); return 1; } } while(0)
static int commit_ok(void *context,const ss_state *candidate) {(void)context;(void)candidate;return 0;}
static int commit_fail(void *context,const ss_state *candidate) {(void)context;(void)candidate;return -1;}
static void le16(uint8_t *p,uint32_t x) {p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);}
static void le32(uint8_t *p,uint32_t x) {le16(p,x);le16(p+2,x>>16);}

int main(void) {
 uint8_t wav[48]={0};memcpy(wav,"RIFF",4);le32(wav+4,40);memcpy(wav+8,"WAVEfmt ",8);
 le32(wav+16,16);le16(wav+20,1);le16(wav+22,1);le32(wav+24,8000);le32(wav+28,16000);
 le16(wav+32,2);le16(wav+34,16);memcpy(wav+36,"data",4);le32(wav+40,4);le16(wav+44,4096);le16(wav+46,61440);
 ss_state state,restored;ss_init(&state);ss_init(&restored);
 ss_native native={0,1,SS_SHUTTER_ELECTRONIC,SS_AFS};ss_playback play;ss_format format;
 CHECK(ss_parse_wav(wav,sizeof(wav),&format)==SS_OK && format.frames==2);
 int32_t samples[2];CHECK(ss_decode_frames_q31(wav,sizeof(wav),0,2,samples,2,&format)==SS_OK);
 CHECK(samples[0]==268435456 && samples[1]==-268435456);
 CHECK(!ss_valid_name("../bad.wav",10));CHECK(ss_valid_name("focus.WAV",9));
 CHECK(ss_import(&state,SS_FOCUS,"focus.WAV",9,wav,sizeof(wav),commit_ok,0)==SS_DISABLED);
 CHECK(ss_set_enabled(&state,SS_FOCUS,1,SS_SHUTTER_ELECTRONIC,commit_ok,0)==SS_OK);
 CHECK(ss_import(&state,SS_FOCUS,"focus.WAV",9,wav,sizeof(wav),commit_ok,0)==SS_OK);
 CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_PLAY_FOCUS);
 native.focus=SS_AFA;CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_PLAY_FOCUS);
 native.focus=SS_AFC;CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_NATIVE_FOCUS);
 native.focus=SS_MF;CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_SUPPRESS);
 native.focus=SS_AFS;native.audio_signals=0;CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_SUPPRESS);
 native.audio_signals=1;
 CHECK(ss_set_enabled(&state,SS_ELECTRONIC,1,SS_SHUTTER_ELECTRONIC,commit_ok,0)==SS_OK);
 CHECK(ss_import(&state,SS_ELECTRONIC,"shot.wav",8,wav,sizeof(wav),commit_ok,0)==SS_OK);
 CHECK(ss_plan(&state,&native,SS_ELECTRONIC_EXPOSURE,&play)==SS_OK && play.route==SS_PLAY_ELECTRONIC);
 native.silent=1;
 CHECK(ss_plan(&state,&native,SS_ELECTRONIC_EXPOSURE,&play)==SS_OK && play.route==SS_SUPPRESS);
 CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_SUPPRESS);
 native.silent=0;ss_state old=state;
 CHECK(ss_set_enabled(&state,SS_ELECTRONIC,0,SS_SHUTTER_ELECTRONIC,commit_fail,0)==SS_STORAGE);
 CHECK(memcmp(&old,&state,sizeof(state))==0);
 uint8_t snapshot[4096];size_t written=0;
 CHECK(ss_snapshot_write(&state,snapshot,sizeof(snapshot),&written)==SS_OK);
 CHECK(ss_snapshot_restore(&restored,snapshot,written)==SS_OK);
 CHECK(restored.generation==state.generation && restored.slots[0].custom && restored.slots[1].custom);
 CHECK(!memcmp(restored.slots[0].wav,wav,sizeof(wav)));
 ss_state previous=restored;snapshot[written-1]^=1;
 CHECK(ss_snapshot_restore(&restored,snapshot,written)==SS_CORRUPT);
 CHECK(!memcmp(&restored,&previous,sizeof(previous)));
 CHECK(ss_native_shutter_changed(&state,SS_SHUTTER_MECHANICAL,commit_ok,0)==SS_OK && !state.slots[0].enabled);
 CHECK(ss_set_enabled(&state,SS_ELECTRONIC,1,SS_SHUTTER_MECHANICAL,commit_ok,0)==SS_INCOMPATIBLE);
 CHECK(ss_focus_default(&state,commit_ok,0)==SS_OK);
 CHECK(ss_plan(&state,&native,SS_FOCUS_CONFIRMED,&play)==SS_OK && play.route==SS_NATIVE_FOCUS);
 ss_menu_view view;CHECK(ss_get_menu_view(&state,SS_ELECTRONIC,&view)==SS_OK && !view.import_selectable);
 wav[4]=1;CHECK(ss_parse_wav(wav,sizeof(wav),&format)==SS_WAV_INVALID);
 printf("{\"checks\":%u,\"passed\":true,\"camera_io\":false}\n",checks);return 0;
}
