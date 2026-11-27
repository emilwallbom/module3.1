> HISTORICAL v2: before the half-car track allowance and robust terminal/junction fixes. See PAPER_ALIGNMENT.md and VALIDATION.md for the current version.

# Current validation: paper-aligned full-size v2

**The revised learning benchmark has not passed.** The old 5 x 40-lap success belongs to v1, which used additional speed envelopes, model priors, and terminal slack. It does not validate the present controller. See [the historical report](VALIDATION_LEGACY_V1.md) and [the correspondence audit](PAPER_ALIGNMENT.md).

The default is N=12, 10 Hz, 20 terminal samples from each of the latest two successful laps, paper Eq. (13) data-only regression, and hard terminal equality. The optional `author-soft` variant changes terminal equality to the penalized slack from the authors' code. No speed-cap or nominal-model fallback is used.

Five seeds requested 40 learning laps each for each terminal mode. Each attempt stopped at its first rejection, as live autonomy does. All completed warm-up and learning laps and all rejected attempts are retained. These runs are **attempted 40-lap benchmarks**, not completed 40-lap sessions.

| Terminal mode | Seed | Valid learning laps | Rejected | Solver p95 ms | Stop reason |
| --- | --- | --- | --- | --- | --- |
| paper-hard | 0 | 0 | 1 | 25.9 | LMPC QP: primal infeasible; primal=0.01002, dual=0.221 |
| paper-hard | 1 | 0 | 1 | 21.0 | LMPC QP: primal infeasible; primal=0.09095, dual=2.786 |
| paper-hard | 2 | 1 | 1 | 25.7 | LMPC QP: maximum iterations reached; primal=0.0005584, dual=0.01401 |
| paper-hard | 3 | 0 | 1 | 43.9 | Identification has only 0 samples inside the paper kernel; no model substituted |
| paper-hard | 4 | 0 | 1 | 46.3 | LMPC QP: primal infeasible; primal=0.04775, dual=0.9562 |
| author-soft | 0 | 0 | 1 | 23.1 | Identification has only 4 samples inside the paper kernel; no model substituted |
| author-soft | 1 | 0 | 1 | 21.9 | Identification has only 0 samples inside the paper kernel; no model substituted |
| author-soft | 2 | 1 | 1 | 34.7 | Identification has only 0 samples inside the paper kernel; no model substituted |
| author-soft | 3 | 1 | 1 | 32.0 | Identification has only 0 samples inside the paper kernel; no model substituted |
| author-soft | 4 | 0 | 1 | 24.5 | Identification has only 1 samples inside the paper kernel; no model substituted |

The failures show that the copied paper controller and these initialization data are not a validated combination for this different full-size plant. Initial tests also tried richer speed/steering excitation; some completed a learning lap, but none established reliable multi-lap learning. Raw pilot results remain under `artifacts/paper-v2-*`. Those experiments are not defaults and do not contribute data to current sessions. Model adequacy and initialization remain unresolved; a longer horizon or a visually wider path alone would not prove a successful reproduction.

Automated checks: **20 tests, 0 failures/errors**. These cover the exact paper neighborhood/kernel and weighted regression against direct least squares, missing-support rejection without a prior, hard terminal residuals, profile/configuration isolation, absence of geometric/data speed caps, safe-set/cost/successors, Frenet Jacobians, plant standstill/braking, real TCP disconnect/reconnect, invalid-lap rejection, checkpoints, and manual/replay isolation. Passing unit/integration tests does not establish the failed learning acceptance criterion.

The rebuilt Unity player measured **60.0 FPS** at 1280 x 720, 16.67 ms p95 frame time, with 4 cars. Timing samples are taken only during the four-car replay window after warm-up, separately from the later manual-driving exercise. The graphical check uses the visibly labeled legacy recording read-only; it validates rendering, cameras and manual motion, not v2 learning. Manual motion observed: True. Logs, camera captures and raw measurements are under `artifacts`.

Current benchmark checkpoints and per-attempt reports are under `recordings/paper-v2/benchmarks/<terminal-mode>/seed-*`. Historical successful recordings remain under `recordings/validated`, loaded only for read-only legacy replay. Source, Windows player and recording archives are under `builds/delivery`. The full-size tire model and C4-style fallback are approximate; the account-gated Ricy model is not bundled.
