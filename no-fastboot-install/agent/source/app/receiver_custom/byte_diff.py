from product_integrity import pinned, state_path
BLOCK_BYTES = 64 * 1024
BYTE_LOW_BITS = int.from_bytes(b'\x01' * BLOCK_BYTES, 'little')

def count_differences(before, after):
    if not isinstance(before, (bytes, bytearray)) or not isinstance(after, (bytes, bytearray)):
        raise TypeError('Difference counter requires bytes or bytearray')
    if len(before) != len(after):
        raise ValueError('Difference counter requires equal lengths')
    total = 0
    for start in range(0, len(before), BLOCK_BYTES):
        a = before[start:start + BLOCK_BYTES]
        b = after[start:start + BLOCK_BYTES]
        if a != b:
            # Collapse the eight bits of each XOR byte into its low bit.
            # Big-int operations run in native code; masking prevents cross-byte counts.
            bits = int.from_bytes(a, 'little') ^ int.from_bytes(b, 'little')
            bits |= bits >> 4
            bits |= bits >> 2
            bits |= bits >> 1
            total += (bits & BYTE_LOW_BITS).bit_count()
    return total
