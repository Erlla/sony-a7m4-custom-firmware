#ifndef CSND_EVENT_RUNTIME_H
#define CSND_EVENT_RUNTIME_H
typedef unsigned char er_u8;
typedef unsigned int er_u32;
typedef unsigned long long er_u64;
/* Resource manager owns registration, immutable sample lifetime and native
 * submission. These are unresolved link contracts, never success stubs in a
 * deployed image. All resource calls except focus_mode occur on this worker.
 * focus_mode: 0 stock; 1 CP native kind4 overlay (AP MUST NOT replay);
 * 2 stock positively muted + a separately registered kind (conditional only).
 */
extern int csnd_resource_tick(er_u64 app_base,er_u32 revision);
extern er_u32 csnd_resource_focus_mode(void);
extern int csnd_resource_dispatch(er_u64 app_base,er_u32 slot,er_u32 generation,er_u32 epoch);

void csnd_event_startup(void); /* same ABI as old8F9C080; fixed linker anchor */
void csnd_event_config_changed(void); /* same ABI as old8F9C000; atomic only */
void csnd_event_exposure(const er_u8 *packet); /* old8F9C13C */
int csnd_event_focus(const er_u8 *packet,er_u32 source); /* old8F9C420 */
void csnd_event_worker(void *unused);
void csnd_event_pump(void); /* one worker iteration, exposed for verification */
void csnd_event_snapshot(er_u32 out[32]); /* successive acquire loads, not atomic */
er_u32 csnd_event_revision(void);
/* Worker-only successful fresh-lease session edge; 0 defers without mutation. */
int csnd_event_resource_epoch(er_u32 expected_revision);
#endif
