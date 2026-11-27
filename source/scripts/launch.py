"""Windows entry points. Helper processes stay local and are hidden."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from racing import spec
from racing.session import Run

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
LOCK=json.loads((ROOT/"tools-lock.json").read_text())
EDITOR=ROOT/".tools"/"unity"/LOCK["unity_version"]/"Editor"
CLI=ROOT/".tools"/"unity-cli"/"bin"/"unity.exe"
ENV=os.environ.copy()
ENV.update({"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","UPM_CACHE_ROOT":str(ROOT/".cache"/"upm"),
            "UNITY_GI_CACHE_PATH":str(ROOT/".cache"/"gi"),"UNITY_NO_AGENT_HINTS":"1"})
ENV["PATH"]=str(EDITOR/"Data"/"Resources"/"Licensing"/"Client")+os.pathsep+ENV.get("PATH","")
HIDDEN=getattr(subprocess,"CREATE_NO_WINDOW",0)
VIEWER_RECORD=ROOT/".cache"/"viewer.json"


class ViewerLease:
    """One interactive viewer per workspace; lifetime follows the launcher process."""
    def __init__(self):
        self.handle=None
        self.acquired=False

    def __enter__(self):
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype=wintypes.HANDLE
        key=hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:20]
        self.handle=kernel.CreateMutexW(None,False,"Local\\CorvetteLMPC.Viewer."+key)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        self.acquired=ctypes.get_last_error()!=183  # ERROR_ALREADY_EXISTS
        return self

    def __exit__(self,*ignored):
        if self.handle:
            kernel=ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            kernel.CloseHandle(self.handle)
            self.handle=None


def process_image(pid):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:return None
    try:
        size=wintypes.DWORD(32768);buffer=ctypes.create_unicode_buffer(size.value)
        if kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):
            return Path(buffer.value).resolve()
        return None
    finally:kernel.CloseHandle(handle)


def focus_existing_viewer():
    """Use window APIs, never a TCP probe that would occupy the simulation listener."""
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        try:
            record=json.loads(VIEWER_RECORD.read_text(encoding="utf-8"))
            executable=Path(record["executable"]).resolve()
            if (Path(record["root"]).resolve()!=ROOT or
                executable not in {(ROOT/"builds"/"CorvetteLMPC"/"CorvetteLMPC.exe").resolve(),(EDITOR/"Unity.exe").resolve()} or
                process_image(record["pid"])!=executable):
                time.sleep(.1);continue
            user=ctypes.WinDLL("user32",use_last_error=True)
            callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
            user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            user.IsWindowVisible.argtypes=[wintypes.HWND]
            user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
            user.SetForegroundWindow.argtypes=[wintypes.HWND]
            windows=[]
            @callback_type
            def visit(hwnd,unused):
                pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                if pid.value==record["pid"] and user.IsWindowVisible(hwnd):windows.append(hwnd)
                return True
            user.EnumWindows(visit,0)
            if windows:
                user.ShowWindow(windows[0],9);user.SetForegroundWindow(windows[0])
                print("Simulator already running; brought its existing window forward. Use LEARN / DRIVE / REPLAY there.")
                return record
        except (OSError,ValueError,KeyError,TypeError):pass
        time.sleep(.1)
    raise RuntimeError("The simulator is already starting or running. Wait for its existing window; no second viewer was opened.")


def alive(pid):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x100000,False,int(pid))
    if not handle:return False
    try:return kernel.WaitForSingleObject(handle,0)==258
    finally:kernel.CloseHandle(handle)


def existing_backend():
    path=ROOT/".cache"/"backend-8765.json"
    if not path.exists():return False
    try:
        info=json.loads(path.read_text(encoding="utf-8"))
        return Path(info["root"]).resolve()==ROOT and alive(info["pid"])
    except (OSError,ValueError,KeyError):return False


def start_backend(terminal_mode=spec.DEFAULT_PROFILE):
    identity=Run(terminal_mode=terminal_mode).identity
    if existing_backend():
        info=json.loads((ROOT/".cache"/"backend-8765.json").read_text())
        if info.get("identity")!=identity:
            raise RuntimeError("A different controller backend is running. Close its simulator before launching this profile.")
        return None
    (ROOT/"artifacts").mkdir(exist_ok=True)
    stream=(ROOT/"artifacts"/"server.log").open("a",encoding="utf-8")
    child=subprocess.Popen([sys.executable,"-m","racing.server","--terminal-mode",terminal_mode,
                            "--recordings",str(ROOT/"recordings"/"racing-v3"/"live"/terminal_mode/identity[:12])],
                           cwd=ROOT,env=ENV,stdout=stream,stderr=stream,creationflags=HIDDEN)
    for _ in range(100):
        if existing_backend():return child
        if child.poll() is not None:raise RuntimeError("Backend failed to start. See artifacts/server.log")
        time.sleep(.05)
    raise RuntimeError("Backend startup timed out. See artifacts/server.log")


def stop_backend():
    try:
        with socket.create_connection(("127.0.0.1",8765),timeout=5) as connection:
            reader=connection.makefile("r")
            reader.readline()
            connection.sendall(b'{"protocol":1,"command":"shutdown"}\n')
            while reader.readline():pass
    except OSError:pass


def activate():
    if subprocess.run([str(CLI),"license","status","--json"],env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        print("Unity license is already active.")
    else:
        subprocess.run([str(CLI),"auth","login"],env=ENV,check=True)
        print("Unity Editor Software Terms: https://unity.com/legal/editor-terms-of-service/software")
        if input("If you accept the Unity Personal terms, type ACCEPT: ").strip()!="ACCEPT":
            raise RuntimeError("License terms were not accepted; activation left unchanged")
        subprocess.run([str(CLI),"license","activate","--personal","--accept-eula"],env=ENV,check=True)
    subprocess.run([str(CLI),"editors","add",str(EDITOR/"Unity.exe")],env=ENV,check=True)
    if input("Accept this Editor's Software Terms as well? Type ACCEPT: ").strip()=="ACCEPT":
        subprocess.run([str(CLI),"terms","accept",LOCK["unity_version"],"--yes"],env=ENV,check=True)


def build():
    from repair_urp_metadata import repair
    repair()
    (ROOT/"artifacts").mkdir(exist_ok=True)
    subprocess.run([str(EDITOR/"Unity.com"),"-batchmode","-nographics","-quit","-projectPath",str(ROOT/"UnityProject"),
                    "-executeMethod","ProjectBuilder.Build","-logFile",str(ROOT/"artifacts"/"unity-build.log")],env=ENV,check=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["play","editor","backend","activate","build"])
    parser.add_argument("--demo",action="store_true")
    parser.add_argument("--terminal-mode",choices=spec.PROFILES,default=spec.DEFAULT_PROFILE)
    args=parser.parse_args()
    if args.action=="activate":activate();return
    if args.action=="build":build();return
    if args.action=="backend":
        from racing.server import serve
        identity=Run(terminal_mode=args.terminal_mode).identity
        serve(directory=ROOT/"recordings"/"racing-v3"/"live"/args.terminal_mode/identity[:12],terminal_mode=args.terminal_mode);return
    if args.action=="play":
        executable=ROOT/"builds"/"CorvetteLMPC"/"CorvetteLMPC.exe"
        if not executable.exists():build()
        command=[str(executable)]+(["--demo"] if args.demo else [])
    else:
        command=[str(EDITOR/"Unity.exe"),"-projectPath",str(ROOT/"UnityProject")]
    with ViewerLease() as lease:
        if not lease.acquired:
            focus_existing_viewer();return
        backend=start_backend(args.terminal_mode)
        try:
            # The requested game/editor is interactive; only its helper stays hidden.
            process=subprocess.Popen(command,cwd=ROOT,env=ENV)
            VIEWER_RECORD.parent.mkdir(exist_ok=True)
            VIEWER_RECORD.write_text(json.dumps({"pid":process.pid,"root":str(ROOT),"executable":command[0],
                "terminal_mode":args.terminal_mode,"action":args.action}),encoding="utf-8")
            process.wait()
        finally:
            if backend is not None:
                stop_backend()
                try:backend.wait(timeout=8)
                except subprocess.TimeoutExpired:print("Backend still running; its process ID is in .cache/backend-8765.json")


if __name__=="__main__":
    try:main()
    except (RuntimeError,subprocess.CalledProcessError) as error:
        print(error,file=sys.stderr);raise SystemExit(1)
