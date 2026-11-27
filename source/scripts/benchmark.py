"""Run independent seeded benchmarks in worker processes (no rendering)."""
import os
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_NUM_THREADS"]="1"
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json
import argparse
from racing.train import train
from racing import spec
from racing.session import Run


def job(arguments):
    seed,laps,directory,terminal_mode=arguments
    return train("l_track",seed,laps,Path(directory)/f"seed-{seed}",terminal_mode=terminal_mode)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",nargs="+",type=int,default=[0,1,2,3,4])
    parser.add_argument("--laps",type=int,default=40)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--output")
    parser.add_argument("--terminal-mode",choices=spec.PROFILES,default=spec.DEFAULT_PROFILE)
    args=parser.parse_args()
    identity=Run(terminal_mode=args.terminal_mode).identity
    args.output=args.output or f"recordings/racing-v3/validated/{args.terminal_mode}/{identity[:12]}"
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        reports=list(pool.map(job,[(seed,args.laps,args.output,args.terminal_mode) for seed in args.seeds]))
    Path(args.output).mkdir(parents=True,exist_ok=True)
    (Path(args.output)/"benchmark.json").write_text(json.dumps(reports,indent=2),encoding="utf-8")
    raise SystemExit(0 if all(r["passed"] for r in reports) else 1)


if __name__=="__main__":main()
