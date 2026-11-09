"""Small data-independent checks; model-transfer evidence is separate."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from color_math import lab
from color_delta import delta_e_2000
from evaluation import protects


class TrainingMath(unittest.TestCase):
    def test_ciede2000_published_reference(self):
        self.assertAlmostEqual(float(delta_e_2000([50,2.6772,-79.7751],[50,0,-82.7485])),2.0425,places=4)

    def test_srgb_black_white_and_gray(self):
        values=lab(np.array([[0,0,0],[.18,.18,.18],[1,1,1]]))
        self.assertAlmostEqual(values[0,0],0,places=8)
        self.assertAlmostEqual(values[-1,0],100,places=4)
        self.assertTrue(np.all(np.diff(values[:,0])>0))
        self.assertLess(abs(values[:,1:]).max(),1e-3)

    def test_average_improvement_cannot_hide_one_bad_color(self):
        self.assertFalse(protects([.1,2.01],[1,2]))

    def test_epsilon_stays_outside_the_original_floor(self):
        reference=np.array([1.])
        self.assertTrue(protects(reference+.00009,reference))
        self.assertFalse(protects(reference+.00018,reference))

    def test_zero_grid_is_zero_response(self):
        import torch
        from response_network import Response
        model=Response(dict(degree=1,coordinate_weights=np.zeros((4,3)).tolist(),
                            gains_native_to_RGB=np.eye(3).tolist()))
        values=torch.tensor([[[0.,0.,0.],[20.,70.,110.],[255.,255.,255.]]])
        result,_,_=model(values,torch.zeros((1,3,5,9,9)))
        self.assertTrue(torch.equal(result,values))

    def test_signed_integer_budget_with_a_shared_color_limit(self):
        from integer_search import solve
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            delta,meta=solve(np.empty((0,4)),np.array([[1.,0.,1.,0.]]),np.array([-2.,1.,-1.,1.]),
                             np.empty(0),np.array([1.]),np.ones(4),np.ones(4),np.ones(2),2,seconds=5)
        self.assertEqual(delta.tolist(),[1,0])
        self.assertLessEqual(meta['maximum_linear_excess'],1e-8)


if __name__=='__main__':unittest.main()
