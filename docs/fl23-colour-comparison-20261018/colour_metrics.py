"""Probability histograms and vectorized CIEDE2000; no exposure/WB compensation."""
import numpy as np

def histogram_metrics(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    assert a.shape==b.shape and a.ndim==1 and a.sum()>0 and b.sum()>0
    p,q=a/a.sum(),b/b.sum();m=(p+q)/2
    kl=lambda x:float(np.sum(x[x>0]*np.log2(x[x>0]/m[x>0])))
    return dict(overlap_pct=float(np.minimum(p,q).sum()*100),
        total_variation_pct=float(np.abs(p-q).sum()*50),
        BC_pct=float(np.sqrt(p*q).sum()*100),JS_bits=(kl(p)+kl(q))/2,
        W1_code_values=float(np.abs(np.cumsum(p)-np.cumsum(q)).sum()),
        mean_camera=float(p@np.arange(len(p))),mean_edit=float(q@np.arange(len(q))))

def lab_d65(rgb):
    x=np.asarray(rgb,dtype=np.float64)/255
    x=np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
    xyz=x@np.array([[.4124564,.3575761,.1804375],
                    [.2126729,.7151522,.0721750],
                    [.0193339,.1191920,.9503041]]).T
    xyz/=np.array([.95047,1.,1.08883]);d=6/29
    f=np.where(xyz>d**3,np.cbrt(xyz),xyz/(3*d*d)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)

def delta_e00(first,second):
    """CIEDE2000 kL=kC=kH=1; tested against Sharma/Wu/Dalal34 reference pairs."""
    l1,a1,b1=np.moveaxis(np.asarray(first,dtype=float),-1,0)
    l2,a2,b2=np.moveaxis(np.asarray(second,dtype=float),-1,0)
    c1=np.hypot(a1,b1);c2=np.hypot(a2,b2);cb=(c1+c2)/2
    g=.5*(1-np.sqrt(cb**7/(cb**7+25.**7)))
    ap1=(1+g)*a1;ap2=(1+g)*a2
    cp1=np.hypot(ap1,b1);cp2=np.hypot(ap2,b2)
    hp1=np.degrees(np.arctan2(b1,ap1))%360
    hp2=np.degrees(np.arctan2(b2,ap2))%360
    dl=l2-l1;dc=cp2-cp1;rawdh=hp2-hp1;zero=cp1*cp2==0
    dh=np.where(zero,0,np.where(rawdh>180,rawdh-360,np.where(rawdh<-180,rawdh+360,rawdh)))
    dH=2*np.sqrt(cp1*cp2)*np.sin(np.radians(dh)/2)
    lb=(l1+l2)/2;cpb=(cp1+cp2)/2
    hb=np.where(zero,hp1+hp2,np.where(np.abs(rawdh)<=180,(hp1+hp2)/2,
        np.where(hp1+hp2<360,(hp1+hp2+360)/2,(hp1+hp2-360)/2)))
    t=1-.17*np.cos(np.radians(hb-30))+.24*np.cos(np.radians(2*hb))+.32*np.cos(np.radians(3*hb+6))-.20*np.cos(np.radians(4*hb-63))
    sl=1+.015*(lb-50)**2/np.sqrt(20+(lb-50)**2);sc=1+.045*cpb;sh=1+.015*cpb*t
    rt=-2*np.sqrt(cpb**7/(cpb**7+25.**7))*np.sin(np.radians(60*np.exp(-((hb-275)/25)**2)))
    x,y,z=dl/sl,dc/sc,dH/sh
    return np.sqrt(np.maximum(0,x*x+y*y+z*z+rt*y*z))

def describe_delta(cam_lab,edit_lab,mask=None):
    a=cam_lab if mask is None else cam_lab[mask]
    b=edit_lab if mask is None else edit_lab[mask]
    a=a.reshape(-1,3);b=b.reshape(-1,3)
    assert len(a)>0
    d=delta_e00(a,b)
    mean_a=a.mean(axis=0);mean_b=b.mean(axis=0)
    return dict(pixels=len(a),deltaE00_mean=float(d.mean()),deltaE00_median=float(np.median(d)),
        deltaE00_p95=float(np.percentile(d,95)),deltaE00_lt1_pct=float(np.mean(d<1)*100),
        deltaE00_lt2_pct=float(np.mean(d<2)*100),
        mean_Lab_camera=mean_a.tolist(),mean_Lab_edit=mean_b.tolist(),
        edit_minus_camera_Lab=(mean_b-mean_a).tolist(),
        deltaE00_of_mean_Lab=float(delta_e00(mean_a,mean_b)))

def edge_shift(camera,edit,radius=3):
    """Integer translation diagnostic only; do not warp or correct measured images."""
    def edges(a):
        y=np.asarray(a,dtype=float)@np.array([.2126,.7152,.0722])
        return np.hypot(y[1:-1,2:]-y[1:-1,:-2],y[2:,1:-1]-y[:-2,1:-1])
    a,b=edges(camera),edges(edit);margin=radius+4
    fixed=a[margin:-margin,margin:-margin];fixed=fixed-fixed.mean();den=np.linalg.norm(fixed)
    scores=[]
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            candidate=b[margin+dy:b.shape[0]-margin+dy,margin+dx:b.shape[1]-margin+dx]
            candidate=candidate-candidate.mean()
            score=float(np.sum(fixed*candidate)/(den*np.linalg.norm(candidate)))
            scores.append(dict(dx=dx,dy=dy,edge_NCC=score))
    best=max(scores,key=lambda r:r['edge_NCC']);zero=next(r for r in scores if r['dx']==r['dy']==0)
    return dict(size=[camera.shape[1],camera.shape[0]],radius=radius,best=best,zero=zero,
        correction_applied=False,scope='Finite integer translations; no subpixel/lens-distortion equivalence claim')
