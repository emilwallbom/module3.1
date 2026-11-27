"""Read-only portable runtime and real-controller check. No downloads or installs."""
import os
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_NUM_THREADS"]="1"
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import ctypes
import numpy as np
import scipy.linalg
import osqp
import clarabel
from racing.session import Run


def main():
    root=Path(__file__).resolve().parents[1]
    assert Path(sys.executable).resolve().is_relative_to(root),"Python is outside this package"
    assert all(Path(p).resolve().is_relative_to(root) for p in sys.path),"Import path escapes the package"
    manifest=json.loads((root/"portable-manifest.json").read_text())
    for name,version in manifest["dependencies"].items():assert metadata.version(name)==version,(name,version)
    # Import and exercise compiled scientific components, not just package metadata.
    assert np.allclose(scipy.linalg.solve(np.eye(3),np.ones(3)),np.ones(3))
    import scipy.sparse as sparse
    solver=osqp.OSQP();solver.setup(P=sparse.csc_matrix([[2.]]),q=np.array([-2.]),A=sparse.eye(1,format="csc"),l=np.array([0.]),u=np.array([2.]),verbose=False)
    assert abs(solver.solve().x[0]-1)<.001
    settings=clarabel.DefaultSettings();settings.verbose=False
    answer=clarabel.DefaultSolver(sparse.csc_matrix([[2.]]),np.array([-2.]),sparse.csc_matrix([[-1.]]),np.array([0.]),[clarabel.NonnegativeConeT(1)],settings).solve()
    assert abs(answer.x[0]-1)<.001
    identity=Run().identity;assert identity==manifest["controller_identity"]
    folder=root/"recordings/racing-v3/validated/robust-lmpc"/identity[:12]/"seed-0"
    checkpoint=folder/"checkpoint.json";before=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    run=Run(directory=folder);run.load();run.repository=None
    run.paused=False;run.solve_times=[]
    for _ in range(50):
        run.step()
        assert not run.failure,run.failure
    assert len(run.solve_times)==50
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==before
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p];kernel.GetModuleHandleW.restype=ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint]
    crt={}
    for name in ("vcruntime140.dll","vcruntime140_1.dll","msvcp140.dll"):
        handle=kernel.GetModuleHandleW(name)
        if handle:
            buffer=ctypes.create_unicode_buffer(32768);kernel.GetModuleFileNameW(handle,buffer,len(buffer))
            assert Path(buffer.value).resolve().is_relative_to(root),f"Runtime loaded outside package: {buffer.value}"
            crt[name]=buffer.value
    result={"portable_check":"passed","root":str(root),"python":sys.executable,"paths":sys.path,
        "identity":identity,"real_mpc_solves":len(run.solve_times),"checkpoint_modified":False,
        "solver_p95_ms":float(np.percentile(run.solve_times,95)),"versions":manifest["dependencies"],"app_local_crt":crt}
    print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__":main()
