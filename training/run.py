"""Small Agent entry points; no camera control, GUI or automatic publication."""
from pathlib import Path
import argparse
import json
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['doctor','render-chart','render','fit-chart'])
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--sony-edit',type=Path,help='Locally supplied supported Edit Mach-O universal binary')
    parser.add_argument('--srsettings',type=Path,help='Locally supplied srsettings0000.tbl')
    parser.add_argument('--device',default='auto',choices=['auto','cpu','cuda'])
    parser.add_argument('--native',type=Path,help='Validated camera-look v2 seed/candidate JSON')
    parser.add_argument('--raw',type=Path)
    parser.add_argument('--film',default='CC')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--steps',type=int,default=1800)
    parser.add_argument('--trust',type=int,default=16)
    parser.add_argument('--name',default='My look')
    parser.add_argument('--roi',type=int,nargs=4,metavar=('X','Y','W','H'))
    args=parser.parse_args()
    import numpy as np
    import torch
    if args.device=='auto':args.device='cuda'if torch.cuda.is_available()else'cpu'
    import support as w
    from camera_model import CameraModel
    model=CameraModel(args.assets,args.sony_edit,args.srsettings,args.device)
    if args.action=='doctor':
        print(json.dumps(dict(ready=True,identity=model.identity,assets=str(model.assets),
                              device=args.device,camera_access=False),ensure_ascii=False,indent=2))
        return
    if args.native is None or args.output is None:
        parser.error('Supply --native and a new --output directory')
    out=args.output.resolve()
    if out.exists():
        parser.error('Choose a new output directory; previous results are retained')
    out.mkdir(parents=True)
    native=w.fmt.parse(args.native.read_bytes());model.check_defaults(native)
    started=time.monotonic()
    if args.action in ('render-chart','fit-chart'):
        from evaluation import metrics
        dataset=w.read(model.assets/'charts/dataset.json')
        with np.load(model.assets/'charts/fuji_targets.npz',allow_pickle=False)as z:
            if args.film not in z:parser.error('Film not in target dataset: '+args.film)
            target=z[args.film].copy()
        native16=model.chart_native(native)
        if args.action=='fit-chart':
            from fit_grid import fit
            result=fit(model,native,native16,target,out,name=args.name,steps=args.steps,trust=args.trust)
        else:
            prediction=model.sample(native16,model.bake(native))
            with np.load(model.assets/'charts/sony_input.npz',allow_pickle=False)as z:kinds=z['kind'].copy()
            result,de=metrics(prediction,target,kinds)
            np.savez_compressed(out/'samples.npz',prediction=prediction,target=target,deltaE00=de,kinds=kinds)
            w.save(out/'metrics.json',result)
        result.update(native=w.pin(args.native),model=w.pin(model.path),dataset_id=dataset['dataset_id'],
                      seconds_total=time.monotonic()-started,physical_camera_test=False)
        w.save(out/'receipt.json',result)
    else:
        if args.raw is None:parser.error('Supply --raw')
        import native_frontend as E
        result=E.decode(args.raw,native,out/'native.tif',dict(identity=model.identity),roi=args.roi)
        import tifffile
        image=tifffile.memmap(out/'native.tif')
        table=model.bake(native)
        from PIL import ImageCms
        icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        target=tifffile.memmap(out/'render.tif',shape=image.shape,dtype='<u2',photometric='rgb',metadata=None,
                              extratags=[(34675,'B',len(icc),icc,False)])
        for y in range(0,len(image),128):
            block=image[y:y+128]
            target[y:y+128]=model.sample(block.reshape(-1,3),table).reshape(block.shape)
        target.flush()
        result.update(raw=w.pin(args.raw),native=w.pin(args.native),model=w.pin(model.path),
                      seconds_total=time.monotonic()-started,output=w.pin(out/'render.tif'))
        w.save(out/'receipt.json',result)
    print(json.dumps(dict(output=str(out),action=args.action,seconds=round(time.monotonic()-started,3),
                          physical_camera_test=False),ensure_ascii=False))


if __name__=='__main__':main()
