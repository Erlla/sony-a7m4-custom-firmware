import numpy as np

def sample_torch(grid, coordinates):
    import torch
    pos = coordinates.clamp(0, 1) * torch.tensor([4, 8, 8], dtype=coordinates.dtype, device=coordinates.device)
    limits = torch.tensor([3, 7, 7], device=coordinates.device)
    lo = torch.minimum(pos.floor().long(), limits); f = pos - lo
    result = torch.zeros_like(coordinates)
    for corner in np.ndindex(2, 2, 2):
        c = torch.tensor(corner, device=coordinates.device)
        index = lo + c
        weight = torch.where(c.bool(), f, 1-f).prod(dim=1)
        result = result + weight[:, None] * grid[:, index[:, 0], index[:, 1], index[:, 2]].T
    return result
