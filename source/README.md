# Corvette C4 LMPC Racing Lab

A local Unity 6.3 LTS / URP racing simulator using LMPC safe-set/value-function learning. **Current revision: `racing-limits-lmpc-v3`; default profile: `robust-lmpc`.** The default is an explicitly adapted full-size controller, with the user-requested half-car track allowance, penalized terminal mismatch, and nonlinear-step prediction across curvature junctions.

Read [the paper correspondence and every known divergence](docs/PAPER_ALIGNMENT.md), then [current validation results](docs/VALIDATION.md). The paper-hard comparison remains available. Source/player/recording archives are under `builds/delivery`; use the root launchers for the complete simulator, including its Python helper.

Validated on this PC: **five seeds x 40 learning laps, zero rejected attempts**. First-learning lap time was 22.6 s; the final-five median was 19.6 s (warm-up median 48.25 s). The current four-car replay measured 60 FPS at 720p. These are results for the documented full-size adaptation and half-car rule, not a reproduction of the paper's BARC experiment.

## Start

Double-click **Run Simulator.cmd** for a new robust learning run, or **Watch Demo.cmd** for the current recorded benchmark. Unity and Python are installed locally and the Unity Personal license is activated.

The launcher starts the localhost Python helper and closes it when the game exits. Only one simulator viewer can use the local simulation at a time. Running a launcher again restores the existing window instead of opening a second disconnected copy; use its LEARN / DRIVE / REPLAY buttons to change modes. Always start through a root launcher, since the player executable alone does not start Python. A new run makes two conservative warm-up laps, then requests 40 learning laps. `LOAD SAVED` restores the current configuration's live checkpoint. `LOAD DEMO` opens the current benchmark read-only; `OLD v1` opens the historical demo with a legacy label. Replays never enter current training. Selecting a recorded lap enters Replay.

**Track limit:** up to 0.9 m (half the 1.8 m car width) may extend beyond either road edge. An aligned car can put its center on the edge. Rotation and front/rear corners count, so this is not permission to place the whole car outside the road. Physics and lap validation use the same rule.

**Run Paper Hard.cmd** selects the paper-equations comparison (1.2 s, data-only regression, hard terminal equality); it can become infeasible on the full-size plant. **Run Author Soft Terminal.cmd** selects its terminal-relaxation variant. These are separate from the default robust adaptation, with separate checkpoints. Genuine failures still pause and reject the attempt; a rejected lap does not improve the successful safe set by repeated retries.

| Control | Action |
| --- | --- |
| W / Up | Accelerate |
| S / Down / Space | Brake |
| A/D or Left/Right | Fast steering; sensitivity reduces with speed |
| C | Chase, cockpit, hood, overhead, orbit |
| Right-drag / mouse wheel | Orbit angle / distance |
| Tab | Focus the active car or a ghost |
| G | Toggle ghosts |
| L | Learning overlays |
| P | Pause/resume the current mode |
| R | Reset manual car, or retry a rejected AI attempt from its lap start |
| M | Switch Learn / Drive |
| H / Escape | Help |

Keyboard steering reaches full low-speed lock in about **0.11 s** (previously 0.50 s), recenters faster on release, and changes direction quickly. Its maximum angle reduces with speed so short key taps are easier to control. This is a Unity input mapping change; AI controls, the vehicle physics, and learning settings are unchanged. See [presentation and steering changes](docs/PRESENTATION.md).

The **LAPS** panel selects recorded laps for replay or replaces the third ghost with a historical lap. The replay slider seeks through the selected lap. Baseline, best, and previous/selected ghosts use equal elapsed lap time, never collisions. `Drive` has a separate vehicle state, lap store, and input stream; it cannot seed or alter the learner. Forward driving and braking are supported; R recovers an off-track manual car.

## Portable ZIP for another PC

