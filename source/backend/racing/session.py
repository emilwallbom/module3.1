"""Training state, manual isolation, lap admission, and resumable recordings."""
from copy import deepcopy
from pathlib import Path
import time
import numpy as np
from .controller import LMPC, TrackingController, ControlFailure
from .data import Lap, Repository, config_identity
from .track import Track
from .vehicle import Vehicle
from . import spec


class Run:
    def __init__(self, track="l_track", seed=0, directory=None, horizon=None, manual=False, terminal_mode=spec.DEFAULT_PROFILE):
        self.track = Track(track)
        self.vehicle = Vehicle(self.track)
        self.controller = LMPC(self.vehicle, horizon, terminal_mode=terminal_mode)
        self.tracker = TrackingController(self.vehicle)
        self.manual = manual
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.dt = 0.1
        self.world = self.vehicle.initial(0 if manual else 8)
        self.state = self.vehicle.state(self.world)
        self.last_input = np.zeros(2)
        self.laps = []
        self.completed = 0
        self.sim_time = 0.
        self.paused = False
        self.failure = ""
        self.solve_times = []
        self.max_terminal_slack = 0.
        self.max_tire_range_slack = 0.
        self.solver_events = []
        self.sequence = 0
        self._begin_lap()
        config, self.identity = config_identity(self.track, self.vehicle, horizon=self.controller.N, terminal_mode=terminal_mode)
        self.repository = Repository(directory, config, self.identity) if directory else None

    def _begin_lap(self):
        self.lap_start = self.world.copy()
        self.lap_start_control = self.last_input.copy()
        self.current_x = [self.local_state()]
        self.current_u = []
        self.current_poses = [self.world[:3].copy()]
        self.controller.new_lap()
        self.extension_target = next((lap for lap in reversed(self.laps) if lap.valid and lap.kind in ("learn", "warmup")), None)
        self.extension_count = len(self.extension_target.ext_x) if self.extension_target else 0

    def local_state(self):
        state = self.state.copy()
        state[4] -= self.completed*self.track.length
        return state

    @property
    def learning_laps(self):
        return sum(lap.valid and lap.kind == "learn" for lap in self.laps)

    @property
    def phase(self):
        if self.manual:
            return "drive"
        return "warmup" if sum(lap.valid and lap.kind in ("warmup", "learn") for lap in self.laps) < 2 else "learn"

    def step(self, manual_control=None):
        if self.paused:
            return
        phase = self.phase
        state = self.local_state()
        try:
            if self.manual:
                control = np.asarray(manual_control if manual_control is not None else [0, 0], dtype=float)
            elif phase == "warmup":
                control = self.tracker.solve(state)+self.rng.normal(0, spec.WARMUP_INPUT_NOISE_STD)
            else:
                control = self.controller.solve(state, self.laps)
                self.solve_times.append(self.controller.diagnostics["milliseconds"])
                self.max_terminal_slack=max(self.max_terminal_slack,self.controller.diagnostics.get("terminal_slack",0.))
                self.max_tire_range_slack=max(self.max_tire_range_slack,self.controller.diagnostics.get("tire_range_slack",0.))
                if (self.controller.diagnostics.get("accepted_feasible_iteration_limit") or self.controller.diagnostics.get("relinearizations")
                    or self.controller.diagnostics.get("solver") == "clarabel"):
                    self.solver_events.append({"time": self.sim_time, **self.controller.diagnostics})
            c = self.vehicle.config
            control = np.clip(control, [-c.max_steer,-c.max_brake], [c.max_steer,c.max_accel])
            world = self.vehicle.step(self.world, control, self.dt)
            next_state = self.vehicle.state(world, self.state[4])
            self.world, self.state = world, next_state
            self.last_input = control.copy()
            self.controller.last_input = control.copy()
            self.sim_time += self.dt
            self.sequence += 1
            self.current_u.append(control.copy())
            self.current_x.append(self.local_state())
            self.current_poses.append(world[:3].copy())
            if not self.manual and self.extension_target is not None and len(self.extension_target.ext_x) < self.controller.N+24:
                extension = self.local_state().copy()
                extension[4] += self.track.length
                self.extension_target.ext_x.append(extension)
                self.extension_target.ext_u.append(control.copy())
            margin = self.vehicle.footprint_margin(self.state)
            if margin < -0.01 and not self.manual:
                raise ControlFailure(f"Vehicle footprint crossed the road boundary ({margin:.3f} m)")
            if len(self.current_u) > 1800 and not self.manual:
                raise ControlFailure("Lap exceeded 180 seconds")
            if self.state[4] >= (self.completed+1)*self.track.length:
                valid = all(self.vehicle.footprint_margin(x) >= -0.01 for x in self.current_x)
                lap = self._make_lap(phase, valid, "" if valid else "Road boundary crossed")
                self.laps.append(lap)
                self.completed += 1
                self._begin_lap()
                self.save()
                return lap
        except (ControlFailure, FloatingPointError, ValueError, np.linalg.LinAlgError) as error:
            if self.manual:
                self.paused, self.failure = True, str(error)
                return
            if self.extension_target is not None:
                del self.extension_target.ext_x[self.extension_count:]
                del self.extension_target.ext_u[self.extension_count:]
            lap = self._make_lap(phase, False, str(error))
            self.laps.append(lap)
            self.solver_events.append({"time": self.sim_time, "event":"attempt_rejected", "reason":str(error),
                                       "diagnostics":dict(self.controller.diagnostics)})
            self.paused, self.failure = True, str(error)
            self.save()
            return lap

    def _make_lap(self, phase, valid, reason):
        return Lap(len(self.laps)+1, phase, np.asarray(self.current_x),
                   np.asarray(self.current_u).reshape(-1, 2), np.asarray(self.current_poses),
                   valid=valid, reason=reason)

    def recover(self):
        self.world = self.lap_start.copy()
        self.state = self.vehicle.state(self.world, self.completed*self.track.length)
        self.last_input = self.lap_start_control.copy()
        self.controller.last_input = self.last_input.copy()
        self.paused, self.failure = False, ""
        self._begin_lap()

    def save(self):
        if self.repository:
            self.repository.save(self.laps, {"seed": self.seed, "completed": self.completed,
                "sim_time": self.sim_time, "world": self.world.tolist(), "progress": float(self.state[4]),
                "last_input": self.last_input.tolist(), "rng": self.rng.bit_generator.state,
                "paused": self.paused, "failure": self.failure, "solve_times": self.solve_times,
                "lap_start": self.lap_start.tolist(), "lap_start_control":self.lap_start_control.tolist(),
                "max_terminal_slack":self.max_terminal_slack,"max_tire_range_slack":self.max_tire_range_slack,
                "solver_events": self.solver_events})

    def load(self):
        if not self.repository:
            raise ValueError("No recording directory configured")
        laps, runtime = self.repository.load()
        self.laps = laps
        self.completed = runtime["completed"]
        self.sim_time = runtime["sim_time"]
        self.world = np.array(runtime["world"])
        self.state = self.vehicle.state(self.world, runtime["progress"])
        self.last_input = np.array(runtime["last_input"])
        self.controller.last_input = self.last_input.copy()
        self.rng.bit_generator.state = runtime["rng"]
        self.solve_times = runtime.get("solve_times", [])
        self.max_terminal_slack=runtime.get("max_terminal_slack",0.)
        self.max_tire_range_slack=runtime.get("max_tire_range_slack",0.)
        self.solver_events = runtime.get("solver_events", [])
        self.paused, self.failure = runtime.get("paused", False), runtime.get("failure", "")
        self._begin_lap()
        if self.failure:
            self.lap_start = np.array(runtime["lap_start"])
            self.lap_start_control = np.array(runtime.get("lap_start_control",[0.,0.]))

    def report(self):
        warmup = [lap.seconds for lap in self.laps if lap.valid and lap.kind == "warmup"]
        learned = [lap.seconds for lap in self.laps if lap.valid and lap.kind == "learn"]
        baseline = float(np.median(warmup)) if warmup else None
        final = float(np.median(learned[-5:])) if learned else None
        valid=[lap.x for lap in self.laps if lap.valid]
        states=np.vstack(valid) if valid else np.zeros((1,6))
        c=self.vehicle.config
        outside=np.abs(states[:,5])+np.abs(np.sin(states[:,3]))*c.length/2+np.abs(np.cos(states[:,3]))*c.width/2-self.track.width/2
        return {"seed": self.seed, "track": self.track.name, "identity": self.identity,
                "algorithm_revision": spec.ALGORITHM_REVISION, "terminal_mode": self.controller.terminal_mode,
                "horizon": self.controller.N, "terminal_samples_per_lap": spec.TERMINAL_SAMPLES_PER_LAP,
                "max_terminal_slack":self.max_terminal_slack,"max_tire_range_slack":self.max_tire_range_slack,
                "maximum_overhang_m":float(max(0.,outside.max())),"allowed_overhang_m":c.width*spec.TRACK_OVERHANG_FRACTION,
                "warmup_median": baseline, "final_five_median": final,
                "improved": bool(baseline and final and final < baseline),
                "learning_laps": len(learned), "failed_attempts": sum(not l.valid for l in self.laps),
                "solver_p95_ms": float(np.percentile(self.solve_times, 95)) if self.solve_times else None,
                "laps": [lap.summary() for lap in self.laps], "failure": self.failure,
                "solver_events": self.solver_events}

    def frame(self):
        prediction = [] if self.controller.prediction is None or self.manual else [self.track.global_pose(x).tolist() for x in self.controller.prediction]
        samples = [] if self.manual else [self.track.global_pose(x).tolist() for x in self.controller.samples.T]
        return {"type": "frame", "protocol": 1, "sequence": self.sequence, "time": self.sim_time,
                "controller_profile": self.controller.terminal_mode, "algorithm_revision": spec.ALGORITHM_REVISION,
                "phase": self.phase, "paused": self.paused, "failure": self.failure,
                "pose": self.world[:3].tolist(), "state": self.state.tolist(),
                "control": self.last_input.tolist(), "prediction": prediction, "safe_samples": samples,
                "solver": self.controller.diagnostics, "lap": self.completed+1,
                "elapsed": len(self.current_u)*self.dt, "history": [lap.summary() for lap in self.laps]}


