# Terminal dead-end regression

`terminal_deadend_v2.npz` contains the two latest successful simulator trajectories and failing state/control from the user's local v2 session. It includes the corresponding recorded continuation arrays. These are simulator-generated data, not measurements from the authors' BARC experiment.

The v2 controller repeatedly rejected this state at the beginning of the next lap. The regression test verifies that the robust v3 QP can solve it while respecting its control bounds and steering-rate guard. Multi-lap stability is checked separately by the seeded benchmarks; this fixture alone does not establish it.
