"""Signed MILP with separate native trust radius and real photo/live capacity."""
import time
import numpy as np
from scipy import sparse
from scipy.optimize import milp, Bounds, LinearConstraint


def solve(metric, points, cost, metric_rhs, point_rhs, admissible, capacity, radii, budget, seconds=20):
    started = time.monotonic()
    radii = np.asarray(radii, dtype=float)
    n = len(radii)
    assert metric.shape[1] == points.shape[1] == len(cost) == 2 * n
    capacity = np.asarray(capacity, dtype=float).reshape(-1)
    assert capacity.shape == (2 * n,) and np.all(capacity >= 0)
    matrix = sparse.vstack([sparse.csr_matrix(metric), sparse.csr_matrix(points)], format='csr')
    matrix.eliminate_zeros()
    rhs = np.r_[metric_rhs, point_rhs]
    scale = np.asarray(abs(matrix).max(axis=1).toarray()).ravel()
    active = scale > 0
    assert np.all(rhs[~active] >= -1e-9)
    normalized = sparse.diags(1 / np.maximum(scale[active], 1e-7)) @ matrix[active]
    hi = np.minimum(np.repeat(radii, 2), capacity) * admissible
    costs = cost / max(float(abs(cost).max()), 1e-10) + 1e-6
    pair = sparse.csr_matrix((np.ones(2 * n), (np.repeat(np.arange(n), 2), np.arange(2 * n))), shape=(n, 2 * n))
    blocks = [normalized, pair, sparse.csr_matrix(np.ones((1, 2 * n)))]
    limits = [rhs[active] / np.maximum(scale[active], 1e-7), radii, np.array([budget])]
    if np.all(radii == 1):
        A = sparse.vstack(blocks, format='csc')
        c = costs
    else:
        plus = pair.copy(); plus.data[1::2] = 0; plus.eliminate_zeros()
        minus = pair.copy(); minus.data[::2] = 0; minus.eliminate_zeros()
        direction = sparse.diags(radii)
        blocks = [sparse.hstack([b, sparse.csr_matrix((b.shape[0], n))]) for b in blocks]
        blocks.extend([sparse.hstack([plus, -direction]), sparse.hstack([minus, direction])])
        limits.extend([np.zeros(n), radii])
        A = sparse.vstack(blocks, format='csc')
        c = np.r_[costs, np.zeros(n)]
        hi = np.r_[hi, np.ones(n)]
    result = milp(c, integrality=np.ones(len(c)), bounds=Bounds(np.zeros(len(c)), hi),
                  constraints=LinearConstraint(A, np.full(A.shape[0], -np.inf), np.concatenate(limits)),
                  options=dict(time_limit=seconds, mip_rel_gap=.005, node_limit=200000,
                               presolve=False, threads=1, parallel=False))
    meta = dict(status=int(result.status), message=result.message, seconds=time.monotonic() - started,
                L1_budget=budget, all_dense_color_rows=len(point_rhs), active_rows=int(active.sum()),
                nonzero_coefficients=int(matrix.nnz), variables=len(c), native_radius=1,
                scope='Dense and post-grid criteria only; all native spatial gates remain unknown')
    if result.x is None:
        return None, meta
    x = np.rint(result.x[:2 * n]).astype(int)
    assert np.all(x.reshape(-1, 2).prod(1) == 0)
    assert np.all(x <= np.minimum(np.repeat(radii, 2), capacity) * admissible)
    delta = (x * np.tile([1, -1], n)).reshape(-1, 2).sum(1)
    meta.update(nonzero_elements=int(np.count_nonzero(delta)), L1=int(abs(delta).sum()),
                predicted_objective_change=float(cost @ x), maximum_linear_excess=float((matrix @ x - rhs).max()),
                directional_counts=[[int(i), int(v)] for i, v in enumerate(x) if v])
    return delta, meta
