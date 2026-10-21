#include <stdint.h>
#include <stddef.h>
#include "resource.h"
extern void csnd_event_snapshot(uint32_t out[32]);
extern uint32_t csnd_volume_get(uint32_t);
extern void csnd_resource_driver_snapshot(uint32_t out[64]);
extern void csnd_resource_fault_snapshot(uint32_t out[26]);
extern void csnd_resource_focus_snapshot(uint32_t out[9]);
extern uint32_t csnd_original_crc32(const uint8_t *,size_t);
/* RAM-only export. Old maintenance diagnostics are deliberately retired in639;
 * current maintenance status remains in the event/core records. */
uint32_t csnd_native_diagnostic_crc(const uint8_t *input,size_t bytes){
 if(input&&bytes==1532){
  static const char tag[8]={'C','S','N','D','0','6','4','4'};
  uint32_t matches=1;for(uint32_t i=0;i<8;i++)if(input[i]!=(uint8_t)tag[i])matches=0;
  if(matches){
   uint32_t*w=(uint32_t*)(uintptr_t)input;
   for(uint32_t i=288;i<383;i++)w[i]=0;
   w[288]=0x544e5645;w[289]=1;csnd_event_snapshot(w+290);
   w[322]=0x5345524e;w[323]=1;csnd_resource_snapshot(w+324);
   w[356]=0x54535043;w[357]=1;csnd_resource_cp_snapshot(w+358);
   csnd_resource_driver_snapshot(w+32);
   csnd_resource_focus_snapshot(w+96);
   w[374]=0x4c4f5643;w[375]=1;w[376]=csnd_volume_get(0);w[377]=csnd_volume_get(1);
   static const uint16_t index[26]={90,91,92,93,94,95,105,106,107,108,109,110,111,280,281,282,283,284,285,286,287,378,379,380,381,382};uint32_t fault[26];
   csnd_resource_fault_snapshot(fault);for(uint32_t i=0;i<26;i++)w[index[i]]=fault[i];
  }
 }
 return csnd_original_crc32(input,bytes);
}
