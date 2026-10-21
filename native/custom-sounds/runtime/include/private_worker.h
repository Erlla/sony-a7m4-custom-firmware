#ifndef CSND_PRIVATE_WORKER_H
#define CSND_PRIVATE_WORKER_H
#include "ap_sd_backend.h"
/* A private derived native Sequence. Only first16B are native base fields.
 * No original CLUT property, name/list model or original job field is reused. */
enum csnd_operation { CSND_SCAN=1,CSND_IMPORT=2,CSND_ENABLE=3,CSND_DEFAULT=4,CSND_NATIVE_DRAIN=5,CSND_COLD_LOAD=6 };
enum csnd_session_phase { CSND_IDLE=0,CSND_QUEUED=1,CSND_RUNNING=2,CSND_COMPLETE=3,CSND_CANCELED=4 };
typedef struct {
    uint32_t references,gate,generation,slot,phase,status,selected,card;
    uint8_t media[0x150];
    csnd_picker_list list;
} csnd_private_session;
typedef struct {
    uintptr_t *vtable;
    void *native_context;
    uint32_t magic,schema,generation,operation,slot,card,row,name_bytes;
    uint32_t enabled,shutter,reserved[2];
    csnd_private_session *session;
    uint8_t media[0x150];
    char name[256];
    uintptr_t private_vtable[7];
} csnd_private_job;
csnd_private_session *csnd_private_session_create(uint32_t generation,uint32_t slot,const uint8_t *media,uint32_t card);
void csnd_private_session_release(csnd_private_session *);
int csnd_private_cancel(csnd_private_session *,uint32_t generation);
int csnd_private_list_copy(csnd_private_session *,uint32_t generation,csnd_picker_list *);
csnd_private_job *csnd_private_job_create(csnd_private_session *,uint32_t operation,uint32_t row,uint32_t enabled,uint32_t shutter);
void csnd_private_job_execute(csnd_private_job *);
void csnd_private_job_cancel(csnd_private_job *);
void csnd_private_job_abandon(csnd_private_job *);
void csnd_private_job_destroy(csnd_private_job *);
void csnd_private_job_delete(csnd_private_job *);
/* Explicit manager is obtained by the native GUI adapter, then this hands
 * ownership to the actual native3305084 registry. No direct worker dispatch.
 * GUI linkage and real startup map/queue initialization remain separate gates. */
int csnd_private_submit(void *manager,csnd_private_session *,uint32_t operation,uint32_t row,uint32_t enabled,uint32_t shutter);
#endif
