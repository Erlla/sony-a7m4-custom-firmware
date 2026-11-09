"""Exact paired-colour scoring, neutral/shadow diagnostics and RGB histograms."""
import numpy as np
from color_math import lab
from color_delta import delta_e_2000


def metrics(prediction16, target, kinds=None):
    rgb=np.asarray(prediction16,dtype=float)/65535
    target=np.asarray(target,dtype=float)
    if rgb.shape!=target.shape:
        raise ValueError('Prediction and target sampling do not match')
    pl,tl=lab(rgb),lab(target)
    de=delta_e_2000(pl,tl)
    def score(mask):
        x=de[mask]
        if not len(x):return None
        return dict(count=len(x),mean=float(x.mean()),p95=float(np.percentile(x,95)),maximum=float(x.max()),
                    RGB_RMSE_255=float(np.sqrt(np.mean(((rgb[mask]-target[mask])*255)**2))))
    result=dict(all=score(np.ones(len(de),bool)),
                shadow=score((tl[:,0]>=5)&(tl[:,0]<=35)),
                rgb_histogram=dict(bins=256,prediction=[np.histogram(rgb[:,i],np.linspace(0,1,257))[0].tolist()for i in range(3)],
                                   target=[np.histogram(target[:,i],np.linspace(0,1,257))[0].tolist()for i in range(3)]),
                error_unit='CIEDE2000, sRGB D65 Lab; RGB RMSE in 0..255',
                physical_camera_test=False)
    if kinds is not None:
        result['categories']={str(k):score(kinds==k) for k in np.unique(kinds)}
        gray=kinds=='gray'
        result['neutral'] = dict(predicted_Lab=pl[gray].tolist(),target_Lab=tl[gray].tolist(),
                                target_L5_to35=score(gray&(tl[:,0]>=5)&(tl[:,0]<=35)))
        from colorsys import rgb_to_hsv
        ph=np.asarray([rgb_to_hsv(*v)for v in rgb]);th=np.asarray([rgb_to_hsv(*v)for v in target])
        stable=(np.hypot(pl[:,1],pl[:,2])>=5)&(np.hypot(tl[:,1],tl[:,2])>=5)&(ph[:,1]>=.1)&(th[:,1]>=.1)&(pl[:,0]>=5)&(tl[:,0]>=5)
        angle=(ph[:,0]-th[:,0])*360
        angle=(angle+180)%360-180
        result['hue']=dict(valid_count=int(stable.sum()),mean_absolute_degrees=float(np.abs(angle[stable]).mean())if stable.any()else None,
                           signed_degrees=angle.tolist(),valid=stable.tolist(),
                           meaning='Predicted hue minus paired target hue; low-chroma/black points masked explicitly')
    return result,de


def protects(candidate, baseline, epsilon=1e-4):
    """One fixed colour floor; tolerance does not accumulate across search steps."""
    candidate,baseline=map(np.asarray,(candidate,baseline))
    return bool(np.all(candidate<=baseline+epsilon))
