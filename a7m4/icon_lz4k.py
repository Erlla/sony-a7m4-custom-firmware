"""Encode the block profile observed in the supplied Sony icon banks.

This implements the local resource format, not a hardware emulator. Each F0
block has its own dictionary and end marker; nonfinal output blocks are 4096 B.
"""
BLOCK_BYTES = 4096
LENGTHS = (*range(3, 17), 32, 64)


def encode_block(raw):
    if not 0 < len(raw) <= BLOCK_BYTES:
        raise ValueError('An icon block must contain 1..4096 output bytes')
    positions, tokens = {}, []
    at = 0
    while at < len(raw):
        best, distance = 0, 0
        limit = min(64, len(raw) - at)
        if limit >= 3:
            for previous in reversed(positions.get(raw[at:at + 3], [])[-256:]):
                delta = at - previous
                if delta >= 4096:
                    continue
                n = 3
                while n < limit and raw[previous + n] == raw[at + n]:
                    n += 1
                n = 64 if n >= 64 else 32 if n >= 32 else min(n, 16)
                if n > best:
                    best, distance = n, delta
                if best == 64:
                    break
        if best < 3:
            best = 1
            tokens.append(raw[at:at + 1])
        else:
            length_code = 15 if best == 64 else 14 if best == 32 else best - 3
            tokens.append(bytes([(length_code << 4) | (distance >> 8), distance & 255]))
        for previous in range(at, at + best):
            if previous + 3 <= len(raw):
                positions.setdefault(raw[previous:previous + 3], []).append(previous)
        at += best
    tokens.append(b'\0\0')
    encoded = bytearray([0xf0])
    for start in range(0, len(tokens), 8):
        group = tokens[start:start + 8]
        encoded.append(sum(1 << i for i, token in enumerate(group) if len(token) == 2))
        for token in group:
            encoded.extend(token)
    return bytes(encoded)


def encode(raw):
    raw = bytes(raw)
    if not raw:
        raise ValueError('An icon stream cannot be empty')
    return b''.join(encode_block(raw[p:p + BLOCK_BYTES]) for p in range(0, len(raw), BLOCK_BYTES))


def decode(encoded):
    """Decode with per-block bounds, and enforce the observed icon-bank profile.

    Also require each compressed block to fit 4096 B. All six original banks
    satisfy this narrower release constraint; it is not a claim about every
    stream the hardware can legally decode.
    """
    pos, output, blocks = 0, bytearray(), []
    while pos < len(encoded):
        start, base = pos, len(output)
        if encoded[pos] != 0xf0:
            raise ValueError('Expected an F0 compressed block')
        pos += 1
        ended = False
        while not ended:
            if pos >= len(encoded):
                raise ValueError('Missing block end marker')
            flags = encoded[pos]
            pos += 1
            for bit in range(8):
                if flags & (1 << bit):
                    if pos + 2 > len(encoded):
                        raise ValueError('Truncated reference')
                    a, b = encoded[pos:pos + 2]
                    pos += 2
                    distance = ((a & 15) << 8) | b
                    if not distance:
                        if a or b or flags >> (bit + 1):
                            raise ValueError('Unexpected end marker/pending flags')
                        ended = True
                        break
                    length = LENGTHS[a >> 4]
                    if distance > len(output) - base:
                        raise ValueError('Reference crosses a block boundary')
                    if len(output) - base + length > BLOCK_BYTES:
                        raise ValueError('Block output exceeds 4096 bytes')
                    for _ in range(length):
                        output.append(output[-distance])
                else:
                    if pos >= len(encoded):
                        raise ValueError('Truncated literal')
                    if len(output) - base >= BLOCK_BYTES:
                        raise ValueError('Block output exceeds 4096 bytes')
                    output.append(encoded[pos])
                    pos += 1
        count = len(output) - base
        if not count or (pos < len(encoded) and count != BLOCK_BYTES):
            raise ValueError('Unexpected nonfinal/empty block size')
        if pos - start > BLOCK_BYTES:
            raise ValueError('Compressed block exceeds observed release profile')
        blocks.append(dict(offset=start, input_bytes=pos - start, output_bytes=count))
    return bytes(output), blocks
