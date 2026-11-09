import numpy as np

def design(rgb,degree):
    x=np.asarray(rgb,float)/127.5-1
    columns=[np.ones(len(x)),*x.T]
    if degree==2:columns += [x[:,i]*x[:,j]for i in range(3)for j in range(i,3)]
    return np.stack(columns,axis=1)
