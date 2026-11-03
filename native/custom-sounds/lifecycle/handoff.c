/* Serialize focus/shutter at the original Sysnd task admission boundary.
 * Queue contains values only; native completion and buffer ownership stay native.
 */
#include <stdint.h>
typedef uint32_t u32;
typedef uint8_t u8;
void *memset(void *p,int v,unsigned n){u8 *b=p;while(n--)*b++=(u8)v;return p;}
#define W(a) (*(volatile u32 *)(a))
#define B(a) (*(volatile u8 *)(a))
#define CAP 32u
struct job {u32 object, mode; u32 request[8];};
struct state {u32 head, count, dispatching, generation, revision; struct job jobs[CAP];};
static struct state queue;
extern u32 admission_original(void *,const void *);
extern u32 begin_original(void *,const void *,u32);
extern u32 app_admission_original(void *,const void *);
u32 sound_admission_guard(void *,const u8 *,u32,u32);
void sound_handoff_tick(void);
void release_focus_reservation(void);

static u32 schedule(u32 remove) {
    u32 row[2]={2,(u32)sound_handoff_tick};
    void *scheduler=((void *(*)(void))0x5dcd63)();
    return ((u32 (*)(void *,void *))(remove?0x5dcf13:0x5dced3))(scheduler,row);
}
/* Common pending is an operation code: 1=Start, 2=Stop. Native Stop may
 * leave a 2 after cancellation before playback; 5DE37A only consumes 1.
 * A completed Stop is not an outstanding playback owner. */
static u32 busy(void) {
    return W(0x121f118)|W(0x121f130)|W(0xfc6aec)|W(0xfc6af0)|W(0xfc6b20)|W(0xfc6b38)|(B(0xf57bac)==1u);
}
static u32 enabled(void) {
    return W(0x1564844) && W(0x1564870)==6 && !W(0x1564874) && (W(0xf4aecc)&2);
}
static u32 custom_focus(void) {
    return W(0x1564844) && W(0x15648a8)==6 && !W(0x15648ac);
}
/* A staging transaction must not retain native requests that the AP Stop
 * barrier is waiting to complete. New starts are settled before admission. */
u32 preparing(void) {
    return W(0x1564844) && (W(0x1564874) || W(0x1564870)==5 ||
                              W(0x15648ac) || W(0x15648a8)==5);
}
static void retire_pair(void *object) {
    u32 current=B(0xf57b4e);
    if((current==4 || current==17) && B(0xf57b4c)==1 && W(0x121f118)==2) {
        u32 stop[8]={0};((u8*)stop)[0]=2;((u8*)stop)[2]=(u8)current;
        queue.dispatching=1;admission_original(object,stop);queue.dispatching=0;
    }
}
static void reject(void *object,const void *request) {
    ((void (*)(void *,u32,const void *))0x5ddcc7)(object,0xe005,request);
}
/* Rewind an already active immutable PCM clip through the original DMA API.
 * Its native completion timer and Sysnd resource lease stay in place. Do not
 * re-run property/format/gain setup or discard the new focus notification. */
