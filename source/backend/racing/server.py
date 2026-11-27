"""Protocol 1: newline-delimited JSON over localhost TCP; no remote listener."""
import argparse
import json
import select
import socket
import time
import os
import sys
from pathlib import Path
from .session import Session
from . import spec


def points(values):
    return [{"x": float(v[0]), "y": float(v[1]), "yaw": float(v[2])} for v in values]


def ghost_message(session):
    ghosts = session.ghosts()
    for ghost in ghosts:
        ghost["poses"] = points(ghost["poses"])
    return {"type": "ghosts", "protocol": 1, "ghosts": ghosts}


def send(client, document):
    payload = (json.dumps(document, separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")
    client.sendall(payload)


def serve(port=8765, directory="recordings/racing-v3/live", track="l_track", terminal_mode=spec.DEFAULT_PROFILE):
    session = Session(track=track, directory=directory, terminal_mode=terminal_mode)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(1)
        root=Path(__file__).resolve().parents[2]
        (root/".cache").mkdir(exist_ok=True)
        (root/".cache"/f"backend-{port}.json").write_text(json.dumps({"pid":os.getpid(),"port":port,"root":str(root),"executable":sys.executable,
            "terminal_mode":terminal_mode,"algorithm_revision":session.learn.repository.config["algorithm_revision"],"identity":session.learn.identity}),encoding="utf-8")
        print(f"Racing protocol 1 listening on 127.0.0.1:{port}", flush=True)
        while True:
            client, _ = listener.accept()
            with client:
                client.settimeout(2)
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                buffer = b""
                revision = -1
                deadline = time.perf_counter()
                last_tick = deadline
                try:
                    send(client, {"type": "hello", "protocol": 1, "track": session.learn.track.manifest(),
                                  "identity": session.learn.identity})
                    while True:
                        while select.select([client], [], [], 0)[0]:
                            data = client.recv(65536)
                            if not data:
                                raise ConnectionError("Viewer disconnected")
                            buffer += data
                            if len(buffer) > 1024*1024:
                                raise ValueError("Command exceeds protocol limit")
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                try:
                                    document = json.loads(line)
                                    if document.get("protocol") != 1:
                                        raise ValueError("Unsupported protocol version")
                                    if document.get("command") == "shutdown":
                                        return
                                    if document.get("command") == "demo":
                                        from .session import Run
                                        identity=Run(terminal_mode=spec.DEFAULT_PROFILE).identity
                                        session.load_external_replay(root/"recordings"/"racing-v3"/"validated"/spec.DEFAULT_PROFILE/identity[:12]/"seed-0")
                                    elif document.get("command") == "legacy_demo":
                                        session.load_external_replay(root/"recordings"/"validated"/"seed-0")
                                    else:
                                        session.command(document)
                                    session.message = "" if document.get("command") != "save" else session.message
                                except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
                                    session.message = str(error)
                        now = time.perf_counter()
                        if now >= deadline:
                            speed = 1 if session.mode == "drive" else session.speed
                            session.step()
                            frame = session.frame()
                            frame["prediction"] = points(frame["prediction"])
                            frame["safe_samples"] = points(frame["safe_samples"])
                            frame["wall_step_ms"] = (time.perf_counter()-now)*1000
                            frame["slowdown"] = max(1.0, (time.perf_counter()-last_tick)/(0.1/speed))
                            last_tick = now
                            if revision != session.revision:
                                send(client, ghost_message(session))
                                revision = session.revision
                            send(client, frame)
                            # Never drop or enlarge physics steps to catch up with rendering.
                            deadline = max(deadline+0.1/speed, time.perf_counter())
                        time.sleep(0.001)
                except (OSError, ConnectionError, ValueError) as error:
                    session.command({"command": "pause", "value": True})
                    session.control[:] = 0
                    print(f"Viewer connection ended: {error}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--recordings", default="recordings/racing-v3/live")
    parser.add_argument("--terminal-mode", choices=spec.PROFILES, default=spec.DEFAULT_PROFILE)
    parser.add_argument("--track", choices=["l_track", "oval"], default="l_track")
    args = parser.parse_args()
    serve(args.port, args.recordings, args.track, args.terminal_mode)


if __name__ == "__main__":
    main()
