# Current validation: racing limits and robust LMPC v3

Final configuration: `317a6cfacb0371cf368252c40e241792b32369ba3931e398536d1b8b7505db92`, profile **robust-lmpc**, revision `racing-limits-lmpc-v3`. Tested on this PC on 24 November 2026: Windows 11, Ryzen 7 250, Radeon 780M, approximately 31 GiB RAM; Unity 6000.3.29f1, Windows x64 Mono/URP/D3D11.

**Current learning acceptance passed: True.** All attempts are recorded. Five fixed seeds each request two warm-ups and 40 learning laps. Seeds vary the small warm-up input excitation; they do not represent different physical vehicles or road conditions.

| Seed | Warm-up median s | First learning s | Final five median s | Valid learning laps | Rejected | Maximum overhang m | Solver p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 48.25 | 22.60 | 19.60 | 40 | 0 | 0.9044 | 108.3 |
| 1 | 48.25 | 22.60 | 19.60 | 40 | 0 | 0.9042 | 107.6 |
| 2 | 48.25 | 22.60 | 19.60 | 40 | 0 | 0.9034 | 106.6 |
| 3 | 48.25 | 22.60 | 19.60 | 40 | 0 | 0.9043 | 107.7 |
| 4 | 48.25 | 22.60 | 19.60 | 40 | 0 | 0.9036 | 106.9 |

The requested overhang limit is **0.9 m**, with 0.01 m numerical admission tolerance. Overhang is measured from the rotated rectangular vehicle footprint at every recorded control sample. The same rule is used during driving and lap admission. Earlier whole-car-inside results use a different policy and are not directly comparable lap-time records.

The terminal equality is penalized, not hard: maximum recorded terminal-slack norm across these runs is **0.050158** (the raw mixed-SI state norm), and maximum soft tire working-range slack is **0.005425 rad**. These quantities are exposed rather than hidden. Actual road limits and actuator bounds remain enforced. The learned local convex hull is not claimed to be a formal safety guarantee for this adapted nonlinear plant.

The final controller has no centerline-curvature speed cap or lap-index speed schedule. It uses 24 steps at 10 Hz, nonlinear discrete-step prediction across curvature junctions, local residual learning against the bicycle model, a 0.7 rad/s steering-rate guard, and a soft tire working-range penalty. See [every paper divergence](PAPER_ALIGNMENT.md). First-learning versus final-five times are reported alongside the conservative warm-up comparison; improvement is not guaranteed on every individual lap.

All five seeds ran concurrently. Controller timing includes model identification, nonlinear-step linearization, QP assembly, numerical retries and solving; checkpoint serialization and plant integration are separate. Counts and maxima for solves exceeding 100 ms are retained in `artifacts/validation-racing-v3.json`. Occasional overruns slow simulation time rather than enlarging or dropping physics steps.

A separate checkpoint-reload check ran **500 control steps** with one controller, continuing from 40 to 42 successful learning laps in memory, without modifying the saved benchmark. It measured **39.13 ms p95**, maximum **75.87 ms**, and **0 solves over 100 ms**, with no failure. This represents the simulator's one-controller workload; the five-worker benchmark table includes concurrent CPU contention.

**27 automated tests, 0 failures/errors.** Tests cover both sides of the half-car limit and rotated corners, nominal batch/scalar plant agreement, accurate prediction across the exact S-bend curvature-sign junction, the recorded v2 terminal dead end, paper Eq. (13) regression, terminal/cost/successor construction, retry control restoration, no geometric/data speed cap, checkpoint/profile isolation, current and legacy read-only replays, manual isolation, and real TCP disconnect/reconnect/shutdown.

The Windows build and real graphical smoke check completed. Four-car rendering measured **60.0 FPS at 1280 x 720**, p95 **16.68 ms**, using only the four-car replay window after warm-up. All five cameras and overlays were captured, and manual acceleration/steering/braking were exercised; observed manual motion: True. The replay source is the current benchmark, not the old v1 demonstration. Raw logs, screenshots and timing data are under `artifacts`.

The oval validation completed **5 learning laps**, with **0 rejected attempts**: warm-up median 56.20 s, final-five median 21.30 s. It uses a separate track/configuration identity.

A new `paper-hard` comparison with the half-car rule remains unsuccessful: 0 valid learning laps, 1 rejected attempts, stop reason `LMPC QP: primal infeasible; primal=0.4856, dual=0.224`. It remains an explicit comparison option, not an automatic fallback for the robust mode.

Earlier development variants are preserved, including the initial v3 raw-state regression, tire-only fix, and residual model with frozen-curvature position prediction. They failed before the final nonlinear-junction correction. Their per-attempt reports/checkpoints remain in the older configuration folders under `recordings/racing-v3/validated`; pilot logs are under `artifacts/v3-*`. Historical v2 and v1 results are in [VALIDATION_PAPER_V2.md](VALIDATION_PAPER_V2.md) and [VALIDATION_LEGACY_V1.md](VALIDATION_LEGACY_V1.md). Their successes or failures do not replace the final configuration's results.

Current replay data: `recordings/racing-v3/validated/robust-lmpc/317a6cfacb03/seed-0`. Current live sessions have their own profile/configuration directory and cannot mix old data into learning. Source, player and recording archives are under `builds/delivery`. The car and tires remain approximate full-size simulation presets, not a calibrated real Corvette or the authors' BARC hardware.

Latest renderer, cockpit, and C4 validation: [MOTION_AND_C4.md](MOTION_AND_C4.md). The controller benchmark above is unchanged; the later presentation update passes 30 Python tests and 19 Unity keyboard/motion checks, with its own build-hashed performance report.