static u32 restart_focus(void) {
    if(W(0xfc6b20)!=2 || W(0xfc6aec)!=1 || B(0xfc6b19))return 0;
    if(((u32 (*)(u32))0xa56c57)(0))return 0;
    /* The same per-run progress counters are cleared by native first start. */
    W(0x145b070)=0;W(0x145b074)=0;
    return !((u32 (*)(void *,const void *,u32))0xa55d73)(
        (void*)0xfc6ad8,(const void*)0xfc6af4,0);
}
static void dispatch(struct job *j) {
    queue.dispatching=1;
    sound_admission_guard((void*)(j->object&~3u),(u8*)j->request,j->mode,j->object&3u);
    queue.dispatching=0;
}
static void cancel(u32 kind) {
    u32 kept=0,old=queue.count;
    for(u32 i=0;i<old;i++) {
        struct job *j=&queue.jobs[(queue.head+i)&(CAP-1)];
        if(((u8*)j->request)[2]==kind)reject((void*)(j->object&~3u),j->request);
        else {queue.jobs[(queue.head+kept)&(CAP-1)]=*j;kept++;}
    }
    queue.count=kept;if(old && !kept)schedule(1);
}
/* PIN admission, APP admission and common begin share one latest-value queue. */
u32 sound_handoff_admit(void *object,const u8 *request,u32 mode,u32 entry) {
    if(queue.dispatching || (request[2]!=4 && request[2]!=17))return 0;
    if(request[0]==2){cancel(request[2]);release_focus_reservation();return 0;}
    if(request[0]!=1)return 0;
    u32 blocked=preparing();
    if(blocked){cancel(17);cancel(4);reject(object,request);retire_pair(object);return 1;}
    if(!blocked && !enabled() && !custom_focus() && !queue.count)return 0;
    u32 current=B(0xf57b4e),pin_kind=B(0x121f196);
    /* Leave unrelated original sounds under native arbitration. For the
     * focus/shutter pair, every new Start supersedes either waiting kind. */
    if(request[2]==4 && !blocked && !queue.count && current!=4 && current!=17 && pin_kind!=4 && pin_kind!=17)return 0;
    cancel(17);cancel(4);
    /* A new same-focus event restarts the current clip at its first sample.
     * Explicit Stop, retirement and cross-kind events keep native handoff. */
    if(request[2]==4 && custom_focus() && current==4 && B(0xf57b4c)==1 &&
       W(0x121f118)==2 && W(0x121f130)==1 && B(0xf57bac)!=2 &&
       B(0x121f134)!=2 && B(0x121f194)!=2 &&
       !W(0xfc6af0) && !W(0xfc6b38) && restart_focus()) {
        reject(object,request);return 1;
    }
    if(!queue.count && !busy() && !blocked)return 0;
    if(queue.count==CAP){reject(object,request);return 1;}
    if(!queue.count){queue.generation=W(0x1564860);queue.revision=W(0x1564864);}
    struct job *j=&queue.jobs[(queue.head+queue.count)&(CAP-1)];
    j->object=(u32)object|entry;j->mode=entry==1?mode:0;
    for(u32 i=0;i<32;i++)((u8*)j->request)[i]=request[i];
    queue.count++;
    if(queue.count==1 && schedule(0)>1){queue.count=0;reject(object,request);return 1;}
    /* Either kind preempts the active focus/shutter through original Stop.
     * Do not issue another Stop while it is already retiring. */
    retire_pair(object);
    return 1;
}
void sound_handoff_tick(void) {
    if(!queue.count){schedule(1);return;}
    if(preparing()){
        void *object=(void*)(queue.jobs[queue.head].object&~3u);
        cancel(17);cancel(4);retire_pair(object);return;
    }
    if(busy())return;
    struct job j=queue.jobs[queue.head];
    queue.head=(queue.head+1)&(CAP-1);queue.count--;
    if(!queue.count)schedule(1);
    if(((u8*)j.request)[2]==17 && (!enabled() || queue.generation!=W(0x1564860) || queue.revision!=W(0x1564864))) {
        reject((void*)(j.object&~3u),j.request);return;
    }
    dispatch(&j);
}
/* Protect the native lookup -> publication gap. After original admission has
 * published its busy/current row, that native state becomes the resource lease
 * until the accepted property callback has actually started and completed.
 * Stop never takes this reader, so it can always retire an existing actor. */
u32 sound_admission_guard(void *object,const u8 *request,u32 mode,u32 entry) {
    u32 held=0;
    volatile u32 *gate=(volatile u32*)0x1564840;
    if(request[0]==1 && (request[2]==4 || request[2]==17)) {
        u32 value=__atomic_load_n(gate,__ATOMIC_ACQUIRE);
        if((value&0x80000000u) || value==0x7fffffffu ||
           !__atomic_compare_exchange_n(gate,&value,value+1,1,__ATOMIC_ACQ_REL,__ATOMIC_RELAXED)) {
            reject(object,request);return 0;
        }
        held=1;
        if(preparing()) {
            __atomic_fetch_sub(gate,1,__ATOMIC_RELEASE);
            reject(object,request);return 0;
        }
    }
    u32 rc=entry==2?app_admission_original(object,request):
           entry==1?begin_original(object,request,mode):admission_original(object,request);
    if(held)__atomic_fetch_sub(gate,1,__ATOMIC_RELEASE);
    return rc;
}
