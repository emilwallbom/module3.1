"""Measure one controller after checkpoint reload without modifying recordings."""
import os
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_NUM_THREADS"]="1"
import argparse
import json
from pathlib import Path
import numpy as np
from racing.session import Run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--steps",type=int,default=500)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    identity=Run().identity
    folder=root/"recordings/racing-v3/validated/robust-lmpc"/identity[:12]/"seed-0"
    run=Run(directory=folder);run.load()
    run.repository=None  # Checkpoint and trajectories remain unchanged.
    initial=run.learning_laps
    run.solve_times=[];run.solver_events=[]
    for _ in range(args.steps):
        run.step()
        if run.paused:break
    times=np.array(run.solve_times)
    report={"identity":identity,"source_checkpoint":str(folder),"requested_steps":args.steps,
            "measured_solves":len(times),"initial_learning_laps":initial,"final_learning_laps":run.learning_laps,
            "solver_p50_ms":float(np.median(times)),"solver_p95_ms":float(np.percentile(times,95)),
            "solver_max_ms":float(times.max()),"over_100ms":int((times>100).sum()),
            "failure":run.failure,"checkpoint_modified":False}
    (root/"artifacts/controller-performance.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if not run.failure and len(times)==args.steps else 1)


if __name__=="__main__":main()
