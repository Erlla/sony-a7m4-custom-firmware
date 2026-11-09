import struct
import numpy as np
import support as w

def photo_payloads(value):
    """JSON -> observed selected RAW fields. No extra color conversion."""
    p = value['parameters']['photo']
    terms = np.asarray(p['matrices']['values'][0], dtype=np.int64)
    packed = np.zeros(96, dtype=np.int64)
    for group in range(16):
        for term in range(6):
            packed[term * 16 + (group ^ 1)] = terms[group, term] * 4
    if np.any(packed < -32768) or np.any(packed > 32767):
        raise ValueError('Matrix exceeds the observed signed RAW encoding')
    matrix9 = struct.pack('<9h', *w.native.expand_matrix(terms[0].tolist(), [1024] * 3))
    decoded_gamma = w.native.decode_gamma(bytes(p['gamma']['records'][6]))
    gamma = decoded_gamma['y']
    axis = w.native.gamma_x(decoded_gamma['divisions'])
    cc = {}
    for tag, vals in zip((0x7842, 0x7844, 0x7845), p['coefficients']['values']):
        cc[tag] = struct.pack('<8h', *[vals[k] * (1 if i < 4 else 2)
                                     for i, k in enumerate((3, 0, 1, 2, 7, 4, 5, 6))])
    return dict(matrix96=struct.pack('<96h', *packed.tolist()), matrix9=matrix9,
                gamma=struct.pack('<128i', *[2 * y for y in gamma[:127]], 2 * gamma[-1]),
                gamma_axis=struct.pack('<128i', *[32 * x for x in axis[:127]], 32 * axis[-1]), cc=cc)
