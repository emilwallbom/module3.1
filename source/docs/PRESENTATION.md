# Presentation and keyboard steering update

This update changes Unity rendering and the mapping from keyboard keys to manual steering. The Python backend is byte-for-byte unchanged, including MPC, identification, safe sets, objectives, constraints, track geometry, vehicle dynamics, integration, timing, and recording admission. Controller identity remains `317a6cfacb0371cf368252c40e241792b32369ba3931e398536d1b8b7505db92`. Existing checkpoints remain compatible. No new paper-method divergence is introduced by the presentation work; existing controller adaptations are documented in [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md).

## Manual steering

Previously the input filter moved at 0.9 rad/s toward a fixed 0.45 rad target: half a second to reach lock. The new Unity-only mapping uses 4 rad/s when applying steering, 6 rad/s when reversing direction, and 8 rad/s when releasing the key. At 60 FPS, full low-speed lock is reached within seven frames (117 ms), release from full lock within four frames (67 ms), and opposite lock within eleven frames (184 ms).

The maximum keyboard angle is `clamp(0.45 / (1 + (abs(vx)/12)^2), 0.085, 0.45)` radians. Parking steering retains the original 0.45 rad range; at 25 m/s the limit is 0.085 rad. This reduces abrupt high-speed oversteer from binary keys. Focus loss clears the filtered input and sends the existing brake command. Throttle and brake mapping are unchanged.

These times describe the input filter. Manual control still uses the existing backend control cadence and vehicle model. AI steering does not use this keyboard filter or its speed-dependent limit. The visual steering bar shows the applied backend control.

## Original visual assets

The procedural C4 fallback now has a beveled wedge body, angled windshield and hatch glass, beltline trim, door handles, fender vents, mirrors, five-spoke wheels, tire shoulders, exhausts, and a modeled cockpit with an animated steering wheel. It remains an original simplified C4-style model; the optional account-gated Ricy model is not bundled.

The circuit has procedural asphalt, grass, gravel and curb textures; road-edge paint and grid markings; Armco; pit garages and race control; a grandstand; irregular tree canopies; and rolling hills. HDR color grading, a procedural sky, soft sun shadows, restrained bloom and vignette, and a one-time environment reflection probe provide the lighting. Static meshes are batched by material. All scenery is decorative and has no physics colliders.

The interface uses flat button states, calmer panels, a live steering indicator, and a compact track map. All existing modes, commands, overlays, recordings and cameras remain available. The chase camera is closer and the cockpit viewpoint is seated behind the wheel. Ghosts remain synchronized to the same recording times. Ghost bodies within five metres of the focused camera car are hidden in cockpit/hood views to avoid blocking the road; their map positions and underlying recordings remain available. Four-car performance samples include only frames with all three ghost bodies active.

## Validation on this PC

- Windows x64 Mono build: passed.
- Existing Python suite: **27 passed** (`artifacts/tests-presentation.xml`).
- Editor keyboard checks: **8 passed** (`artifacts/keyboard-steering-checks.json`).
- Backend/dependency integrity: **11 files checked, zero changes** (`artifacts/presentation-integrity.json`; original hashes in `artifacts/presentation-baseline.json`).
- Real player smoke test: all five camera views plus learning overlays captured; manual acceleration, steering and braking exercised; no runtime exception, error or protocol packet warning.
- Four-car comparison: **60.00 FPS**, 1280 x 720, **16.67 ms** frame-time p95 over 1500 sampled frames (`artifacts/performance-presentation.json`). Screenshots are under `artifacts/simulator.png` and `artifacts/view-0.png` through `view-5.png`.

The existing five-seed learning benchmark remains the validation of the unchanged controller. It was not rerun for this rendering and keyboard-input update.

## Startup fix: repeated launches

A demo window left open could occupy the single-viewer Python server. Previously another launch reused that server but started a second player, which stayed on “Local server is not running” without receiving track geometry. The launcher now holds a Windows named mutex scoped to this workspace for the lifetime of the interactive viewer. Repeated launches validate the recorded viewer PID against its actual executable path, restore its window, and return without starting a second backend or player. This does not change the server, control cadence, or MPC. Closing the owning launcher releases the kernel handle automatically, so a stale metadata file does not keep the application locked.

Validation: 30 tests pass, including cross-process viewer exclusion, automatic lease release, executable identity checks, and proof that a duplicate launch cannot spawn a backend/player. A real second invocation of Run Simulator.cmd kept the same single player PID and the same established server connection.

## Later motion and cockpit correction

The pose easing and exterior-shell cockpit described above have been superseded by the timestamped playback and dedicated driver interior in [MOTION_AND_C4.md](MOTION_AND_C4.md). That document describes the current renderer and C4 fallback. The MPC backend remains unchanged.
