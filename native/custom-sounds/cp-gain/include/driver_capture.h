#ifndef DRIVER_CAPTURE_H
#define DRIVER_CAPTURE_H
typedef unsigned int u32;
typedef unsigned char u8;
/* Query returns one complete record: no asynchronous field mixing. */
struct driver_record20 {
 u32 sequence,tick_raw,kind,result,phys_lo,phys_hi,generation,revision;
 u32 format,base,capacity,start,end,last_gain_caller,gain_receipt;
 u32 bus_base,bus_capacity,bus_start,bus_end,flags;
};
struct driver_record {
 u32 sequence,tick_raw,kind,result,phys_lo,phys_hi,generation,revision;
 u32 format,base,capacity,start,end,last_gain_caller,gain_receipt;
 u32 bus_base,bus_capacity,bus_start,bus_end,flags;
 u32 stock_kind,stock_volume,gain3904,gain3908;
};
struct driver_diag {
 volatile u32 gate,version;u32 sequence,missed,entry_sp,pending_kind;
 struct driver_record20 pending;struct driver_record record[2];
};
extern struct driver_diag csnd_driver_diag;
void csnd_driver_pre(u32 entry_sp);
void csnd_driver_post(u32 entry_sp,u32 result);
u32 csnd_driver_query(u32 kind,struct driver_record*out,u32*meta);
/* page0 header; pages1..6 require exact header sequence, else STALE=3. */
u32 csnd_driver_page(u32 kind,u32 page,u32 expected_sequence,u32*out4);
#endif

_Static_assert(sizeof(struct driver_record20)==80,"old pending ABI");
_Static_assert(sizeof(struct driver_record)==96,"new record ABI");
_Static_assert(sizeof(struct driver_diag)==296,"BSS grows exactly32");
