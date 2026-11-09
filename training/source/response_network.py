import torch
from torch import nn
import torch.nn.functional as F

class Response(nn.Module):
    def __init__(self,seed_model,width=64):
        super().__init__()
        self.degree=seed_model['degree'];self.width=width
        self.register_buffer('coordinates',torch.tensor(seed_model['coordinate_weights'],dtype=torch.float32))
        self.gains=nn.Parameter(torch.tensor(seed_model['gains_native_to_RGB'],dtype=torch.float32))
        self.coord=nn.Sequential(nn.Linear(3,width),nn.Tanh(),nn.Linear(width,width),nn.Tanh(),nn.Linear(width,3))
        self.field=nn.Sequential(nn.Linear(12,width),nn.Tanh(),nn.Linear(width,width),nn.Tanh(),nn.Linear(width,9))
        for module in (self.coord[-1],self.field[-1]):nn.init.zeros_(module.weight);nn.init.zeros_(module.bias)

    def forward(self,x,grid,training_clip=False):
        z=x/127.5-1
        features=[torch.ones_like(z[...,:1]),z]
        if self.degree==2:features.extend([z[...,i:i+1]*z[...,j:j+1]for i in range(3)for j in range(i,3)])
        base=torch.cat(features,-1)@self.coordinates
        coord_delta=.25*torch.tanh(self.coord(z));u=torch.clamp(base+coord_delta,0,1)
        # Native memory uses axis0=depth5, axis1=height9, axis2=width9.
        sample=(u[...,list((2,1,0))]*2-1)[:,None,None,:,:]
        g=F.grid_sample(grid,sample,mode='bilinear',padding_mode='border',align_corners=True)[:,:,0,0,:].transpose(1,2)
        gn=g/64
        difference=torch.stack([z[...,0]-z[...,1],z[...,2]-z[...,1],z[...,0]-z[...,2]],-1)
        inp=torch.cat([z,gn,difference,difference.abs()],-1)
        fields=64*torch.tanh(self.field(inp)).reshape(*g.shape[:2],3,3)
        shift=g@self.gains+torch.einsum('npi,npij->npj',gn,fields)
        latent=x+shift;clipped=torch.clamp(latent,0,255)
        # Exact observed clipping in the forward pass. A straight-through
        # surrogate allows a wrong clipped prediction to leave the flat zone.
        predicted=latent+(clipped-latent).detach()if training_clip else clipped
        return predicted,coord_delta,fields
