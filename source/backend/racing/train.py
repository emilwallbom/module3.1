import argparse
import json
import os
from pathlib import Path
import time
from .session import Run
from . import spec


def train(track, seed, laps, output, resume=False, terminal_mode=spec.DEFAULT_PROFILE):
    run = Run(track, seed, output, terminal_mode=terminal_mode)
    if resume:
        run.load()
    started = time.perf_counter()
    while run.learning_laps < laps and not run.paused:
        result = run.step()
        if result:
            print(json.dumps({**result.summary(), "seed": seed, "wall_seconds": round(time.perf_counter()-started, 2)}), flush=True)
    report = run.report()
    report["wall_seconds"] = time.perf_counter()-started
    report["passed"] = run.learning_laps >= laps and report["improved"] and report["failed_attempts"] == 0
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output)/"report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "laps"}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Train Rosolia-style local LMPC; every attempt is recorded")
    parser.add_argument("--track", choices=["l_track", "oval"], default="l_track")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--laps", type=int, default=40)
    parser.add_argument("--output")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--terminal-mode", choices=spec.PROFILES, default=spec.DEFAULT_PROFILE)
    args = parser.parse_args()
    reports = []
    for seed in args.seeds or [args.seed]:
        output = Path(args.output or f"recordings/racing-v3/training/{args.terminal_mode}")/f"seed-{seed}"
        reports.append(train(args.track, seed, args.laps, output, args.resume, args.terminal_mode))
    if args.seeds:
        (Path(args.output or f"recordings/racing-v3/training/{args.terminal_mode}")/"benchmark.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    raise SystemExit(0 if all(r["passed"] for r in reports) else 1)


if __name__ == "__main__":
    main()
