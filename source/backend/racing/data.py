from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import numpy as np
from . import spec


def config_identity(track, vehicle, dt=spec.DT, horizon=None, terminal_mode=spec.DEFAULT_PROFILE):
    if horizon is None:horizon=spec.ROBUST_HORIZON if terminal_mode=="robust-lmpc" else spec.HORIZON
    config = {"schema": 1, "algorithm_revision": spec.ALGORITHM_REVISION, "history_laps": spec.HISTORY_LAPS,
              "terminal_samples_per_lap": spec.TERMINAL_SAMPLES_PER_LAP,
              "regression_neighbors": spec.REGRESSION_NEIGHBORS, "regression_metric": spec.REGRESSION_METRIC,
              "identification_bandwidth": spec.REGRESSION_BANDWIDTH,
              "identification": "bicycle-model-plus-local-rk4-residual-regression" if terminal_mode=="robust-lmpc" else "paper-eq13-weighted-lstsq-no-prior",
              "position_prediction": "discrete-rk4-world-flow-and-newton-frenet-projection" if terminal_mode=="robust-lmpc" else "paper-euler-frenet",
              "regularized_model": {"scales":[10.,3.,.6,.3,3.],"bandwidth":.55,"prior_weights":[25.,25.,25.,25.,2.]} if terminal_mode=="robust-lmpc" else None,
              "steering_rate_guard": spec.ROBUST_STEERING_RATE if terminal_mode=="robust-lmpc" else None,
              "tire_working_range": {"utilization":spec.ROBUST_TIRE_UTILIZATION,"slip_penalty":spec.ROBUST_SLIP_PENALTY} if terminal_mode=="robust-lmpc" else None,
              "terminal_mode": terminal_mode, "terminal_slack_weight": 500. if terminal_mode != "paper-hard" else 0.,
              "input_rate_weights": [10.,.05] if terminal_mode=="robust-lmpc" else spec.INPUT_RATE_WEIGHTS,
              "warmup_input_noise_std": spec.WARMUP_INPUT_NOISE_STD,
              "road_constraint": "footprint-with-width-overhang", "overhang_fraction":spec.TRACK_OVERHANG_FRACTION,
              "track": track.name, "width": track.width, "length": track.length,
              "vehicle": vehicle.identity(), "dt": dt, "horizon": horizon,
              "state_order": ["vx", "vy", "yaw_rate", "heading_error", "progress", "lateral_error"],
              "input_order": ["steering", "acceleration"]}
    return config, hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


@dataclass
class Lap:
    number: int
    kind: str
    x: np.ndarray
    u: np.ndarray
    poses: np.ndarray
    dt: float = 0.1
    valid: bool = True
    reason: str = ""
    ext_x: list = field(default_factory=list)
    ext_u: list = field(default_factory=list)

    @property
    def seconds(self):
        return len(self.u)*self.dt

    def arrays(self):
        x = np.vstack([self.x, self.ext_x]) if self.ext_x else self.x
        u = np.vstack([self.u, self.ext_u]) if self.ext_u else self.u
        return x, u

    def summary(self):
        return {"number": self.number, "kind": self.kind, "seconds": self.seconds,
                "valid": self.valid, "reason": self.reason}

    def replay(self):
        return {**self.summary(), "dt": self.dt, "poses": self.poses.tolist(),
                "speeds": self.x[:, 0].tolist()}


class Repository:
    def __init__(self, directory, config, identity):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config, self.identity = config, identity
        checkpoint = self.directory/"checkpoint.json"
        if checkpoint.exists():
            existing = json.loads(checkpoint.read_text(encoding="utf-8"))
            if existing.get("identity") != identity:
                raise ValueError("Existing recording configuration does not match; choose a new output directory")

    def save(self, laps, runtime):
        arrays = {}
        for index, lap in enumerate(laps):
            for name in ["x", "u", "poses", "ext_x", "ext_u"]:
                arrays[f"{index}_{name}"] = np.asarray(getattr(lap, name))
        # Immutable generations ensure a crash never pairs new metadata with old arrays.
        import uuid
        generation = uuid.uuid4().hex
        filename = f"trajectories-{generation}.npz"
        np.savez_compressed(self.directory/filename, **arrays)
        document = {"schema": 1, "identity": self.identity, "config": self.config,
                    "arrays": filename, "laps": [lap.summary() for lap in laps], "runtime": runtime}
        temporary = self.directory/"checkpoint.json.partial"
        temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
        temporary.replace(self.directory/"checkpoint.json")
        # Preserve the current and previous generation; recordings remain bounded.
        generations = sorted(self.directory.glob("trajectories-*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
        for obsolete in generations[2:]:
            obsolete.unlink()
        self.export_csv(laps)

    def load(self):
        document = json.loads((self.directory/"checkpoint.json").read_text(encoding="utf-8"))
        if document.get("schema") != 1 or document["identity"] != self.identity:
            raise ValueError("Checkpoint configuration does not match this track/vehicle/controller")
        filename = document["arrays"]
        if Path(filename).name != filename:
            raise ValueError("Checkpoint array filename must be local")
        laps = []
        with np.load(self.directory/filename, allow_pickle=False) as arrays:
            for i, summary in enumerate(document["laps"]):
                lap = Lap(summary["number"], summary["kind"], arrays[f"{i}_x"].copy(),
                          arrays[f"{i}_u"].copy(), arrays[f"{i}_poses"].copy(),
                          valid=summary["valid"], reason=summary["reason"])
                lap.ext_x = list(arrays[f"{i}_ext_x"].copy())
                lap.ext_u = list(arrays[f"{i}_ext_u"].copy())
                laps.append(lap)
        return laps, document["runtime"]

    def export_csv(self, laps):
        import csv
        with (self.directory/"laps.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["number", "kind", "seconds", "valid", "reason"])
            writer.writeheader()
            writer.writerows(lap.summary() for lap in laps)


def local_safe_set(laps, progress, neighbors=spec.TERMINAL_SAMPLES_PER_LAP, *, include_inputs=False):
    successful = [lap for lap in laps if lap.valid and lap.kind in ("warmup", "learn")][-spec.HISTORY_LAPS:]
    if len(successful) < 2:
        raise ValueError("LMPC needs two successful autonomous initialization laps")
    states, successors, costs, successor_inputs = [], [], [], []
    for lap in successful:
        x, u = lap.arrays()
        usable = x[:-1]
        count = min(neighbors, len(usable))
        indices = np.argsort(abs(usable[:, 4]-progress), kind="stable")[:count]
        states.extend(usable[indices])
        successors.extend(x[indices+1])
        costs.extend(len(lap.u)-indices)
        successor_inputs.extend(u[np.minimum(indices+1, len(u)-1)])
    result = np.array(states).T, np.array(successors).T, np.asarray(costs, dtype=float)
    return (*result, np.array(successor_inputs).T) if include_inputs else result

