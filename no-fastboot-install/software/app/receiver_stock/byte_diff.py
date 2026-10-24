from product_integrity import pinned, state_path
BLOCK_BYTES = 64 * 1024

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
            total += sum((x != y for x, y in zip(a, b)))
    return total
