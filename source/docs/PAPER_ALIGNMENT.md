# LMPC correspondence and explicit full-size adaptations

The primary reference is Rosolia and Borrelli, **Learning How to Autonomously Race a Car: A Predictive Control Approach**, IEEE TCST 28(6), 2020, DOI [10.1109/TCST.2019.2948135](https://doi.org/10.1109/TCST.2019.2948135), [author preprint](https://arxiv.org/pdf/1901.08184). The supplied published PDF was checked directly. Relevant pinned author source files are retained under `references/RacingLMPC`; their public code has defaults that differ from the published experiment.

**Current default: `robust-lmpc`, revision `racing-limits-lmpc-v3`. It is an explicitly adapted full-size LMPC, not an exact reproduction of the BARC experiment.** `paper-hard` remains available as a controller-equations comparison. [Current validation](VALIDATION.md) separates their results from the previous revisions.

## The requested half-car track rule

The car may extend **half its width beyond either road edge**: 0.9 m for the 1.8 m-wide preset. Rotation counts, including the front/rear corners. The measured legal margin is

```
road_width/2 + car_width/2 - abs(lateral_error)
  - abs(sin(heading_error))*car_length/2
  - abs(cos(heading_error))*car_width/2
```

Thus an aligned car may place its center on the road edge. A rotated car must keep its outward corner within the same 0.9 m allowance. The QP uses the conservative convex envelope `abs(ey) + length/2*abs(epsi) <= road_width/2`, and actual plant states use the trigonometric footprint above. Lap admission allows 1 cm numerical tolerance. Physics and recorded-lap validation share this rule; it is included in the configuration hash. This replaces v2's whole-car-inside rule. Tire grip remains the same approximation across the surface; there is no separately calibrated grass model.

## What follows the paper

All profiles store successful autonomous trajectories, select **20 nearby states from each of the latest two successful laps**, construct their six-dimensional convex hull, and use barycentric interpolation of observed remaining control steps as terminal cost. Neighbor selection uses progress, as the paper's matrix D does. The prediction candidate shifts and appends the selected samples' successors and controls, following Eq. (10) and Section IV-C. No centerline tracking cost or prescribed racing line is used.

States are `[vx, vy, yaw_rate, heading_error, progress, lateral_error]`; inputs are `[steering, acceleration]`, in SI units. Two conservative tracking laps initialize the successful history. Continuous progress and successor data extend across the finish line. Failed attempts and manual laps are excluded from successful training history; provisional continuation from a failed lap is rolled back. The periodic extension follows the authors' public code: cost-to-go can become negative past that lap's finish, and the horizon running cost is treated as constant in the QP. This differs from explicitly optimizing the discontinuous finish-indicator stage cost in Eq. (8a); the car keeps circulating rather than planning a stop at the line.

## Profile differences

| Component | Default `robust-lmpc` | `paper-hard` | `author-soft` |
| --- | --- | --- | --- |
| Control period | 0.1 s | 0.1 s | 0.1 s |
| Horizon | **24 steps / 2.4 s**, full-size tuning | **12 / 1.2 s**, published experiment | 12 / 1.2 s |
| Velocity prediction | Known nonlinear bicycle step plus regularized local residual regression | Paper Eq. (13), data-only weighted regression | Same data-only regression |
| Position prediction | Linearization of the complete discrete RK4/world-coordinate step and exact local Frenet projection | Paper Eq. (12), Euler/frozen curvature | Same Euler/frozen curvature |
| Terminal equality | Slack penalized by **500 times squared norm** | Hard, within solver tolerance | Same terminal-slack component as author code |
| Input increment cost | `[10,0.05]`, full-size tuning | `[1,0.01]`, explicit choice; paper does not publish these coefficients | `[1,0.01]` |
| Steering increment guard | 0.7 rad/s | None | None |
| Tire working-range penalty | Soft front/rear slip envelope derived from 90% nominal tire-force utilization; coefficient 10000 | None | None |
| Track rule | Requested half-width overhang | Same user-requested rule | Same user-requested rule |

The soft terminal equality is the direct fix for an exact historical six-state terminal combination being unreachable under model mismatch. It does **not** relax the road or actuator bounds. Terminal mismatch is exposed in telemetry and accumulated in validation reports. It is not the hard terminal-set guarantee in the paper.

The steering-rate guard prevents abrupt full-lock reversals that invalidated local predictions. The tire penalty discourages operation outside the nominal tire model's useful working range; its slack is recorded and is not a hard friction guarantee. It depends on **predicted vehicle slip**, not track-centerline curvature. A larger trajectory radius can therefore support more speed. There is no geometric corner-speed cap, previous-observed-speed cap, or lap-index speed schedule.

## Model correction and the S-bend fix

The strict data-only full-size controller fitted some poorly excited constant-speed data inaccurately, with large observed one-step yaw-rate errors. Robust mode learns **residual transitions**: observed next velocity minus the nonlinear nominal RK4 next velocity at each recorded state/input. It fits local residual slopes/intercepts with a ridge penalty toward zero. The neighborhood uses normalized `[vx,vy,r,steering,acceleration]` scales `[10,3,0.6,0.3,3]`, up to 80 points, compact bandwidth 0.55, and coefficient penalties `[25,25,25,25,2]`. These are full-size adaptation choices, not Eq. (13)'s original identification. Outside local support the nonlinear nominal model remains available.

The simulator plant and nominal bicycle currently have identical physical parameters, so residuals are approximately zero. The learned terminal set/value function and observed lap trajectories drive the racing-line improvement; this setup does not demonstrate identification of an unknown real Corvette. The residual framework can represent model mismatch, but transfer to a different plant is unvalidated.

Another repeated failure occurred exactly where track curvature changes sign. Holding curvature fixed for an entire 0.1 s step can predict the wrong reference-heading change when a fast car crosses that junction during the step. Robust mode now propagates the nonlinear RK4 step in world coordinates, projects the endpoint with a converged local Newton solve, and computes the discrete-step state/input Jacobian in a vectorized batch. Paper profiles retain their Euler approximation. A dedicated junction test compares against the actual plant and demonstrates the old heading-prediction error. The batch nominal model is also checked against the scalar plant.

For reproducibility, v3 metadata retains the paper-reference `regression_metric` and `identification_bandwidth` fields; robust overrides are explicitly recorded under `regularized_model`, `identification`, and `position_prediction`. Those effective model settings, the track policy, profile, and horizon all enter the configuration identity.

## Other differences and limits

- The paper uses the 1/10-scale physical BARC platform. This retains the requested approximate 1500 kg C4-sized bicycle, 2.44 m wheelbase, tanh-saturated tires, low-speed stabilization, and a 200 Hz RK4 plant. It is not calibrated BARC hardware or a measured Corvette. The reference L-track centerline is enlarged 20x to 384.5916 m, with an 8 m road. This is not a dynamically similar scale transformation.
- Warm-up tracking uses an 8 m/s setpoint rather than approximately 1.2 m/s BARC initialization, with seeded input excitation standard deviations `[0.0003 rad, 0.025 m/s²]`.
- All profiles impose fixed full-size operating bounds: vx in [0.5,36] m/s during prediction, heading error within +/-pi/2, steering +/-0.5 rad, acceleration [-7,3] m/s². The road envelope considers the car's dimensions rather than a point. Actual recorded states are checked at each 10 Hz control sample; a continuous-time footprint guarantee is not claimed.
- OSQP is primary; Clarabel can solve the identical QP after numerical failure. A retry can relinearize around a recorded trajectory. Explicit residual checks, iteration-limit acceptance rules, and floating-point tolerances are numerical implementation choices. A rejected attempt still pauses. No tracking-controller command is silently substituted during a learning lap.
- Retrying restores the recorded lap-start state **and previous control**, and clears stale barycentric warm starts. Retrying unchanged data does not itself learn from a rejected attempt.
- Unity, the C4-style body, ghosts, cameras, manual driving and replay are visualization features. Manual data remain separate. Replays never seed the learner. Old v1/v2 data and failed development trials remain preserved; new live sessions and benchmarks use separate profile/configuration directories.

The public author repository also differs from the paper: its pinned main uses N=14, its default safe-set configuration selects four fastest histories, and its regression uses a different input-inclusive L1 neighborhood. `author-soft` here selects only its terminal-relaxation component; it does not claim to duplicate that entire program. See [the archived v2 audit](PAPER_ALIGNMENT_V2.md) for the earlier paper-equations comparison.

Full-size stability and lap-time improvement are empirical checks, not transferred guarantees from the paper. See the current report for all attempts, terminal/tire slack, overhang and computation time.
