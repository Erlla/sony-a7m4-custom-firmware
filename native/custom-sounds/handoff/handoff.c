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
extern void admission_original(void *,const void *);
extern void begin_original(void *,const void *,u32);
extern void app_admission_original(void *,const void *);
void sound_handoff_tick(void);

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
static void reject(void *object,const void *request) {
    ((void (*)(void *,u32,const void *))0x5ddcc7)(object,0xe005,request);
}
static void dispatch(struct job *j) {
    queue.dispatching=1;
    if(j->object&2u) app_admission_original((void*)(j->object&~3u),j->request);
    else if(j->object&1u) begin_original((void*)(j->object&~3u),j->request,j->mode);
    else admission_original((void*)j->object,j->request);
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
    if(request[0]==2){cancel(request[2]);return 0;}
    if(request[0]!=1)return 0;
    if(!enabled() && !queue.count)return 0;
    u32 current=B(0xf57b4e),pin_kind=B(0x121f196);
    /* Leave unrelated original sounds under native arbitration. For the
     * focus/shutter pair, every new Start supersedes either waiting kind. */
    if(request[2]==4 && !queue.count && current!=4 && current!=17 && pin_kind!=4 && pin_kind!=17)return 0;
    cancel(17);cancel(4);
    if(!queue.count && !busy())return 0;
    if(queue.count==CAP){reject(object,request);return 1;}
    if(!queue.count){queue.generation=W(0x1564860);queue.revision=W(0x1564864);}
    struct job *j=&queue.jobs[(queue.head+queue.count)&(CAP-1)];
    j->object=(u32)object|entry;j->mode=entry==1?mode:0;
    for(u32 i=0;i<32;i++)((u8*)j->request)[i]=request[i];
    queue.count++;
    if(queue.count==1 && schedule(0)>1){queue.count=0;reject(object,request);return 1;}
    /* Either kind preempts the active focus/shutter through original Stop.
     * Do not issue another Stop while it is already retiring. */
    if((current==4 || current==17) && B(0xf57b4c)==1 && W(0x121f118)==2) {
        u32 stop[8]={0};((u8*)stop)[0]=2;((u8*)stop)[2]=(u8)current;
        queue.dispatching=1;admission_original(object,stop);queue.dispatching=0;
    }
    return 1;
}
void sound_handoff_tick(void) {
    if(!queue.count){schedule(1);return;}
    if(busy())return;
    struct job j=queue.jobs[queue.head];
    queue.head=(queue.head+1)&(CAP-1);queue.count--;
    if(!queue.count)schedule(1);
    if(((u8*)j.request)[2]==17 && (!enabled() || queue.generation!=W(0x1564860) || queue.revision!=W(0x1564864))) {
        reject((void*)(j.object&~3u),j.request);return;
    }
    dispatch(&j);
}