Send **`builds/delivery/CorvetteLMPC-Portable-Windows-x64.zip`**, not this entire development folder and not the older player-only ZIP. Extract the whole ZIP to a writable folder on a Windows 10/11 x64 PC, then double-click its **Run Simulator.cmd**. It includes a private Python runtime, locked solver dependencies, the Windows player, and current/historical demo recordings. No Unity Editor, Unity login, separate Python installation, or internet access is required to run it. A Direct3D 11 graphics driver is required.

Use **Watch Demo.cmd** to open the included learning session read-only. Keep the extracted folders together and launch outside the ZIP. Close another simulator copy before running a different extracted folder, since they use the same localhost port. The archive is about 98 MiB; a download link may be more practical than an email attachment.

Build and validate it with `.venv\Scripts\python.exe scripts/package_portable.py` and `scripts/validate_portable.py`. Validation extracts the actual ZIP to a different Unicode path, isolates Python imports and native DLLs, executes real MPC solves, runs the actual player, and exercises the recipient launcher. See [portable packaging details](docs/PORTABLE.md).

## What learns

All profiles use the **latest two** successful autonomous laps and **20 nearby terminal samples per lap**. Their six-dimensional convex hull and recorded remaining control steps provide the terminal set and cost. The shifted prediction uses matching successor states/controls. Lap data and value functions update after each successful lap. There is no prescribed racing-line target or centerline tracking cost.

The default `robust-lmpc` uses **24 steps at 10 Hz (2.4 s)** and terminal equality slack penalized by 500 times its squared norm. It predicts the discrete nonlinear RK4 step in world coordinates, including curvature-sign changes inside a control step, then projects back to Frenet coordinates and linearizes. This resolves the frozen-curvature prediction error found at the S-bend junction.

Robust velocity identification learns local **residuals against the nonlinear bicycle model**, with regularization toward zero correction. Because the simulated plant uses the same physical parameters, residuals are nearly zero here; trajectory and learned value-function updates drive the racing-line improvement. A steering-rate guard and a soft tire-slip working-range penalty protect local predictions. These are documented full-size adaptations, not the paper's data-only identification or hard-terminal guarantee.

`paper-hard` retains **N=12**, the paper's Eq. (13) data-only regression (P=80, h=10, state metric diag(0.1,1,1)), Euler Frenet kinematics and hard terminal equality. `author-soft` changes that terminal equality to the authors' public code's slack component. The [alignment audit](docs/PAPER_ALIGNMENT.md) lists exact parameters and remaining differences for all profiles.

There is **no track-centerline corner-speed cap**, no previous-observed-speed cap, and no lap-index speed schedule. Tire penalties depend on the predicted car state; a smoother trajectory can support a higher speed. Terminal mismatch and tire-range slack are visible in telemetry and reported in validation. Failed and manual laps remain excluded from successful history.

States are `[vx, vy, yaw_rate, heading_error, progress, lateral_error]`; inputs are `[steering, acceleration]`, in SI units. The approximate 1500 kg C4-sized plant integrates at 200 Hz independently of rendering. The circuit centerline is the reference L-track at 20x scale, **384.5916 m**, with an 8 m road. Green dots are projected six-dimensional terminal samples, not geometric safe volumes; blue-to-red recorded lines encode speed.

## Tools and reproducibility

- **Open Unity Project.cmd** opens the editable project and its local backend.
- **Build Simulator.cmd** builds the Windows x64 Mono player.
- **Train Headless.cmd** accepts the arguments below.
- **Run Benchmark.cmd** runs the five-seed / 40-lap validation.
- **Setup.cmd** restores local tools and the locked Python environment.
- **Activate Unity.cmd** handles interactive browser login and explicit terms acceptance on a new machine.

```powershell
.\.venv\Scripts\python.exe -m racing.train --laps 40 --seed 0
.\.venv\Scripts\python.exe -m racing.train --track oval --laps 5 --output recordings/racing-v3/oval
.\.venv\Scripts\python.exe -m racing.train --terminal-mode author-soft --laps 40
.\.venv\Scripts\python.exe scripts/benchmark.py --seeds 0 1 2 3 4 --workers 5
.\.venv\Scripts\python.exe scripts/export_csv.py PATH_TO_CHECKPOINT_DIRECTORY
.\.venv\Scripts\python.exe -m pytest -q
```

