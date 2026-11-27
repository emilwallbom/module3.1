"""The single-client simulation must never receive a second launched viewer."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import launch

pytestmark=pytest.mark.skipif(os.name!="nt",reason="Windows viewer lifecycle")


def test_viewer_lease_excludes_another_process_and_releases(tmp_path,monkeypatch):
    monkeypatch.setattr(launch,"ROOT",tmp_path)
    script="import sys;from pathlib import Path;import launch;launch.ROOT=Path(sys.argv[1]);\nwith launch.ViewerLease() as lease: print(int(lease.acquired))"
    def other_process():
        return subprocess.check_output([sys.executable,"-c",script,str(tmp_path)],cwd=Path(launch.__file__).parent,
            creationflags=launch.HIDDEN,text=True).strip()
    with launch.ViewerLease() as first:
        assert first.acquired
        assert other_process()=="0"
    assert other_process()=="1"
    # An exited owner leaves no persistent lock file or stale mutex ownership.
    with launch.ViewerLease() as after_exit:assert after_exit.acquired


def test_duplicate_launch_only_focuses_existing_window(monkeypatch):
    class BusyLease:
        acquired=False
        def __enter__(self):return self
        def __exit__(self,*args):pass
    focused=[]
    monkeypatch.setattr(launch,"ViewerLease",BusyLease)
    monkeypatch.setattr(launch,"focus_existing_viewer",lambda:focused.append(True))
    def forbidden(*args,**kwargs):pytest.fail("Duplicate launch must not start a backend or player")
    monkeypatch.setattr(launch,"start_backend",forbidden)
    monkeypatch.setattr(launch.subprocess,"Popen",forbidden)
    monkeypatch.setattr(sys,"argv",["launch.py","play"])
    launch.main()
    assert focused==[True]


def test_viewer_record_pid_validation_uses_real_executable():
    assert launch.process_image(os.getpid()) is not None
    assert launch.process_image(0) is None
