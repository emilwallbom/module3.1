> HISTORICAL v1 RESULTS. Superseded by paper-aligned v2. These results do not validate the current controller. See VALIDATION.md and PAPER_ALIGNMENT.md.

# Validation on this PC

Windows 11, Ryzen 7 250, Radeon 780M, 31 GiB RAM. Unity 6000.3.29f1, Windows x64 Mono, URP, Direct3D 11. Tests run on 24 November 2026.

All five fixed seeds completed two warm-up laps and 40 learning laps with zero rejected attempts. Results include every attempt. The final five-lap median is lower than the conservative warm-up baseline for every seed.

| Seed | Warm-up median (s) | Final five median (s) | Rejected | Solver p95 (ms) | Solves >100 ms |
| --- | --- | --- | --- | --- | --- |
| 0 | 48.25 | 25.00 | 0 | 69.8 | 119 |
| 1 | 48.25 | 25.10 | 0 | 70.1 | 109 |
| 2 | 48.25 | 25.00 | 0 | 69.6 | 125 |
| 3 | 48.25 | 25.10 | 0 | 40.0 | 19 |
| 4 | 48.25 | 25.00 | 0 | 69.3 | 113 |

Seeds 0, 1, 2, and 4 ran concurrently; seed 3 ran separately. These timings include local identification and QP setup/solve. Occasional overruns remain: this is a desktop simulation, with fixed simulation steps and displayed slowdown rather than a hard real-time controller. Numerical retries and feasible iteration-limit results appear in each report's `solver_events`. These empirical results do not imply monotonic improvement or transfer the paper's guarantees to this approximate full-size model.

The real graphical player measured **60.0 FPS** at **1280×720**, with 4 cars and **16.67 ms p95 frame time**. Six screenshots cover five cameras and overlays; automated manual acceleration, steering, and braking exercised the same model. Manual motion was observed: True. Captures are in `artifacts/view-*.png`; logs and raw measurements are alongside them.

The oval completed five learning laps without rejection: warm-up median 56.2 s, final-five median 40.0 s.

All **16 automated tests passed**: track closure and coordinate conversion, finish-line continuation, standstill/braking, analytic Frenet Jacobians, safe-set/cost construction, local regression and out-of-support prior, constrained QP backup, invalid-lap rejection/recovery, checkpoint identity, manual isolation, replay/ghost interpolation, pause/reset, real TCP disconnect/reconnect, and graceful shutdown. The idempotent setup script and Windows player build also completed successfully. Trajectory CSV export was checked on all 42 recorded seed-3 laps.

`recordings/validated/seed-0` is the supplied replayable learning session. All five complete benchmark recordings, per-attempt CSV summaries, configuration hashes, and JSON reports are included locally. Earlier development attempts remain under `artifacts`, including `pre-final-benchmark-reports.json`; they are not final acceptance results.

The shipped body is the original simplified C4-style fallback. The account-gated Ricy asset was not downloaded; its optional FBX importer is unverified against that asset. Dynamics are approximate, and driving supports forward acceleration/braking with reset for recovery.
