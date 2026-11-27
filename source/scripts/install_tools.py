"""Install official Unity binaries locally; verify release-feed checksums."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
CACHE = ROOT / ".cache" / "downloads"


def dismiss_dependency_report(process, editor_path):
    """Dismiss only this installer's optional offer to open its saved report."""
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def window_callback(window,unused):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(window,ctypes.byref(owner))
        if owner.value!=process.pid:return True
        texts=[]
        def child_callback(child,unused):
            buffer=ctypes.create_unicode_buffer(4096)
            user32.GetWindowTextW(child,buffer,len(buffer));texts.append(buffer.value)
            return True
        user32.EnumChildWindows(window,callback_type(child_callback),0)
        if any("Would you like to view the list now?" in text for text in texts):
            report=editor_path/"MissingDependencies"/"MissingDependencies.txt"
            if report.exists():print(report.read_text(errors="replace"),flush=True)
            user32.PostMessageW(window,0x111,7,0)  # IDNO: report has already been printed.
        return True
    user32.EnumWindows(callback_type(window_callback),0)


def run_installer(command, editor_path, environment=None):
    process=subprocess.Popen(command,cwd=ROOT,env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
    while process.poll() is None:
        dismiss_dependency_report(process,editor_path)
        time.sleep(.5)
    return process


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def download(url, destination, algorithm, expected):
    destination.parent.mkdir(parents=True, exist_ok=True)
    def digest(path):
        h = hashlib.new(algorithm)
        with path.open("rb") as source:
            for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                h.update(block)
        return h.digest()
    if destination.exists() and digest(destination) == expected:
        return
    partial = destination.with_suffix(destination.suffix + ".partial")
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as target:
        total = 0
        checkpoint = 0
        while block := response.read(4 * 1024 * 1024):
            target.write(block)
            total += len(block)
            if total - checkpoint >= 256 * 1024 * 1024:
                print(f"Downloaded {total / 1024**3:.2f} GiB", flush=True)
                checkpoint = total
    if digest(partial) != expected:
        raise RuntimeError(f"Checksum mismatch: {destination.name}")
    partial.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    lock_path = ROOT / "tools-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
    else:
        cli = get_json("https://public-cdn.cloud.unity3d.com/hub/prod/cli/latest.json")
        release = get_json("https://services.api.unity.com/unity/editor/release/v1/releases?limit=1&version=6000.3")["results"][0]
        editor = next(d for d in release["downloads"] if d["platform"] == "WINDOWS" and d["architecture"] == "X86_64")
        lock = {"unity_version": release["version"], "unity_revision": release.get("shortRevision", "96d2fe17529c"),
                "editor": {k: editor[k] for k in ["url", "integrity", "downloadSize", "installedSize"]},
                "cli_version": cli["version"], "cli": cli["binaries"]["win32-x64"],
                "reference_commit": "b49c95e7795ef6f343efacedb6b90a69c7855b32"}
        lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Pinned Unity {lock['unity_version']}, CLI {lock['cli_version']}", flush=True)
    cli = lock["cli"]
    cli_path = TOOLS / "unity-cli" / "bin" / "unity.exe"
    download(f"https://public-cdn.cloud.unity3d.com/hub/prod/cli/{lock['cli_version']}/{cli['filename']}",
             cli_path, "sha256", bytes.fromhex(cli["sha256"]))
    version = lock["unity_version"]
    editor_path = TOOLS / "unity" / version
    installer = CACHE / f"UnitySetup64-{version}.exe"
    algorithm, checksum = lock["editor"]["integrity"].split("-", 1)
    download(lock["editor"]["url"], installer, algorithm, base64.b64decode(checksum))
    if not args.download_only and not (editor_path / "Editor" / "Unity.exe").exists():
        command = f'"{installer}" /S -CPULightmapper=no /D={editor_path}'
        print("Installing Editor inside project; optional CPU lightmapper disabled", flush=True)
        try:
            result = run_installer(command,editor_path)
        except OSError as error:
            if error.winerror != 740:
                raise
            # Per-process compatibility mode runs the installer with fewer privileges.
            # It grants no rights and retains normal filesystem/registry permissions.
            # All selected components are app-local; the optional shared runtime is omitted.
            environment = os.environ.copy()
            environment["__COMPAT_LAYER"] = "RunAsInvoker"
            print("Installing with existing user permissions into the writable project", flush=True)
            result = run_installer(command,editor_path,environment)
        if result.returncode:
            raise RuntimeError(f"Unity installer exited {result.returncode}")
    if not args.download_only:
        if not (editor_path / "Editor" / "Unity.exe").exists():
            raise RuntimeError("Installer did not produce the configured Editor executable")
        print(f"Editor ready: {editor_path / 'Editor' / 'Unity.exe'}", flush=True)
        clients = list(editor_path.rglob("Unity.Licensing.Client.exe"))
        print("Local licensing clients: " + str([str(p) for p in clients]), flush=True)
        subprocess.run([str(cli_path), "--version"], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
