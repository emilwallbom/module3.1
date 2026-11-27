"""Capture the player and accept only a completed smoke run of the current build."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import uuid
from launch import ROOT,ENV,start_backend,stop_backend,ViewerLease,VIEWER_RECORD
from racing import spec


def main():
    output=ROOT/".cache"/("visual-check-"+uuid.uuid4().hex)
    output.mkdir(parents=True)
    executable=ROOT/"builds"/"CorvetteLMPC"/"CorvetteLMPC.exe"
    with ViewerLease() as lease:
        if not lease.acquired:
            raise RuntimeError("An interactive simulator is already running. Visual validation requires its own viewer.")
        backend=start_backend()
        try:
            process=subprocess.Popen([str(executable),"--smoke","--capture-all",
                "--capture="+str(output/"simulator.png"),"--performance="+str(output/"performance.json"),
                "-logFile",str(output/"player.log")],cwd=ROOT,env=ENV)
            VIEWER_RECORD.write_text(json.dumps({"pid":process.pid,"root":str(ROOT),"executable":str(executable),
                "terminal_mode":spec.DEFAULT_PROFILE,"action":"visual-check"}),encoding="utf-8")
            code=process.wait()
            if code:raise RuntimeError(f"Player exited with {code}; see {output/'player.log'}")
            report=output/"performance.json"
            if not report.exists():
                raise RuntimeError(f"Viewer closed before the 75-second check completed. Previous results were not replaced. Log: {output/'player.log'}")
            result=json.loads(report.read_text())
            if not (result["rendered_cars"]==4 and result["frames"]>500 and result["captured_views"]==6 and result["manual_exercise_observed"]):
                raise RuntimeError(f"Incomplete camera/performance validation: {report}")
            result["player_assembly_sha256"]=hashlib.sha256((executable.parent/"CorvetteLMPC_Data"/"Managed"/"Assembly-CSharp.dll").read_bytes()).hexdigest()
            result["validation_run"]=output.name
            report.write_text(json.dumps(result,indent=2))
            for path in output.iterdir():
                if path.is_file():shutil.copy2(path,ROOT/"artifacts"/path.name)
            print(json.dumps(result,indent=2),flush=True)
        finally:
            if backend is not None:
                stop_backend();backend.wait(timeout=8)


if __name__=="__main__":main()
