"""Agent-callable grid proposal and exact integer verification.

This is a reusable fitting primitive, not a new camera-model training routine.
For a new look the Agent assigns data roles/guards before calling it.
"""
import copy
import time
import uuid
import numpy as np
import torch
import support as w
import torch_color
from evaluation import metrics, chart_qualification


def differentiable_lab(rgb):
    value=torch_color.lab(rgb)
    tiny=(value[:,1:].square().sum(1)<1e-20).to(value.dtype)*1e-10
    return torch.stack((value[:,0],value[:,1]+tiny,value[:,2]),dim=1)


def interpolated_proposal(model, native16, grid, chunk=32768):
    """Differentiable node subset; proposals must pass formal full-table replay."""
    pos=np.asarray(native16,dtype=float).reshape(-1,3)*(128/65535)
    low=np.minimum(pos.astype(int),127);fraction=pos-low
    indices=[];weights=[]
    for corner in np.ndindex(2,2,2):
        c=np.asarray(corner);at=low+c
        indices.append(at[:,0]*129**2+at[:,1]*129+at[:,2])
        weights.append(np.prod(np.where(c,fraction,1-fraction),axis=1))
    unique,inverse=np.unique(np.stack(indices),return_inverse=True)
    coords=np.column_stack((unique//129**2,unique//129%129,unique%129))*(255/128)
    values=torch.cat([model.forward(coords[i:i+chunk],grid)for i in range(0,len(coords),chunk)]).to(torch.float64)
    at=torch.as_tensor(inverse.reshape(8,-1),device=model.device)
    weight=torch.as_tensor(np.stack(weights),device=model.device,dtype=torch.float64)
    return (values[at]*weight[:,:,None]).sum(0)


def propose(model, seed, native16, target, *, steps=1800, trust=16, sample_limit=8192, random_seed=1701):
    """Adam/STE grid proposal with target-colour shadow and continuity penalties."""
    torch.manual_seed(random_seed)
    target=np.asarray(target,dtype=float)
    rng=np.random.default_rng(random_seed)
    ids=np.sort(rng.choice(len(target),min(sample_limit,len(target)),replace=False))
    values=torch.tensor(np.asarray(seed['parameters']['grid']['photo']).reshape(3,5,9,9),
                        device=model.device,dtype=torch.float32,requires_grad=True)
    origin=values.detach().clone();optimizer=torch.optim.Adam([values],lr=.15)
    tl=differentiable_lab(torch.tensor(target[ids]*255,device=model.device,dtype=torch.float64))
    dark=(tl[:,0]>=5)&(tl[:,0]<=35)
    history=[]
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True)
        g=values+(values.round()-values).detach() if step>=steps*2//3 else values
        rgb=interpolated_proposal(model,native16[ids],g)
        pl=differentiable_lab(rgb);de=torch_color.de00(pl,tl)
        chroma=(pl[:,1:]-tl[:,1:]).square().sum(1)
        tail=torch.topk(de,max(1,len(de)//20)).values
        loss=de.square().mean()+tail.square().mean()
        if dark.any():loss=loss+2*de[dark].square().mean()+.05*chroma[dark].mean()
        # Native-axis second differences; do not project onto an old narrow grid.
        smooth=sum((g.diff(n=2,dim=axis)).square().mean()for axis in (1,2,3))
        loss=loss+.0001*smooth+.001*((g-origin)/max(trust,1)).square().mean()
        loss.backward();optimizer.step()
        with torch.no_grad():values.copy_(torch.maximum(torch.minimum(values,origin+trust),origin-trust).clamp(-64,63))
        if step==0 or (step+1)%100==0 or step+1==steps:
            history.append(dict(step=step+1,loss=float(loss.detach()),mean_DE=float(de.detach().mean())))
    return values.detach().round().to(torch.int16).cpu().numpy(),history


def fit(model, seed, native16, target, output, *, name, steps=1800, trust=16, guard=True,
        qualification='per-colour', new_identity=False):
    """Export a candidate with formal chart scores and an explicit quality policy."""
    started=time.monotonic()
    baseline16=model.sample(native16,model.bake(seed))
    before,base_de=metrics(baseline16,target)
    grid,history=propose(model,seed,native16,target,steps=steps,trust=trust)
    candidate=copy.deepcopy(seed)
    candidate['name']=name
    if new_identity:
        candidate['id']=str(uuid.uuid4())
        candidate['revision']=1
        candidate['author']='M4 LUT training'
        candidate['description']='Custom chart fit. See the training receipt for evaluation.'
        candidate['provenance']=dict(seed_id=seed['id'],seed_revision=seed['revision'],
                                     seed_payload_sha256=seed['payload_sha256'],seed_author=seed['author'])
    for branch in ('photo','live'):candidate['parameters']['grid'][branch]=grid.reshape(3,5,9,9).tolist()
    candidate=w.fmt.seal(candidate)
    destination=output/'candidate.json'
    destination.write_bytes(w.fmt.encode(candidate))
    # Reload and compile the actual exported integer document before scoring it.
    candidate=w.fmt.parse(destination.read_bytes());w.fmt.compile_native(candidate)
    after16=model.sample(native16,model.bake(candidate))
    after,de=metrics(after16,target)
    quality=chart_qualification(de,base_de,qualification)
    if not guard:
        quality.update(chart_candidate_qualified=False,per_colour_guard=False)
    result=dict(candidate_accepted=False,**quality,
                before=before,after=after,history=history,seconds=time.monotonic()-started,
                grid_dimensions=1215,native_parameters_changed=False,camera_model_retrained=False,
                additional_scene_guards='Agent must add task-specific protected pairs before adopting a look',
                physical_camera_test=False,candidate=w.pin(destination))
    w.save(output/'fit.json',result)
    np.savez_compressed(output/'paired_outputs.npz',baseline=baseline16,candidate=after16,target=target,
                        baseline_deltaE=base_de,candidate_deltaE=de)
    return result
