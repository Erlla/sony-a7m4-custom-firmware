#ifndef CSND_MAINTENANCE_SCHEDULER_H
#define CSND_MAINTENANCE_SCHEDULER_H
#include "private_worker.h"
/* bit0 = original manager/dependency-map/queues initialized;
 * bit1 = original /setting mounted and readable. These facts must come from
 * proved original startup consumers. Merely passing3 is not their proof. */
int csnd_maintenance_arm(void *manager,uint32_t proven_readiness_mask);
void csnd_maintenance_after_execute(void *manager,void *native_job);
/* Original postexecute consumer also supports automatic startup: exact native
 * manager + unrelated completed job + live statfsVFAT/rw/accessW_OK guard.
 * Guard failure retries only at a later unrelated native completion. */
typedef struct {uint32_t armed,cold_done,cold_status,mechanical_status,queued,generation;} csnd_maintenance_view;
int csnd_maintenance_view_copy(csnd_maintenance_view *out);
#endif
