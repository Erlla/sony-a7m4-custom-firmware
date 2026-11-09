import torch
import grid_base as gf
import host_grid

def torch_correction(model,rgb):
    import torch
    if model is None:return torch.zeros_like(rgb)
    if 'components'in model:
        return sum((torch_correction(component,rgb)for component in model['components']),torch.zeros_like(rgb))
    tensor=lambda value:torch.as_tensor(value,dtype=rgb.dtype,device=rgb.device)
    distance=(rgb[:,None]/255-tensor(model['centers'])[None]).square().sum(2)
    value=torch.exp(-distance/(2*model['width']**2))@tensor(model['weights'])
    limit=model.get('limit_RGB')
    return value if limit is None else limit*torch.tanh(value/limit)


def torch_transform(rgb, grid, grid_model, calibration=None, anchor_grid=None):
    """Differentiable mirror used by optimization; RGB is in 0..255 codes.

    Continuous grid proposals are allowed here. Final render/export consumes
    the integer native JSON and must be evaluated again after quantization.
    """
    import torch
    tensor=lambda value:torch.as_tensor(value,dtype=rgb.dtype,device=rgb.device)
    x=(rgb+torch_correction(calibration,rgb)).clamp(0,255)
    base=grid_model.get('base',grid_model);design=x/127.5-1
    columns=[torch.ones_like(x[:,0]),*design.unbind(1)]
    outputs=[]
    for channel in base['channels']:
        features=columns[:]
        if channel['degree']==2:
            features += [design[:,i]*design[:,j] for i in range(3) for j in range(i,3)]
        outputs.append(torch.stack(features,1)@tensor(channel['weights']))
    jac=torch.stack([value[:,:3]for value in outputs],2)
    coords=torch.stack([value[:,3]for value in outputs],1)
    grid=tensor(grid)
    anchor=torch.zeros_like(grid) if anchor_grid is None else tensor(anchor_grid)
    amplitude=host_grid.sample_torch(grid,coords)-host_grid.sample_torch(anchor,coords)
    shift=torch.einsum('nij,nj->ni',jac,amplitude)
    if grid_model.get('schema')=='m4-full-pixel-grid/1':
        features=columns[:]
        if grid_model['degree']==2:
            features += [design[:,i]*design[:,j] for i in range(3) for j in range(i,3)]
        feature=(torch.stack(features,1)[:,:,None]*(amplitude/8)[:,None,:]).reshape(len(x),-1)
        shift=shift+feature@tensor(grid_model['weights'])
    return (x+shift).clamp(0,255)
