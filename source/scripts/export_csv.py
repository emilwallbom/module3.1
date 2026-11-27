"""Export checkpoint trajectories without admitting them into a training session."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path, help="Directory containing checkpoint.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = json.loads((args.checkpoint / "checkpoint.json").read_text(encoding="utf-8"))
    filename = document["arrays"]
    if Path(filename).name != filename:
        raise ValueError("Array filename must be local")
    output = args.output or args.checkpoint / "csv"
    output.mkdir(parents=True, exist_ok=True)
    with np.load(args.checkpoint / filename, allow_pickle=False) as arrays:
        for index, lap in enumerate(document["laps"]):
            states, controls, poses = (arrays[f"{index}_{key}"] for key in ("x", "u", "poses"))
            with (output / f"lap-{lap['number']:03d}-{lap['kind']}.csv").open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["time_s", "vx_mps", "vy_mps", "yaw_rate_radps", "heading_error_rad",
                                 "progress_m", "lateral_error_m", "world_x_m", "world_y_m", "yaw_rad",
                                 "steering_rad", "acceleration_mps2"])
                for step, (state, pose) in enumerate(zip(states, poses)):
                    control = controls[step] if step < len(controls) else ["", ""]
                    writer.writerow([step * .1, *state, *pose, *control])
    print(f"Exported {len(document['laps'])} trajectories to {output}")


if __name__ == "__main__":
    main()