Current recordings are under `recordings/racing-v3`, partitioned by profile and configuration identity. The previous `recordings/validated` and `recordings/paper-v2` data remain preserved as historical results; they cannot seed the current learner. Tools are under `.tools`, configurable caches under `.cache`, Unity sources under `UnityProject`, Python sources under `backend`, player files under `builds/CorvetteLMPC`, and experiment data under `recordings`. Unity is pinned to **6000.3.29f1**, CLI **1.0.1**, Python **3.12.15**; exact Python dependencies are in `uv.lock`. The tool installer verifies Unity release-feed checksums. Its per-process user installation avoids optional shared CPU lightmapper components. The installer reports that remote profiling firewall rules were not installed; the local simulator does not require remote profiling.

Unity's normal account/credential, license, preference, and terms records can live in Windows locations. All installed simulator executables, including the Editor's licensing client, are under this project. A small documented repair supplies two missing `.meta` files in the shipped URP package; `scripts/repair_urp_metadata.py` reproduces it without changing vendor source.

Checkpoints contain JSON metadata and generation-named NPZ arrays loaded without pickle, with an atomic metadata switch. They preserve successful history and finish-line continuation samples. A configuration hash prevents mixing incompatible tracks, vehicles, horizons, terminal modes, identification settings or algorithm revisions. Opening an existing incompatible output directory is refused before any checkpoint is overwritten. `laps.csv` summarizes attempts beside each checkpoint; `scripts/export_csv.py` exports every trajectory sample, pose, and applied input into per-lap CSV files. Interrupted runs preserve their last completed-lap checkpoint. The current partial lap is not a durable checkpoint. Retry restores the lap-start state and preceding control and clears stale terminal warm starts.

## Optional detailed C4 body

The targeted [1990 Corvette C4 by Ricy](https://sketchfab.com/3d-models/1990-corvette-c4-2d005bd8f19b4959b5196e69defebae7) is listed under CC BY 4.0, but its download API requires a Sketchfab account. It is **not included**. The original C4-style fallback requires no account and includes a sculpted wedge body, sloped glass, a modeled cockpit with animated steering wheel, directional C4-style sawblade wheels with open wheel arches, mirrors, vents, raised rectangular pop-up headlights, and four round tail lamps. The circuit uses original procedural surface textures, pit garages, grandstands, Armco barriers, trees and hills, HDR color grading, soft shadows, and environment reflections. A compact track map shows active and ghost positions. Active and ghost motion share a timestamped render timeline, so 10 Hz telemetry is interpolated on every render frame. The cockpit uses a separate low dashboard and clear windshield opening. See [motion and cockpit changes](docs/MOTION_AND_C4.md). Nearby ghost bodies are hidden in cockpit/hood views to preserve visibility; their recordings and map positions remain unchanged.

If you obtain a licensed FBX version, open Unity and choose **Tools → Corvette Lab → Import licensed C4 FBX**. The importer copies the model and neighboring texture files, normalizes its length, converts materials, and creates a Resources prefab. Check front/rear orientation and mesh names; imported wheel renderers named wheel/tire/tyre/rim are replaced by the simulator's animated wheels. Other wheel names require manual cleanup. The optional importer cannot be verified against the account-gated model here. Include its author's attribution if using that model in a shared build.

## Research attribution

Ugo Rosolia and Francesco Borrelli, **Learning How to Autonomously Race a Car: A Predictive Control Approach**, IEEE Transactions on Control Systems Technology 28(6), 2020, DOI [10.1109/TCST.2019.2948135](https://doi.org/10.1109/TCST.2019.2948135).

Reference implementation: [urosolia/RacingLMPC](https://github.com/urosolia/RacingLMPC), revision `b49c95e7795ef6f343efacedb6b90a69c7855b32`. The local-safe-set, value-function, model-identification approach, and L-track geometry follow that work. This project contains a new full-size adaptation, not the authors' experimental BARC software. It is intended for education and research.
