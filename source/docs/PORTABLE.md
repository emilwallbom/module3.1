# Portable Windows delivery

The recipient archive is `builds/delivery/CorvetteLMPC-Portable-Windows-x64.zip`. Extract its entire `CorvetteLMPC-Portable` folder into a writable location, then double-click its `Run Simulator.cmd`. `Watch Demo.cmd`, the two comparison-profile launchers, and `Check Portable.cmd` are also provided. This package targets Windows 10/11 x64 with a Direct3D 11 graphics driver. It does not require an Editor installation/activation, external Python, administrator installation, or online package downloads.

## What is bundled

The archive contains the finished Unity Mono player, the unchanged Python backend, private CPython 3.12.15, the installed production dependency closure checked against `uv.lock`, app-local C/C++ runtime DLLs, and two curated demo checkpoints (current robust-lmpc seed 0 and historical v1 seed 0). It contains no Unity Editor, licensing client, account credentials, development caches, manual recordings, or live AI sessions. Python and dependency license files remain included. Microsoft deployment documentation: [application-local redistributable DLLs](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files).

The copied virtual environment is deliberately not used. `runtime/python/python312._pth` specifies only package-relative standard-library, DLL, site-package, backend and launcher paths. Launchers use `-I` isolation. Registry-installed Python, user-site packages, `PYTHONHOME` and `PYTHONPATH` cannot supply missing code. The app-local CRT uses Python's VCRuntime 14.44 and NumPy's redistributed MSVCP 14.40; an older Editor-helper MSVCP caused a native OSQP crash in isolated validation and is not shipped.

`portable-manifest.json` pins dependencies, controller identity, and SHA-256 hashes for every shipped payload file. It excludes itself to avoid a recursive hash. The ZIP also has an external SHA-256 sidecar. New checkpoints/logs/cache files appear only after running, under `recordings/racing-v3/live`, `artifacts`, and `.cache`; Windows/Unity can also create their usual user preferences and logs.

The localhost bridge remains port 8765. Only one extracted project folder can run at a time. The existing launcher mutex prevents duplicate viewers within a folder. Close the game normally so its launcher stops its Python helper. The standalone EXE alone does not start the backend, so use the supplied CMD launcher.

## Rebuild and test

Run from the development environment:

```powershell
.\.venv\Scripts\python.exe scripts\package_portable.py
.\.venv\Scripts\python.exe scripts\validate_portable.py
```

The packaging script creates a fresh staging directory, copies only runtime dependencies and curated recordings, checks native PE import availability, writes the manifest, and atomically replaces the portable ZIP. No download or installer is invoked. The validation script must run with other simulator copies closed.

Validation uses the actual ZIP, verifies its file hashes, extracts to a folder containing spaces and Unicode, poisons external Python settings, and limits PATH to Windows system binaries. The private-runtime check imports/exercises NumPy, SciPy, OSQP and Clarabel, checks all import paths and loaded CRT locations, then runs 50 real robust-LMPC steps from a read-only checkpoint. The graphical check exercises the actual private player/backend, four-car replay, cameras, and manual controls. Finally it runs the recipient CMD from an unrelated working directory, checks duplicate-launch focus, and verifies backend shutdown after closing the player.

This is a relocation test on this PC, not a claim that a separate clean physical PC or VM has been tested. The MPC, physics, training settings, and checkpoint configuration identity are unchanged. Device performance still depends on the destination PC.

## Completed validation

The actual ZIP is 102,772,147 bytes (98.0 MiB). SHA-256: `c0b358e7f168283e1583cbf10e3aa02ceba4edb88af99e4f68bf1b3318b95b15`. All 4,059 payload hashes were verified after extraction. The private runtime passed 50 actual robust-LMPC solves with no failure or checkpoint modification; controller computation p95 was 35.7 ms. App-local CRT locations and package-only import paths were asserted.

The relocated graphical test measured 60.0 FPS at 1280 x 720 with four cars and zero held frames across 1860 measured moving frames. It captured five camera views plus learning overlays, and exercised manual acceleration/steering/braking. The recipient's exact Run Simulator.cmd was then launched from an unrelated working directory; repeat launch retained the same player PID, and closing the player stopped its backend. The existing development suite also passed all 30 tests.

Reports are `artifacts/portable-validation.json`, `artifacts/portable-runtime-check.log`, `artifacts/portable-visual-check.log`, and `artifacts/tests-portable.xml`. The original MPC/physics/dependency hashes were rechecked unchanged. A separate clean physical PC or VM was not tested.
