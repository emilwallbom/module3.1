"""Build an offline, relocatable Windows x64 simulator from the locked local tools."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from racing.session import Run
from portable_native import imports

ROOT=Path(__file__).resolve().parents[1]


def copy_tree(source,target):
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc","*.pyo"))


def dependencies():
    pending=["numpy","scipy","osqp","clarabel"];found={}
    locked={canonicalize_name(p["name"]):p["version"] for p in tomllib.loads((ROOT/"uv.lock").read_text())["package"] if "version" in p}
    while pending:
        name=canonicalize_name(pending.pop())
        if name in found:continue
        dist=metadata.distribution(name)
        if locked.get(name)!=dist.version:raise RuntimeError(f"Installed {name} is not the locked version")
        found[name]=dist
        for text in dist.requires or []:
            requirement=Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({"extra":""}):pending.append(requirement.name)
    return found


def build():
    lock=json.loads((ROOT/"tools-lock.json").read_text())
    identity=Run().identity
    stage=ROOT/"builds"/"portable-staging"/uuid.uuid4().hex/"CorvetteLMPC-Portable"
    stage.mkdir(parents=True)
    python_source=ROOT/".tools/python/cpython-3.12-windows-x86_64-none"
    runtime=stage/"runtime/python";runtime.mkdir(parents=True)
    for name in ("python.exe","pythonw.exe","python3.dll","python312.dll","vcruntime140.dll","vcruntime140_1.dll","LICENSE.txt"):
        shutil.copy2(python_source/name,runtime/name)
    copy_tree(python_source/"DLLs",runtime/"DLLs")
    shutil.copytree(python_source/"Lib",runtime/"Lib",ignore=shutil.ignore_patterns("site-packages","__pycache__","*.pyc","*.pyo","test","idlelib","tkinter","ensurepip"))
    site=runtime/"Lib/site-packages";site.mkdir()
    dists=dependencies()
    for name,dist in dists.items():
        for entry in dist.files or []:
            relative=Path(str(entry))
            if ".." in relative.parts or "__pycache__" in relative.parts or relative.suffix in {".pyc",".pyo",".pth"}:continue
            source=Path(dist.locate_file(entry))
            if not source.is_file():continue
            destination=site/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
    # _pth completely replaces registry, user-site, PYTHONHOME and PYTHONPATH lookup.
    (runtime/"python312._pth").write_text("Lib\nDLLs\nLib\\site-packages\n..\\..\\backend\n..\\..\\scripts\nimport site\n",encoding="ascii")
    copy_tree(ROOT/"backend/racing",stage/"backend/racing")
    (stage/"scripts").mkdir()
    for name in ("launch.py","performance_check.py","visual_check.py","portable_check.py"):
        shutil.copy2(ROOT/"scripts"/name,stage/"scripts"/name)
    player=stage/"builds/CorvetteLMPC"
    shutil.copytree(ROOT/"builds/CorvetteLMPC",player,ignore=shutil.ignore_patterns("*DoNotShip*","*.pdb"))
    # App-local release CRT components from the locked Python/NumPy distributions.
    # The Editor helper's older 14.34 MSVCP crashes OSQP's newer std::mutex ABI.
    msvcp=next((site/"numpy.libs").glob("msvcp140-*.dll"))
    crt={"msvcp140.dll":msvcp,"vcruntime140.dll":python_source/"vcruntime140.dll",
         "vcruntime140_1.dll":python_source/"vcruntime140_1.dll"}
    for folder in (runtime,player):
        for name,path in crt.items():shutil.copy2(path,folder/name)
    for name in ("tools-lock.json","uv.lock","THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT/name,stage/name)
    (stage/"docs").mkdir()
    for name in ("PAPER_ALIGNMENT.md","VALIDATION.md","MOTION_AND_C4.md"):
        shutil.copy2(ROOT/"docs"/name,stage/"docs"/name)
    # Only the referenced generation of two curated, non-personal demonstration checkpoints.
    for relative in (Path("recordings/racing-v3/validated/robust-lmpc")/identity[:12]/"seed-0",Path("recordings/validated/seed-0")):
        source=ROOT/relative;target=stage/relative;target.mkdir(parents=True)
        document=json.loads((source/"checkpoint.json").read_text())
        for name in ("checkpoint.json",document["arrays"],"laps.csv"):
            if (source/name).is_file():shutil.copy2(source/name,target/name)
    commands={"Run Simulator.cmd":"play","Watch Demo.cmd":"play --demo",
              "Run Paper Hard.cmd":"play --terminal-mode paper-hard","Run Author Soft Terminal.cmd":"play --terminal-mode author-soft",
              "Check Portable.cmd":"check"}
    for name,arguments in commands.items():
        program="scripts\\portable_check.py" if arguments=="check" else "scripts\\launch.py "+arguments
        text='@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"runtime\\python\\python.exe" -I '+program+'\r\n'
        text+='pause\r\n' if arguments=="check" else 'if errorlevel 1 pause\r\n'
        (stage/name).write_bytes(text.encode("ascii"))
    (stage/"README.txt").write_text("""CORVETTE C4 LMPC — PORTABLE WINDOWS x64