class Session:
    def __init__(self, track="l_track", seed=0, directory="recordings/racing-v3/live", terminal_mode=spec.DEFAULT_PROFILE):
        self.learn = Run(track, seed, Path(directory)/"autonomous", terminal_mode=terminal_mode)
        self.manual = Run(track, seed, Path(directory)/"manual", manual=True)
        self.mode = "learn"
        self.speed = 1.0
        self.control = np.zeros(2)
        self.replay_time = 0.
        self.replay_lap = None
        self.replay_paused = False
        self.selected_ghost = None
        self.message = ""
        self.revision = 0
        self.learning_target = 40
        self.external_replay_laps = None
        self.external_replay_label = ""

    def load_external_replay(self, directory):
        """Read-only replay of incompatible historical data; never replace learn."""
        import json
        document = json.loads((Path(directory)/"checkpoint.json").read_text(encoding="utf-8"))
        repository = Repository(directory, document["config"], document["identity"])
        laps, _ = repository.load()
        successful = [lap for lap in laps if lap.valid]
        if not successful:
            raise ValueError("Recording has no successful laps")
        self.external_replay_laps = laps
        revision=document["config"].get("algorithm_revision","unknown")
        profile=document["config"].get("terminal_mode","unknown")
        self.external_replay_label = ("REPLAY "+profile if revision==spec.ALGORITHM_REVISION
                                      else "LEGACY RECORDING - "+revision)
        self.replay_lap = successful[-1]
        self.replay_time = 0.
        self.replay_paused = False
        self.selected_ghost = None
        self.mode = "replay"
        self.revision += 1

    @property
    def display_laps(self):
        return self.external_replay_laps if self.mode == "replay" and self.external_replay_laps is not None else self.learn.laps

    @property
    def active(self):
        return self.manual if self.mode == "drive" else self.learn

    def command(self, document):
        command = document.get("command")
        if command == "mode":
            mode = document.get("value")
            if mode not in ("learn", "drive", "replay"):
                raise ValueError("Unknown mode")
            self.mode = mode
            if mode == "learn" and self.external_replay_laps is not None:
                self.external_replay_laps = None
                self.external_replay_label = ""
                self.replay_lap = self.selected_ghost = None
            self.control[:] = 0
            if mode == "replay" and self.replay_lap is None:
                self.replay_lap = next((l for l in reversed(self.learn.laps) if l.valid), None)
            self.revision += 1
        elif command == "control":
            control = np.asarray(document.get("value"), dtype=float)
            if control.shape != (2,) or not np.all(np.isfinite(control)):
                raise ValueError("Expected finite steering and acceleration")
            self.control = np.clip(control, [-0.5, -7], [0.5, 3])
        elif command == "pause":
            if self.mode == "replay":
                self.replay_paused = bool(document.get("value", not self.replay_paused))
            else:
                self.active.paused = bool(document.get("value", not self.active.paused))
                if self.mode == "learn" and not self.learn.paused and self.learn.learning_laps >= self.learning_target:
                    self.learning_target += 40
        elif command == "speed":
            value = float(document.get("value", 1))
            if value not in (0.25, 0.5, 1, 2, 4, 8):
                raise ValueError("Unsupported simulation speed")
            self.speed = value
        elif command == "reset":
            if self.mode == "drive":
                self.manual.world = self.manual.vehicle.initial(0)
                self.manual.state = self.manual.vehicle.state(self.manual.world)
                self.manual.completed = 0
                self.manual.paused, self.manual.failure = False, ""
                self.manual._begin_lap()
            else:
                self.learn.recover()
        elif command == "load":
            self.learn.load()
            self.revision += 1
        elif command == "save":
            if len(self.learn.current_u):
                self.message = "Checkpoints are saved automatically at completed lap boundaries."
            else:
                self.learn.save()
        elif command == "replay":
            number = int(document["lap"])
            self.replay_lap = next((l for l in self.display_laps if l.number == number and l.valid), None)
            if self.replay_lap is None:
                raise ValueError("Replay requires a successful recorded lap")
            self.replay_time = 0
            self.revision += 1
        elif command == "seek":
            self.replay_time = float(np.clip(float(document["value"]), 0, self.replay_lap.seconds if self.replay_lap else 0))
        elif command == "ghost":
            number = int(document["lap"])
            selected = None if number == 0 else next((l for l in self.display_laps if l.number == number and l.valid), None)
            if number and selected is None:
                raise ValueError("Ghost requires a successful recorded lap")
            self.selected_ghost = selected
            self.revision += 1
        else:
            raise ValueError("Unknown command")

    def step(self):
        if self.mode == "replay":
            if self.replay_lap and not self.replay_paused:
                self.replay_time = (self.replay_time+0.1) % self.replay_lap.seconds
            return
        lap = self.active.step(self.control if self.mode == "drive" else None)
        if lap:
            self.revision += 1
            if self.mode == "learn" and self.learn.learning_laps >= self.learning_target:
                self.learn.paused = True
                self.message = f"Completed {self.learning_target} learning laps. Replay, drive, or resume for another 40."

    def ghosts(self):
        laps = [lap for lap in self.display_laps if lap.valid]
        if not laps:
            return []
        selected = [("Baseline", laps[0]), ("Best", min(laps, key=lambda l: l.seconds)),
                    (f"Lap {self.selected_ghost.number}" if self.selected_ghost else "Previous", self.selected_ghost or laps[-1])]
        return [{"label": label, **lap.replay()} for label, lap in selected]

    def frame(self):
        frame = self.active.frame()
        frame.update({"mode": self.mode, "speed": 1 if self.mode == "drive" else self.speed,
                      "controller_profile": self.learn.controller.terminal_mode,
                      "message": self.message, "revision": self.revision,
                      "learning_history": [l.summary() for l in self.display_laps]})
        if self.mode == "replay" and self.replay_lap:
            frame["failure"] = ""
            frame["solver"] = {"status":"replay: controller inactive", "milliseconds":0.,
                               "terminal_slack":0., "terminal_residual":0., "horizon":0,"terminal_samples":0}
            frame["paused"] = self.replay_paused
            frame["replay_duration"] = self.replay_lap.seconds
            i = min(int(self.replay_time/self.replay_lap.dt), len(self.replay_lap.poses)-2)
            fraction = self.replay_time/self.replay_lap.dt-i
            frame["pose"] = ((1-fraction)*self.replay_lap.poses[i]+fraction*self.replay_lap.poses[i+1]).tolist()
            frame["elapsed"] = self.replay_time
            frame["state"] = self.replay_lap.x[i].tolist()
            frame["control"] = self.replay_lap.u[min(i,len(self.replay_lap.u)-1)].tolist()
            frame["phase"] = "replay"
            if self.external_replay_laps is not None:
                frame["controller_profile"] = self.external_replay_label
            frame["lap"] = self.replay_lap.number
            frame["prediction"], frame["safe_samples"] = [], []
        return frame
