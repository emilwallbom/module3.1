"""Summarize the final robust-LMPC benchmark and retain negative comparisons."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from racing.session import Run
from racing import spec

ROOT=Path(__file__).resolve().parents[1]


def main():
    run=Run();base=ROOT/"recordings/racing-v3/validated"/spec.DEFAULT_PROFILE/run.identity[:12]
    reports=[];rows=[]
    for seed in range(5):
        folder=base/f"seed-{seed}"
        report=json.loads((folder/"report.json").read_text())
        checkpoint=json.loads((folder/"checkpoint.json").read_text())
        assert report["identity"]==checkpoint["identity"]==run.identity,"Stale controller report"
        assert report["laps"]==checkpoint["laps"],"Stale attempt report"
        timings=np.asarray(checkpoint["runtime"]["solve_times"])
        report["solver_max_ms"]=float(timings.max())
        report["solver_over_100ms"]=int((timings>100).sum())
        report["first_learning_lap_s"]=next((lap["seconds"] for lap in report["laps"] if lap["valid"] and lap["kind"]=="learn"),None)
        report["track_limit_passed"]=report["maximum_overhang_m"]<=report["allowed_overhang_m"]+.0100001
        reports.append(report)
        rows.append(f"| {seed} | {report['warmup_median']:.2f} | {report['first_learning_lap_s']:.2f} | {report['final_five_median']:.2f} | {report['learning_laps']} | {report['failed_attempts']} | {report['maximum_overhang_m']:.4f} | {report['solver_p95_ms']:.1f} |")
    suites=ET.parse(ROOT/"artifacts/tests-current.xml").getroot().findall("testsuite")
    tests=sum(int(s.attrib["tests"]) for s in suites)
    failures=sum(int(s.attrib["failures"])+int(s.attrib["errors"]) for s in suites)
    graphics=json.loads((ROOT/"artifacts/performance.json").read_text())
    isolated=json.loads((ROOT/"artifacts/controller-performance.json").read_text())
    assert isolated["identity"]==run.identity and not isolated["failure"]
    oval=json.loads((ROOT/"recordings/racing-v3/oval/seed-0/report.json").read_text())
    comparison=json.loads((ROOT/"artifacts/v3-paper-comparison/seed-0/report.json").read_text())
    passed=all(r["passed"] and r["learning_laps"]>=40 and r["track_limit_passed"] for r in reports)
    document={"algorithm_revision":spec.ALGORITHM_REVISION,"identity":run.identity,"profile":spec.DEFAULT_PROFILE,
              "benchmarks":reports,"learning_acceptance_passed":passed,"automated_tests":tests,"test_failures":failures,
              "graphics":graphics,"graphics_recording_source":"current-v3-benchmark-read-only-replay",
              "isolated_controller_performance":isolated,"oval":oval,"paper_hard_comparison":comparison}
    (base/"benchmark.json").write_text(json.dumps(reports,indent=2))
    (ROOT/"artifacts/validation-racing-v3.json").write_text(json.dumps(document,indent=2))
    (ROOT/"artifacts/validation.json").write_text(json.dumps(document,indent=2))
    fps=graphics.get("comparison_fps",graphics["fps_smoothed"])
    maximum_terminal=max(r["max_terminal_slack"] for r in reports)
    maximum_tire=max(r["max_tire_range_slack"] for r in reports)
    text=f"""# Current validation: racing limits and robust LMPC v3

Final configuration: `{run.identity}`, profile **{spec.DEFAULT_PROFILE}**, revision `{spec.ALGORITHM_REVISION}`. Tested on this PC on 24 November 2026: Windows 11, Ryzen 7 250, Radeon 780M, approximately 31 GiB RAM; Unity 6000.3.29f1, Windows x64 Mono/URP/D3D11.

**Current learning acceptance passed: {passed}.** All attempts are recorded. Five fixed seeds each request two warm-ups and 40 learning laps. Seeds vary the small warm-up input excitation; they do not represent different physical vehicles or road conditions.

| Seed | Warm-up median s | First learning s | Final five median s | Valid learning laps | Rejected | Maximum overhang m | Solver p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
"""+"\n".join(rows)
    text+=f"""

The requested overhang limit is **0.9 m**, with 0.01 m numerical admission tolerance. Overhang is measured from the rotated rectangular vehicle footprint at every recorded control sample. The same rule is used during driving and lap admission. Earlier whole-car-inside results use a different policy and are not directly comparable lap-time records.

