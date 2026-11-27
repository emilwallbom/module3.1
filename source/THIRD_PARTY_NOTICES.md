# Attribution and included dependencies

The controller design and L-track geometry follow Rosolia and Borrelli and the UC Berkeley MPC Laboratory's RacingLMPC reference. See README for the paper citation and pinned source revision. Their reference code permits educational/research extensions with clear attribution; no claim is made that this adaptation reproduces their real-car experimental results.

Selected unmodified source files from that pinned revision are retained under `references/RacingLMPC` for the paper-versus-code audit. Their `src/main.py` contains the authors' educational/research licensing and attribution notice. These files are reference material and are not imported by the simulator. Default controller settings follow the paper where the public repository differs; see `docs/PAPER_ALIGNMENT.md`.

The supplied procedural Corvette C4-style mesh and synthesized scene are original project assets. The separately linked Ricy C4 model is **not bundled**. Its public metadata lists CC BY 4.0; if imported, credit **“1990 Corvette C4” by Ricy (@ngon_3d), Sketchfab, CC BY 4.0**, with the model and license links.

Unity Editor, Unity CLI, and the Unity player runtime remain subject to Unity's licenses and Editor Software Terms. NumPy, SciPy, OSQP, Clarabel, and their dependencies retain the licenses installed in the local Python environment. Portable 7-Zip tools used during installation investigation are under `.tools/7zip`; their included license files remain with them. They are not required by the running simulator.