1. Extract the ENTIRE ZIP into a writable folder, such as your Desktop.
2. Open that extracted folder and double-click Run Simulator.cmd.
   Do not run from inside the ZIP. Keep all its folders together.

Windows 10/11 x64 and a Direct3D 11 graphics driver are required.
No Unity Editor, Unity login, separate Python installation, administrator
installation, or internet connection is required to run this package.

Watch Demo.cmd opens the included 40-learning-lap run read-only.
LEARN / DRIVE / REPLAY switch modes. LOAD SAVED restores your local run.
LOAD DEMO opens the current benchmark; OLD v1 opens the historical demo.
Manual laps and replays never enter training data.

W/Up: throttle   S/Down/Space: brake   A/D/arrows: steer
C: camera   Tab: focus car/ghost   G: ghosts   L: learning overlays
P: pause   R: reset/retry   M: Learn/Drive   H/Escape: help

Only one copy can use localhost port 8765 at a time; close any other
simulator folder before opening this one. Launching again in this folder
restores its current window. The game EXE alone does not start Python:
use Run Simulator.cmd. Close the game normally to stop its helper.

Your checkpoints and manual recordings stay under recordings/racing-v3/live.
Portable logs and configurable caches stay under artifacts and .cache.
Windows/Unity may also create normal user preferences and player logs.
Check Portable.cmd verifies private Python, dependencies and MPC solving.

The physics and MPC match the source project. The robust-lmpc default is
an explicitly adapted full-size controller; see docs/PAPER_ALIGNMENT.md.
The car is an original simplified C4-style model, not an imported asset.

Dependency versions and every shipped file hash are in portable-manifest.json.
Python's license is runtime/python/LICENSE.txt. Each Python dependency retains
its license files in runtime/python/Lib/site-packages/<package>.dist-info.
Microsoft app-local C/C++ release runtime DLLs retain Microsoft's copyright;
deployment reference: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
Unity player runtime remains subject to Unity's terms; no Editor/account/
license credentials are included. See THIRD_PARTY_NOTICES.md for attribution.
""",encoding="utf-8")
    manifest={"schema":1,"platform":"Windows x64","python":lock["python_version"],"unity":lock["unity_version"],
        "controller_identity":identity,"dependencies":{n:d.version for n,d in sorted(dists.items())},
        "python_path_mode":"relative python312._pth; isolated -I; no virtualenv",
        "crt_source":"App-local MSVCP 14.40 from the locked NumPy wheel; VCRuntime 14.44 from locked CPython", "files":{}}
    for path in sorted(stage.rglob("*")):
        if path.is_file():manifest["files"][path.relative_to(stage).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    (stage/"portable-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    # Ensure every direct non-system PE dependency is present somewhere in the bundle.
    binaries=[p for p in stage.rglob("*") if p.suffix.lower() in {".dll",".pyd",".exe"}]
    shipped={p.name.lower() for p in binaries}
    system=Path(os.environ["SystemRoot"])/"System32"
    missing={}
    for path in binaries:
        absent=[n for n in imports(path) if n not in shipped and not n.startswith(("api-ms-","ext-ms-")) and not (system/n).exists()]
        if absent:missing[str(path.relative_to(stage))]=absent
    if missing:raise RuntimeError("Missing native dependencies: "+json.dumps(missing))
    destination=ROOT/"builds/delivery/CorvetteLMPC-Portable-Windows-x64.zip"
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix(".zip.partial")
    with ZipFile(temporary,"w",ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():archive.write(path,Path(stage.name)/path.relative_to(stage))
    temporary.replace(destination)
    result={"zip":str(destination),"staging":str(stage),"bytes":destination.stat().st_size,
        "files":len(manifest["files"])+1,"identity":identity,"dependencies":manifest["dependencies"],"native_dependency_scan":"passed"}
    (ROOT/"artifacts/portable-package.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    return destination


if __name__=="__main__":build()
