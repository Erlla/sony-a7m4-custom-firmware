import struct
import numpy as np
import support as w
import cc1_effective as cc1

def fixed_context(fields,white_balance_mode='fixed'):
    try:return cc1.validate_fixed_context(fields,white_balance_mode=white_balance_mode)
    except ValueError:
        if white_balance_mode!='fixed':raise
        # At3200K this batch selects the base:7843 has weight1024 but its row0.
        if fields['weights_7848']!=[1024,0,0,0] or fields['deltas'][0]!=[0]*8 or fields['deltas'][3]!=[0]*8:raise
        actual=fields['effective'];predicted=cc1.interpolate_folded_raw_fields(fields['base'],fields['deltas'],fields['weights_7848'])
        if predicted!=actual:raise ValueError('Base-only fixed-WB arithmetic did not match measured effective field')
        return cc1.FixedContext(tuple(fields['weights_7848']),
                               (tuple(fields['deltas'][0]),tuple(fields['deltas'][3])),tuple(actual))


def nearest(value,denominator=1024):
    value=np.asarray(value,dtype=np.int64)
    return np.where(value>=0,(value+denominator//2)//denominator,-((-value+denominator//2)//denominator))


def matrix_payloads(native,context):
    if not isinstance(context,cc1.FixedContext):raise TypeError('A checked fixed context is required')
    family=np.asarray(native['parameters']['photo']['matrices']['values'],dtype=np.int64)
    same=np.array_equal(family[0],family[1]) and np.array_equal(family[0],family[2])
    if not same and (context.weights!=(0,1348,0,0) or not np.array_equal(family[1],family[2])):
        raise ValueError('Unequal endpoint mapping has only been measured at weights(0,1348,0,0) with A1=A2')
    matrices=np.asarray([[w.native.expand_matrix(group.tolist(),[1024]*3) for group in endpoint] for endpoint in family],dtype=np.int64)
    mixed=matrices[0] if same else matrices[0]+nearest((matrices[1]-matrices[0])*1348)
    if abs(mixed).max()>32767:raise ValueError('Effective matrix exceeds signed16 range')
    # Round all9 matrix entries before packing the6 off-diagonal terms. Mixed
    # row sums can differ by1: expanding rounded6 terms is not equivalent.
    terms=-mixed[:,[1,2,3,5,6,7]];packed=np.zeros(96,dtype=np.int64)
    for group in range(16):
        for term in range(6):packed[term*16+(group^1)]=4*terms[group,term]
    if abs(packed).max()>32767:raise ValueError('Effective RAW matrix96 exceeds signed16 range')
    return dict(matrix96=struct.pack('<96h',*packed.tolist()),matrix9=struct.pack('<9h',*mixed[0].tolist()),
                mapping='identical-endpoints' if same else 'B+round((A1-B)*1348/1024), A1=A2, verified fixed context')
