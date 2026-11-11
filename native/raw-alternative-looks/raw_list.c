/* CP-native twelve-look RAW export; the persistent backup stays unchanged. */
typedef unsigned char u8;
typedef unsigned int u32;

__attribute__((section(".raw_constructor")))
void raw_list_construct(void *destination, u32 mode)
{
    volatile u8 *config = (volatile u8 *)0x014f6fc1;
    config[0x7a] = 10;
    config[0x7b] = 11;
    config[3] = 12;
    ((void (*)(void *, u32))0x00a02a61)(destination, mode);
}

__attribute__((section(".raw_mapping")))
int raw_list_mapping(u32 value, u32 *output)
{
    const volatile u8 *config = (const volatile u8 *)0x014f6fc1;
    for (u32 i = 0; i < config[3]; ++i) {
        if (config[0x70+i] == value) {
            *output = i;
            return 0;
        }
    }
    return -4;
}

__attribute__((section(".raw_quantity")))
int raw_list_quantity(u8 *output)
{
    u32 value = *(const volatile u8 *)0x014f6fc4;
    *output = (u8)value;
    return value == 10 || value == 12 ? 0 : -4;
}