The terminal equality is penalized, not hard: maximum recorded terminal-slack norm across these runs is **{maximum_terminal:.6f}** (the raw mixed-SI state norm), and maximum soft tire working-range slack is **{maximum_tire:.6f} rad**. These quantities are exposed rather than hidden. Actual road limits and actuator bounds remain enforced. The learned local convex hull is not claimed to be a formal safety guarantee for this adapted nonlinear plant.

The final controller has no centerline-curvature speed cap or lap-index speed schedule. It uses 24 steps at 10 Hz, nonlinear discrete-step prediction across curvature junctions, local residual learning against the bicycle model, a 0.7 rad/s steering-rate guard, and a soft tire working-range penalty. See [every paper divergence](PAPER_ALIGNMENT.md). First-learning versus final-five times are reported alongside the conservative warm-up comparison; improvement is not guaranteed on every individual lap.

All five seeds ran concurrently. Controller timing includes model identification, nonlinear-step linearization, QP assembly, numerical retries and solving; checkpoint serialization and plant integration are separate. Counts and maxima for solves exceeding 100 ms are retained in `artifacts/validation-racing-v3.json`. Occasional overruns slow simulation time rather than enlarging or dropping physics steps.

A separate checkpoint-reload check ran **{isolated['measured_solves']} control steps** with one controller, continuing from 40 to {isolated['final_learning_laps']} successful learning laps in memory, without modifying the saved benchmark. It measured **{isolated['solver_p95_ms']:.2f} ms p95**, maximum **{isolated['solver_max_ms']:.2f} ms**, and **{isolated['over_100ms']} solves over 100 ms**, with no failure. This represents the simulator's one-controller workload; the five-worker benchmark table includes concurrent CPU contention.

**{tests} automated tests, {failures} failures/errors.** Tests cover both sides of the half-car limit and rotated corners, nominal batch/scalar plant agreement, accurate prediction across the exact S-bend curvature-sign junction, the recorded v2 terminal dead end, paper Eq. (13) regression, terminal/cost/successor construction, retry control restoration, no geometric/data speed cap, checkpoint/profile isolation, current and legacy read-only replays, manual isolation, and real TCP disconnect/reconnect/shutdown.

The Windows build and real graphical smoke check completed. Four-car rendering measured **{fps:.1f} FPS at {graphics['width']} x {graphics['height']}**, p95 **{graphics['p95_frame_ms']:.2f} ms**, using only the four-car replay window after warm-up. All five cameras and overlays were captured, and manual acceleration/steering/braking were exercised; observed manual motion: {graphics.get('manual_exercise_observed')}. The replay source is the current benchmark, not the old v1 demonstration. Raw logs, screenshots and timing data are under `artifacts`.

The oval validation completed **{oval['learning_laps']} learning laps**, with **{oval['failed_attempts']} rejected attempts**: warm-up median {oval['warmup_median']:.2f} s, final-five median {oval['final_five_median']:.2f} s. It uses a separate track/configuration identity.

A new `paper-hard` comparison with the half-car rule remains unsuccessful: {comparison['learning_laps']} valid learning laps, {comparison['failed_attempts']} rejected attempts, stop reason `{comparison['failure']}`. It remains an explicit comparison option, not an automatic fallback for the robust mode.

Earlier development variants are preserved, including the initial v3 raw-state regression, tire-only fix, and residual model with frozen-curvature position prediction. They failed before the final nonlinear-junction correction. Their per-attempt reports/checkpoints remain in the older configuration folders under `recordings/racing-v3/validated`; pilot logs are under `artifacts/v3-*`. Historical v2 and v1 results are in [VALIDATION_PAPER_V2.md](VALIDATION_PAPER_V2.md) and [VALIDATION_LEGACY_V1.md](VALIDATION_LEGACY_V1.md). Their successes or failures do not replace the final configuration's results.

Current replay data: `recordings/racing-v3/validated/robust-lmpc/{run.identity[:12]}/seed-0`. Current live sessions have their own profile/configuration directory and cannot mix old data into learning. Source, player and recording archives are under `builds/delivery`. The car and tires remain approximate full-size simulation presets, not a calibrated real Corvette or the authors' BARC hardware.
"""
    (ROOT/"docs/VALIDATION.md").write_text(text,encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed and failures==0 and oval["passed"] else 1)


if __name__=="__main__":main()
