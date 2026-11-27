using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

namespace CorvetteLab
{
    [Serializable] public class Point { public float x, y, yaw; }
    [Serializable] public class RoadPoint { public float s, x, y, heading, curvature; }
    [Serializable] public class TrackInfo { public string name; public float width, length; public RoadPoint[] samples; }
    [Serializable] public class LapInfo { public int number; public string kind, reason; public float seconds; public bool valid; }
    [Serializable] public class GhostInfo : LapInfo { public string label; public float dt; public Point[] poses; public float[] speeds; }
    [Serializable] public class SolverInfo { public string status, terminal_mode; public float milliseconds, terminal_slack, terminal_residual, tire_range_slack, residual; public int iterations, horizon, terminal_samples; public bool over_budget; }
    [Serializable] public class Message
    {
        public string type, identity, phase, mode, failure, message, controller_profile, algorithm_revision;
        public int protocol, sequence, lap, revision;
        public float time, elapsed, speed, slowdown, wall_step_ms, replay_duration;
        public bool paused;
        public float[] pose, state, control;
        public Point[] prediction, safe_samples;
        public TrackInfo track;
        public SolverInfo solver;
        public LapInfo[] history, learning_history;
        public GhostInfo[] ghosts;
    }

    public sealed class Wire : IDisposable
    {
        public struct Packet { public string Json;public double Arrival; }
        public static double Now=> (double)System.Diagnostics.Stopwatch.GetTimestamp()/System.Diagnostics.Stopwatch.Frequency;
        public readonly ConcurrentQueue<Packet> Incoming = new ConcurrentQueue<Packet>();
        public volatile bool Connected;
        public string Status = "Connecting to local simulation...";
        readonly ConcurrentQueue<string> outgoing = new ConcurrentQueue<string>();
        volatile bool running = true;
        TcpClient client;
        readonly Thread thread;
        public Wire()
        {
            thread = new Thread(Loop) { IsBackground = true, Name = "Racing localhost bridge" };
            thread.Start();
        }
        public void Command(string command, string arguments = "")
        {
            if (Connected) outgoing.Enqueue("{\"protocol\":1,\"command\":\"" + command + "\"" + arguments + "}");
        }
        void Loop()
        {
            while (running)
            {
                try
                {
                    using (client = new TcpClient())
                    {
                        client.NoDelay = true;
                        var pending = client.BeginConnect("127.0.0.1", 8765, null, null);
                        if (!pending.AsyncWaitHandle.WaitOne(1500)) throw new IOException("Local server is not running");
                        client.EndConnect(pending);
                        var stream = client.GetStream();
                        stream.ReadTimeout = 3000;
                        var writer = new StreamWriter(stream) { AutoFlush = true, NewLine = "\n" };
                        Connected = true; Status = "Connected";
                        // Read on a separate thread so telemetry reception never delays keyboard commands.
                        var receiver = new Thread(() =>
                        {
                            try
                            {
                                using (var reader = new StreamReader(stream))
                                    while (running && Connected)
                                    {
                                        string line = reader.ReadLine();
                                        if (line == null) break;
                                        Incoming.Enqueue(new Packet{Json=line,Arrival=Now});
                                    }
                            }
                            catch (Exception) { }
                            finally { Connected = false; }
                        }) { IsBackground = true };
                        receiver.Start();
                        while (running && Connected)
                        {
                            while (outgoing.TryDequeue(out string line)) writer.WriteLine(line);
                            Thread.Sleep(5);
                        }
                        client.Close(); receiver.Join(500);
                    }
                }
                catch (Exception error) { Status = error.Message; }
                Connected = false;
                while (outgoing.TryDequeue(out _)) { }
                if (running) Thread.Sleep(1000);
            }
        }
        public void Dispose() { running = false; Connected = false; client?.Close(); thread.Join(1000); }
    }
}
