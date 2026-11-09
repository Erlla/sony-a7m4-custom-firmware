"""Resident zero-grid bridge cache for repeated exact129-cubed evaluation.

Native parameter changes still require fresh native RGB. This cache is the
post-native RGB-domain bridge, tied to one frozen camera model.
"""
import numpy as np
import torch
import pixel_bridge


class FrozenTable:
    def __init__(self,model):
        self.model=model
        self.device=model.device
        axis=np.linspace(0,255,129)
        points=np.stack(np.meshgrid(axis,axis,axis,indexing='ij'),-1).reshape(-1,3)
        zero=[]
        with torch.no_grad():
            for lo in range(0,len(points),32768):
                rgb=torch.as_tensor(points[lo:lo+32768],device=self.device,dtype=torch.float64)
                bridge=pixel_bridge.torch_transform(rgb,torch.zeros((3,5,9,9),device=self.device,dtype=torch.float64),
                    model.grid_model,model.calibration,model.anchor_grid)
                zero.append(bridge.float())
        self.zero=torch.cat(zero)
        self.table=torch.empty((len(points),3),device=self.device,dtype=torch.float64)

    @torch.no_grad()
    def __call__(self,grid):
        """Returns a reused buffer; copy it if an older table must be retained."""
        g=torch.as_tensor(grid,device=self.device,dtype=torch.float32).reshape(1,3,5,9,9)
        for lo in range(0,len(self.zero),32768):
            value=self.model.response(self.zero[lo:lo+32768][None],g)[0][0]
            self.table[lo:lo+len(value)]=value.double()
        return self.table.reshape(129,129,129,3)
