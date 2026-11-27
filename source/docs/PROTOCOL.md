# Local simulation bridge, protocol 1

The server binds only `127.0.0.1:8765`. Messages are UTF-8 JSON objects separated by newlines. One viewer owns a connection at a time. Maximum incoming buffered command size is 1 MiB. Every command contains `protocol: 1`. No network service or cloud training is used.

On connection, `hello` supplies the configuration identity and track samples (`s,x,y,heading,curvature`) in SI units. `ghosts` supplies baseline/best/previous-or-selected recordings with `dt`, poses, and speeds. `frame` supplies mode, sequence, simulated time, pose, six-state vector, input, current prediction, projected terminal samples, history, solver diagnostics, and slowdown. Frame updates are at 10 simulation Hz; Unity interpolates poses for rendering. The plant uses 200 Hz internal integration. Poses are `{x,y,yaw}`; Unity maps world `(x,y)` to `(x,0,y)` and yaw to `90°-yaw` because the visual car faces local +Z.

Commands:

| Command | Additional fields |
| --- | --- |
| `mode` | `value`: `learn`, `drive`, or `replay` |
| `control` | `value`: `[steering_radians, acceleration_m_per_s2]` |
| `pause` | Optional boolean `value`; omitted means toggle |
| `speed` | `value`: 0.25, 0.5, 1, 2, 4, or 8; driving always runs at 1× |
| `reset` | Retry current autonomous lap, or reset manual car |
| `load` | Load the live autonomous checkpoint |
| `demo` | Open the current default-profile/configuration seed-0 benchmark read-only |
| `legacy_demo` | Open the historical v1 seed-0 recording with a legacy label |
| `save` | Request a completed-lap checkpoint; current partial laps are not persisted |
| `replay` | `lap`: successful recorded lap number |
| `ghost` | `lap`: successful lap number, or 0 for latest |
| `seek` | `value`: elapsed replay seconds |
| `shutdown` | Stop the helper owned by a launcher/test |

Invalid protocol versions, commands, non-finite controls, and incompatible checkpoints are rejected with a viewer message. A disconnect clears manual input and pauses the current mode. Reconnection preserves the last state; Resume is explicit. Solver failure never causes skipped/enlarged physics steps. When computation takes longer than the requested wall-clock period, simulation slows and the viewer reports the slowdown.


## Controller identity and profiles

Frames include `algorithm_revision` and `controller_profile` (`robust-lmpc`, `paper-hard`, `author-soft`, a current replay label, or a legacy replay label). Solver diagnostics include `terminal_mode`, `horizon`, `terminal_samples`, `terminal_residual`, `terminal_slack`, and `tire_range_slack`. The default is the explicit full-size robust adaptation, with nonlinear discrete prediction and penalized terminal mismatch. Paper-hard comparison is explicitly selected. Protocol 1 is retained; these fields are additive.

The `demo` and `legacy_demo` commands import recordings into a read-only replay store and enter Replay; they never replace the current autonomous Run, configuration, checkpoint or learned data. Entering Learn discards the external replay view. `learning_history` and ghosts show the selected replay store only while replaying it. Default benchmarks and live sessions are separated by profile and configuration hash under `recordings/racing-v3`.
