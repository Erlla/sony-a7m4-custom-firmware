/* One canonical selection for menu, serializer and read-only preview.
 * File restoration happens at existing menu/serializer entries or once after
 * a recording view is created, before it is registered for preview production.
 * Preview readers never initialize, wait, acquire model locks or perform I/O.
 */
#include <stdint.h>
extern uint32_t native_aspect_get(void);
extern void native_aspect_set(uint32_t);
extern void native_aspect_commit(uint32_t);
extern int native_open(const char *,int,...);
extern long native_read(int,void *,unsigned long);
extern long native_write(int,const void *,unsigned long);
extern int native_close(int);
extern int native_fsync(int);
extern int native_rename(const char *,const char *);
extern void aspect_trace_stamp(uint32_t,uint32_t);

typedef struct { uint32_t restore_claim,selection,persist_status,reserved; } selection_state;
selection_state aspect_preview_selection_state;
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
static const char config[]="/setting/custom_aspect_v2.dat";
static const char temporary[]="/setting/custom_aspect_v2.tmp";

uint32_t aspect_ap_completed_selection_read(void)
{
    return LOAD(&aspect_preview_selection_state.selection);
}

static uint32_t normalize(uint32_t id) { return id>=4 && id<=9 ? id : 0; }

/* Explicit selection wins over an earlier, still-running restore. Epochs
 * invalidate cached preview geometry, including a cancel back to the same id.
 * On exhaustion, fail closed until process restart rather than reusing tokens.
 */
uint32_t aspect_preview_publish_select(uint32_t id)
{
    uint32_t old=aspect_ap_completed_selection_read(),next;
    do {
        next=(old>>5)>=0x07fffffeu ? 0xffffffe0u :
             (((old>>5)+1u)<<5)|16u|normalize(id);
    } while(!__atomic_compare_exchange_n(&aspect_preview_selection_state.selection,
               &old,next,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE));
    return next;
}

void aspect_preview_initialize(void)
{
    uint32_t expected=0;
    if(!__atomic_compare_exchange_n(&aspect_preview_selection_state.restore_claim,
            &expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
    uint32_t value[4],id=0;
    int fd=native_open(config,0x80000);
    if(fd>=0) {
        long n=native_read(fd,value,sizeof(value));
        uint8_t extra;
        long more=native_read(fd,&extra,1);
        int closed=native_close(fd);
        if(n==sizeof(value) && more==0 && closed==0 && value[0]==0x32505243 &&
           value[1]==2 && value[2]>=4 && value[2]<=9 && value[3]==~value[2])id=value[2];
    }
    /* Publish only a fully read, validated, closed local result. */
    expected=0;
    __atomic_compare_exchange_n(&aspect_preview_selection_state.selection,
        &expected,0x30u|id,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
}

static void persist(uint32_t id)
{
    uint32_t value[]={0x32505243,2,id,~id};
    STORE(&aspect_preview_selection_state.persist_status,1);
    int fd=native_open(temporary,0x80241,0600);
    if(fd<0)return;
    long n=native_write(fd,value,sizeof(value));
    int synced=native_fsync(fd),closed=native_close(fd);
    if(n!=sizeof(value) || synced || closed || native_rename(temporary,config))return;
    fd=native_open("/setting",0x90000);
    if(fd<0)return;
    synced=native_fsync(fd);closed=native_close(fd);
    if(!synced && !closed)STORE(&aspect_preview_selection_state.persist_status,0);
}

uint32_t aspect_preview_effective(uint32_t native)
{
    aspect_preview_initialize();
    uint32_t token=aspect_ap_completed_selection_read(),id=token&15u;
    return native==0 && (token&16u) && id>=4 ? id : native;
}

uint32_t aspect_preview_menu_get(void)
{
    return aspect_preview_effective(native_aspect_get());
}

void aspect_preview_menu_set(uint32_t id)
{
    if(id>9)return;
    aspect_preview_initialize();
    aspect_preview_publish_select(id);
    native_aspect_set(id>=4 ? 0 : id);
}

uint32_t aspect_preview_before_apply(uint32_t alias)
{
    if(alias>=126 && alias<=129) {
        aspect_preview_initialize();
        aspect_preview_publish_select(0);
    } else if(alias>=5632 && alias<=5637) {
        aspect_trace_stamp(22,alias);
        aspect_preview_initialize();
        aspect_preview_publish_select(alias-5632+4);
        return 126;
    }
    return alias;
}

void aspect_preview_menu_commit(uint32_t alias)
{
    aspect_trace_stamp(42,alias);
    uint32_t id;
    if(alias>=126 && alias<=129)id=alias-126;
    else if(alias>=5632 && alias<=5637)id=alias-5632+4;
    else return;
    aspect_preview_initialize();
    aspect_preview_publish_select(id);
    native_aspect_commit(id>=4 ? 126 : alias);
    persist(normalize(id));
}
