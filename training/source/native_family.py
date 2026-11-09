"""116 native directions: twelve frozen-reference Gamma bumps,96 matrix terms,eight CC1 bases."""
import copy
import support as w
import numpy as np

AXES=tuple(['G'+str(i+1)for i in range(12)]+['M'+str(i+1)for i in range(96)]+['CB'+str(i+1)for i in range(8)])
DIMENSION=len(AXES)


def candidate(base,weights):
    d=np.asarray(weights,float)
    if d.shape!=(116,)or not np.isfinite(d).all():raise ValueError('Expected116 finite native coordinates')
    value=copy.deepcopy(base)
    for branch in('photo','live'):
        p=value['parameters'][branch];original=base['parameters'][branch]
        m=np.asarray(original['matrices']['values'],int)
        p['matrices']['values']=(m+np.rint(d[12:108].reshape(16,6)*24).astype(int)[None]).tolist()
        coefficients=np.asarray(original['coefficients']['values'],int)
        coefficients[0]+=np.rint(d[108:]*8).astype(int);p['coefficients']['values']=coefficients.tolist()
        for index,raw in enumerate(original['gamma']['records']):
            gamma=w.native.decode_gamma(bytes(raw));y=np.asarray(gamma['y'],float)
            # Frozen original-y coordinates cover the rising range, rather than
            # wasting most controls on the large saturated high-x plateau.
            u=(y-y[0])/(y[-1]-y[0]);centers=np.linspace(1/13,12/13,12)
            bumps=np.maximum(0,1-((u[None]-centers[:,None])/(2/13))**2)**2
            bumps*=4*u[None]*(1-u[None])
            warped=np.rint(y+(y[-1]-y[0])*.015*(d[:12]@bumps)).astype(int)
            if np.any(np.diff(warped)<0):raise ValueError('Gamma is not monotone; reduce local trust radius')
            gamma['y']=warped.tolist();p['gamma']['records'][index]=list(w.native.encode_gamma(gamma))
    return w.host.verify_raw(w.fmt.encode(w.fmt.seal(value)))[0]


def safe(base,at,proposal):
    point=np.asarray(proposal,float).copy()
    for _ in range(18):
        point[12:108]=np.rint(point[12:108]*24)/24
        point[108:]=np.rint(point[108:]*8)/8
        try:return point,candidate(base,point)
        except ValueError:point=(np.asarray(at)+point)/2
    raise ValueError('No valid monotone native point in the requested step')
