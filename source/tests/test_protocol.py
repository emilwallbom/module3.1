import json
import os
import socket
import subprocess
import sys
import time


def test_real_tcp_commands_disconnect_and_reconnect(tmp_path):
    # Bind an available local port, then give it to the isolated test server.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0));port=probe.getsockname()[1]
    process=subprocess.Popen([sys.executable,"-m","racing.server","--port",str(port),"--recordings",str(tmp_path)],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    def connect():
        deadline=time.monotonic()+8
        while True:
            try:return socket.create_connection(("127.0.0.1",port),timeout=2)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.05)
    def next_frame(reader):
        for _ in range(20):
            document=json.loads(reader.readline())
            if document["type"]=="frame":return document
        raise AssertionError("No telemetry frame received")
    try:
        with connect() as client:
            reader=client.makefile("r")
            hello=json.loads(reader.readline())
            assert hello["protocol"]==1 and hello["track"]["length"]>380
            client.sendall(b'{"protocol":1,"command":"mode","value":"drive"}\n')
            for _ in range(10):
                frame=next_frame(reader)
                if frame["mode"]=="drive":break
            assert frame["mode"]=="drive"
            client.sendall(b'{"protocol":99,"command":"pause"}\n')
            for _ in range(10):
                frame=next_frame(reader)
                if frame["message"]:break
            assert "Unsupported protocol" in frame["message"]
            reader.close()
        with connect() as client:
            reader=client.makefile("r")
            assert json.loads(reader.readline())["type"]=="hello"
            frame=next_frame(reader)
            assert frame["paused"] and frame["control"]==[0.,0.]
            reader.close()
    finally:
        try:
            with connect() as client:
                reader=client.makefile("r")
                reader.readline()
                client.sendall(b'{"protocol":1,"command":"shutdown"}\n')
                while reader.readline():pass
                reader.close()
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.terminate();process.wait(timeout=5)
