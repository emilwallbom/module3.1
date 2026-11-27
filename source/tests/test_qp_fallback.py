import numpy as np
from scipy import sparse
from racing.controller import conic_fallback


def test_fallback_solves_both_sided_constraints():
    # Unique optimum (0.25, 0.75); equality, upper/lower bounds and a free row.
    p=sparse.eye(2,format="csc")*2
    q=np.array([0.,-1.])
    a=sparse.csc_matrix([[1.,1.],[1.,0.],[0.,1.],[1.,-1.]])
    lower=np.array([1.,0.,0.,-np.inf]);upper=np.array([1.,1.,1.,np.inf])
    solution=conic_fallback(p,q,a,lower,upper,1)
    assert str(solution.status)=="Solved"
    np.testing.assert_allclose(solution.x,[.25,.75],atol=1e-5)
