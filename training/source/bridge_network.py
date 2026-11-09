import numpy as np
import grid_math as gr

def components(model, rgb, member=None):
    rgb = np.asarray(rgb, float)
    outputs = []
    for ch in model['channels']:
        base = gr.design(rgb, 2) @ np.asarray(ch['prior']['weights'])
        z = (rgb-ch['xmean'])/ch['xscale']
        members = []
        for state in ch['states']:
            t = z
            for layer in (0, 2, 4):
                t = t @ np.asarray(state[f'{layer}.weight']).T + state[f'{layer}.bias']
                if layer != 4:
                    t = np.tanh(t)
            members.append(base + t * ch['yscale'])
        outputs.append(np.mean(members, axis=0) if member is None else members[member])
    return np.stack([out[:,:3] for out in outputs], axis=2), np.stack([out[:,3] for out in outputs], axis=1)
