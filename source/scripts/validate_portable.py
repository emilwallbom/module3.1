"""Validate the actual ZIP from a relocated Unicode path with isolated Python settings."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from zipfile import ZipFile
from launch import ROOT,process_image,alive


def close_viewer(pid,expected):
    if process_image(pid)!=expected.resolve():raise RuntimeError("Refusing to close an unverified process")
    user=ctypes.WinDLL("user32",use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    @callback_type
    def visit(hwnd,unused):
        owner=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:user.PostMessageW(hwnd,0x10,0,0)  # WM_CLOSE; normal application shutdown
        return True
    user.EnumWindows(visit,0)


def main():
    archive=ROOT/"builds/delivery/CorvetteLMPC-Portable-Windows-x64.zip"
    destination=ROOT/".cache"/("portable-relocation-"+uuid.uuid4().hex)/"Different folder — Ω with spaces"
    destination.mkdir(parents=True)
    with ZipFile(archive) as package:
        assert package.testzip() is None
        package.extractall(destination)
    relocated=destination/"CorvetteLMPC-Portable"
    manifest=json.loads((relocated/"portable-manifest.json").read_text())
    for relative,digest in manifest["files"].items():
        assert hashlib.sha256((relocated/relative).read_bytes()).hexdigest()==digest,relative
    assert not (relocated/".venv").exists() and not (relocated/".tools").exists()
    assert not (relocated/"UnityProject").exists()
    python=relocated/"runtime/python/python.exe"
    env=os.environ.copy()
    env.update({"PATH":str(Path(os.environ["SystemRoot"])/"System32"),"PYTHONHOME":str(destination/"NO EXTERNAL PYTHON"),
        "PYTHONPATH":str(destination/"NO EXTERNAL PACKAGES"),"PYTHONUSERBASE":str(destination/"NO USER SITE"),
        "OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1"})
    runtime=subprocess.run([str(python),"-I",str(relocated/"scripts/portable_check.py")],cwd=ROOT/".cache",env=env,
        capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    (ROOT/"artifacts/portable-runtime-check.log").write_text(runtime.stdout+runtime.stderr,encoding="utf-8")
    if runtime.returncode:raise RuntimeError(f"Relocated runtime check failed (exit 0x{runtime.returncode & 0xffffffff:08x}); see artifacts/portable-runtime-check.log")
    runtime_result=json.loads(runtime.stdout)
    print("Relocated Python, native solvers and 50 real MPC steps passed.",flush=True)
    # Use the shipped validator: it launches the shipped player/backend, measures all cameras and exits itself.
    visual=subprocess.run([str(python),"-I",str(relocated/"scripts/visual_check.py")],cwd=ROOT/".cache",env=env,
        capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=150,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    (ROOT/"artifacts/portable-visual-check.log").write_text(visual.stdout+visual.stderr,encoding="utf-8")
    if visual.returncode:raise RuntimeError("Relocated graphical check failed; see artifacts/portable-visual-check.log")
    performance=json.loads((relocated/"artifacts/performance.json").read_text())
    assert performance["rendered_cars"]==4 and performance["comparison_fps"]>=30
    print("Relocated Unity player, replay, cameras and manual exercise passed.",flush=True)
    # Execute the exact recipient launcher from an unrelated working directory.
    command=[os.environ["COMSPEC"],"/d","/c",str(relocated/"Run Simulator.cmd")]
    stream=(ROOT/"artifacts/portable-launcher-check.log").open("w",encoding="utf-8")
    first=subprocess.Popen(command,cwd=ROOT/".cache",env=env,stdout=stream,stderr=stream,
        stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    record=None
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                candidate=json.loads((relocated/".cache/viewer.json").read_text())
                if (candidate.get("action")=="play" and
                    process_image(candidate["pid"])==(relocated/"builds/CorvetteLMPC/CorvetteLMPC.exe").resolve()):
                    record=candidate;break
            except (OSError,ValueError):pass
            if first.poll() is not None:raise RuntimeError("Run Simulator.cmd exited before starting its player")
            time.sleep(.1)
        if record is None:raise RuntimeError("Recipient launcher did not start a verified local player")
        duplicate=subprocess.run(command,cwd=ROOT/".cache",env=env,capture_output=True,text=True,errors="replace",
            stdin=subprocess.DEVNULL,timeout=20,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        assert duplicate.returncode==0 and "already running" in duplicate.stdout
        assert json.loads((relocated/".cache/viewer.json").read_text())["pid"]==record["pid"]
        server=json.loads((relocated/".cache/backend-8765.json").read_text())
        assert Path(server["root"]).resolve()==relocated.resolve() and alive(server["pid"])
    finally:
        if record is not None:close_viewer(record["pid"],relocated/"builds/CorvetteLMPC/CorvetteLMPC.exe")
        first.wait(timeout=20);stream.close()
    deadline=time.monotonic()+8
    while alive(server["pid"]) and time.monotonic()<deadline:time.sleep(.1)
    assert not alive(server["pid"]),"Backend did not stop after viewer closed"
    result={"passed":True,"zip":str(archive),"zip_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
        "zip_bytes":archive.stat().st_size,"relocated_root":str(relocated),"manifest_files_verified":len(manifest["files"]),
        "no_external_python_paths":True,"poisoned_python_environment":True,"minimal_path":True,
        "runtime":runtime_result,"graphical":performance,"recipient_cmd_launch":True,"duplicate_launch_focus":True,
        "backend_stopped_on_exit":True,"separate_clean_pc_tested":False}
    (ROOT/"artifacts/portable-validation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("runtime","graphical")},indent=2),flush=True)


if __name__=="__main__":main()
