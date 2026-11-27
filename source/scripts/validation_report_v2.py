"""Report current paper-aligned attempts without turning failures into passes."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from racing.session import Run

ROOT = Path(__file__).resolve().parents[1]


def main():
    all_reports = {}
    rows = []
    for mode in ("paper-hard", "author-soft"):
        reports = []
        expected = Run(terminal_mode=mode).identity
        for seed in range(5):
            folder = ROOT / "recordings/paper-v2/benchmarks" / mode / f"seed-{seed}"
            report = json.loads((folder / "report.json").read_text())
            checkpoint = json.loads((folder / "checkpoint.json").read_text())
            assert report["identity"] == checkpoint["identity"] == expected, "Stale controller results"
            assert report["laps"] == checkpoint["laps"], "Stale attempt report"
            reports.append(report)
            rows.append(f"| {mode} | {seed} | {report['learning_laps']} | {report['failed_attempts']} | {report['solver_p95_ms']:.1f} | {report['failure']} |")
        all_reports[mode] = reports
    suites = ET.parse(ROOT / "artifacts/tests-current.xml").getroot().findall("testsuite")
    tests = sum(int(s.attrib["tests"]) for s in suites)
    failures = sum(int(s.attrib["failures"])+int(s.attrib["errors"]) for s in suites)
    graphics = json.loads((ROOT / "artifacts/performance.json").read_text())
    graphics_fps = graphics.get("comparison_fps", graphics["fps_smoothed"])
    document = {"algorithm_revision":"paper-aligned-fullsize-v2", "benchmarks":all_reports,
                "learning_acceptance_passed":all(r["passed"] for reports in all_reports.values() for r in reports),
                "automated_tests":tests,"test_failures":failures,"graphics":graphics,
                "graphics_recording_source":"legacy-v1-read-only-replay"}
    (ROOT / "artifacts/validation-paper-v2.json").write_text(json.dumps(document, indent=2))
    canonical = ROOT / "artifacts/validation.json"
    legacy = ROOT / "artifacts/validation-legacy-v1.json"
    if canonical.exists() and not legacy.exists():
        legacy.write_bytes(canonical.read_bytes())
    canonical.write_text(json.dumps(document, indent=2))
    text = """# Current validation: paper-aligned full-size v2

**The revised learning benchmark has not passed.** The old 5 x 40-lap success belongs to v1, which used additional speed envelopes, model priors, and terminal slack. It does not validate the present controller. See [the historical report](VALIDATION_LEGACY_V1.md) and [the correspondence audit](PAPER_ALIGNMENT.md).

The default is N=12, 10 Hz, 20 terminal samples from each of the latest two successful laps, paper Eq. (13) data-only regression, and hard terminal equality. The optional `author-soft` variant changes terminal equality to the penalized slack from the authors' code. No speed-cap or nominal-model fallback is used.

Five seeds requested 40 learning laps each for each terminal mode. Each attempt stopped at its first rejection, as live autonomy does. All completed warm-up and learning laps and all rejected attempts are retained. These runs are **attempted 40-lap benchmarks**, not completed 40-lap sessions.

| Terminal mode | Seed | Valid learning laps | Rejected | Solver p95 ms | Stop reason |
| --- | --- | --- | --- | --- | --- |
""" + "\n".join(rows)
    text += f"""

The failures show that the copied paper controller and these initialization data are not a validated combination for this different full-size plant. Initial tests also tried richer speed/steering excitation; some completed a learning lap, but none established reliable multi-lap learning. Raw pilot results remain under `artifacts/paper-v2-*`. Those experiments are not defaults and do not contribute data to current sessions. Model adequacy and initialization remain unresolved; a longer horizon or a visually wider path alone would not prove a successful reproduction.

Automated checks: **{tests} tests, {failures} failures/errors**. These cover the exact paper neighborhood/kernel and weighted regression against direct least squares, missing-support rejection without a prior, hard terminal residuals, profile/configuration isolation, absence of geometric/data speed caps, safe-set/cost/successors, Frenet Jacobians, plant standstill/braking, real TCP disconnect/reconnect, invalid-lap rejection, checkpoints, and manual/replay isolation. Passing unit/integration tests does not establish the failed learning acceptance criterion.

The rebuilt Unity player measured **{graphics_fps:.1f} FPS** at {graphics['width']} x {graphics['height']}, {graphics['p95_frame_ms']:.2f} ms p95 frame time, with {graphics['rendered_cars']} cars. Timing samples are taken only during the four-car replay window after warm-up, separately from the later manual-driving exercise. The graphical check uses the visibly labeled legacy recording read-only; it validates rendering, cameras and manual motion, not v2 learning. Manual motion observed: {graphics.get('manual_exercise_observed')}. Logs, camera captures and raw measurements are under `artifacts`.

Current benchmark checkpoints and per-attempt reports are under `recordings/paper-v2/benchmarks/<terminal-mode>/seed-*`. Historical successful recordings remain under `recordings/validated`, loaded only for read-only legacy replay. Source, Windows player and recording archives are under `builds/delivery`. The full-size tire model and C4-style fallback are approximate; the account-gated Ricy model is not bundled.
"""
    (ROOT / "docs/VALIDATION.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
