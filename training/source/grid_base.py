import numpy as np
import grid_math as gr

def components(model,rgb):
    outputs=[gr.design(rgb,ch['degree'])@np.asarray(ch['weights'])for ch in model['channels']]
    return np.stack([out[:,:3]for out in outputs],axis=2),np.stack([out[:,3]for out in outputs],axis=1)
