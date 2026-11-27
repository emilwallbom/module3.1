# Continuous motion, clear cockpit, and C4 body

The Python backend, MPC, vehicle dynamics, controller timing, keyboard steering mapping, training configuration, and checkpoint identity are unchanged. This update affects Unity presentation and validation tooling.

## Motion

The former renderer repeatedly eased toward a pose held for 100 ms. It therefore accelerated toward each new sample and slowed before the next one; its ghosts used the same held lap clock without frame interpolation. A 60 FPS counter could coexist with visibly jerky car motion. The chase camera added another positional low-pass and more lag.

The receiver now timestamps packets on its background thread with a monotonic clock. A bounded read-only pose buffer tracks the actual simulation pace, with a target 120 ms of wall-time buffering. A continuously advanced render clock interpolates position with endpoint world velocities and heading with yaw rate, using cubic Hermite curves and the short heading arc. Phase correction adapts to speed changes. This is a display buffer, not a change to the simulation or a claim of zero input latency. No future vehicle travel is extrapolated beyond received states.

Ghosts sample their recordings on that same interpolated elapsed-lap clock. Their positions use neighboring trajectory samples for smooth tangents. Lap boundaries, natural replay loops, seeks, mode changes, pause, reset, failures and disconnects are handled explicitly. A disconnected viewer drains only its existing buffer and holds the last authoritative pose.

Car transforms receive the interpolated pose directly. The camera follows that pose without a second positional low-pass. Wheel rotation follows displayed signed travel, so it stops when the car stops and scales with training pace. These visual positions and controls are never returned to Python or admitted as training data. Learning overlays still show the actual controller outputs at their native update rate.

## Cockpit

A dedicated driver interior replaces the exterior shell while the focused car is viewed from the cockpit. It has a lower dashboard, lower instrument pod, and smaller steering wheel. The exterior roof, opaque windshield, seats and body therefore cannot obscure the road. The eye is at local `[-0.31, 1.10, -0.42]` m, with a 68-degree vertical field of view and a slight downward pitch. This interior is an original simplified view model, not an exact reconstruction of the factory dashboard. Other cameras retain the exterior model; nearby ghosts remain hidden from the driver view.

## C4 styling

The original fallback now has a shaped clamshell-style hood and fenders, actual wheel-arch openings, recessed wheel wells, a long wedge nose, raised rectangular pop-up headlamps, a targa-style greenhouse, sloping rear hatch and sail panels, thin bumper/door rub strips, a painted rear fascia with four round lamps, rear lettering, and directional sawblade-style wheels. Paint and lamp materials were adjusted. Vehicle dimensions and physics are unchanged.

This remains an original C4-inspired approximation, rather than an exact stock model-year reconstruction. No external car mesh or reference photograph is bundled. A [1990 C4 rear three-quarter reference](https://www.corvsport.com/1990-c4-corvette-image-gallery/185527_rear_3-4_web/) and the [front reference photograph](https://commons.wikimedia.org/wiki/File:1990_C4_Corvette_front.jpg) informed the styling direction. The optional separately licensed model remains supported.

## Checks

The unchanged Python suite passes **30 tests**. Editor checks pass **8 keyboard checks** and **11 motion checks**, including jittered 10 Hz input rendered at 60 Hz, constant-velocity accuracy, heading wrap, disconnect hold, pause/reset/mode changes, replay loops/seeks, and a 1x-to-3x pace change. The synthetic 10 m/s test has no held frames after settling. Exact results are in `artifacts/motion-checks.json`.

Visual validation now uses a unique output folder per run and refuses an early-closed test window. Only a completed 75-second run replaces the canonical screenshots and performance report, and its report records the hash of the tested player assembly. The validator holds the same single-viewer lease as the normal launcher.

Completed player run for assembly `762f0806ac3c13ba526f936da67f4d019edb118f66e8b252811642f4343c70e6`: **59.9 FPS at 1280 x 720 with four cars**, frame-time p95 **16.87 ms**, and **zero held motion frames out of 1855** moving frames. All five cameras plus the learning overlay view were captured, and manual acceleration/steering/braking were exercised. No runtime exception or bridge-packet warning was observed. The source clock advanced by 0.0139–0.0240 simulated seconds per sampled render frame.

The jittered synthetic test at 10 m/s advanced 0.1616–0.1708 m per 60 Hz frame (ideal 0.1667 m). Exact reports: `artifacts/performance-motion.json`, `artifacts/motion-checks.json`, and `artifacts/tests-motion.xml`. Screenshots: `artifacts/view-1.png` (cockpit), `artifacts/view-4.png` (orbit), and the other captured views. Backend/dependency integrity was rechecked against the pre-presentation hashes: 11 files, zero changes.
