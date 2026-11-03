#include <stdint.h>
typedef uint32_t u32;
/* Gain selection only reads an immutable active bank. It shares the same
 * reader counter as admission and still refuses an exclusive writer. */
u32 gain_reader_acquire(volatile u32 *gate) {
    u32 old=__atomic_load_n(gate,__ATOMIC_ACQUIRE);
    for(;;) {
        if((old&0x80000000u) || old==0x7fffffffu)return 0;
        if(__atomic_compare_exchange_n(gate,&old,old+1,0,
            __ATOMIC_ACQ_REL,__ATOMIC_RELAXED))return 1;
    }
}
void gain_reader_release(volatile u32 *gate) {
    __atomic_fetch_sub(gate,1,__ATOMIC_RELEASE);
}
