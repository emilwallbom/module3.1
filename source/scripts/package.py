"""Archive editable sources and the player; local tool installation stays separate."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / "builds" / "delivery"
    destination.mkdir(parents=True, exist_ok=True)
    files = list(ROOT.glob("*.cmd")) + [ROOT / name for name in
        ("README.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "uv.lock", "tools-lock.json", ".gitignore")]
    for folder in ("backend", "scripts", "tests", "docs", "references", "UnityProject/Assets", "UnityProject/Packages", "UnityProject/ProjectSettings"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".egg-info" not in str(p))
    with ZipFile(destination / "CorvetteLMPC-source.zip", "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
    with ZipFile(destination / "CorvetteLMPC-Windows-player.zip", "w", ZIP_DEFLATED) as archive:
        for path in (ROOT / "builds" / "CorvetteLMPC").rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT / "builds"))
    with ZipFile(destination / "CorvetteLMPC-recordings.zip", "w", ZIP_DEFLATED) as archive:
        for folder in (ROOT / "recordings" / "validated", ROOT / "recordings" / "paper-v2" / "benchmarks",
                       ROOT / "recordings" / "racing-v3" / "validated"):
            for path in folder.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(ROOT))
    print(f"Archives written to {destination}. Player requires the local Python backend; use the root launchers.")


if __name__ == "__main__":
    main()
