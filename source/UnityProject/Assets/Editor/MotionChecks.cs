using System;
using System.IO;
using UnityEngine;
using CorvetteLab;

public static class MotionChecks
{
    static void Require(bool condition,string message){if(!condition)throw new Exception("Render motion: "+message);}
    static Message Frame(float time,float elapsed=-1,string mode="drive")
    {
        return new Message{mode=mode,time=time,elapsed=elapsed<0?time:elapsed,pose=new[]{time*10,0f,0f},state=new[]{10f,0f,0f,0f,0f,0f},
            control=new[]{0f,0f},speed=1,slowdown=1,lap=1,sequence=(int)Math.Round(time*10),replay_duration=2};
    }
    public static void Run()
    {
        var timeline=new PosePlayback();int next=0;float last=0,min=float.MaxValue,max=0;double squared=0;int count=0;
        for(int frame=0;frame<360;frame++)
        {
            double now=frame/60.0;
            while(next<60)
            {
                double jitter=next%3==0?.008:next%3==1?-.006:.003;
                double arrival=next*.1+jitter;
                if(arrival>now)break;
                timeline.Push(Frame(next*.1f),arrival);next++;
            }
            var sample=timeline.Evaluate(now,true);
            if(frame>60)
            {
                float delta=sample.Position.x-last;min=Mathf.Min(min,delta);max=Mathf.Max(max,delta);
                squared+=(delta-10/60f)*(delta-10/60f);count++;
            }
            last=sample.Position.x;
        }
        Require(min>.10f&&max<.24f,"10 Hz packets with jitter must produce continuous 60 Hz motion");
        var held=timeline.Evaluate(100,false);var still=timeline.Evaluate(101,false);
        Require(Vector3.Distance(held.Position,still.Position)<.0001f,"disconnect must stop at last authoritative pose");
        var paused=Frame(6);paused.paused=true;timeline.Push(paused,101.1);
        Require(Mathf.Abs(timeline.Evaluate(101.2,true).Position.x-60)<.0001f,"pause holds authoritative pose");
        timeline.Clear();Require(timeline.BufferedSamples==0,"reset clears stale timeline");
        var a=new PosePlayback.Sample{Time=0,Position=Vector3.zero,Velocity=Vector3.right*10,Heading=179*Mathf.Deg2Rad,Elapsed=1.9f,Lap=1};
        var b=new PosePlayback.Sample{Time=.1,Position=Vector3.right,Velocity=Vector3.right*10,Heading=-179*Mathf.Deg2Rad,Elapsed=0,Lap=1};
        var half=PosePlayback.Interpolate(a,b,.05,2,true);
        Require(Mathf.Abs(half.Position.x-.5f)<.0001f,"interpolation follows exact constant-velocity midpoint");
        Require(Mathf.Abs(Mathf.Abs(half.Heading*Mathf.Rad2Deg)-180)<.01f,"heading uses short arc across pi");
        Require(Mathf.Abs(half.Elapsed-1.95f)<.0001f,"replay finish keeps ghost clock continuous");
        var mode=Frame(0,0,"learn");timeline.Push(mode,102);
        Require(timeline.Evaluate(102,true).Position==new Vector3(0,.02f,0),"mode switch cannot interpolate through old driving session");
        timeline.Clear();var replayA=Frame(0,1.9f,"replay");replayA.sequence=1;timeline.Push(replayA,0);
        var replayB=Frame(.1f,0,"replay");replayB.sequence=1;timeline.Push(replayB,.1);
        Require(timeline.BufferedSamples==2,"natural replay loop keeps both interpolation samples");
        var seek=Frame(.2f,1,"replay");seek.sequence=1;timeline.Push(seek,.2);
        Require(timeline.BufferedSamples==1,"replay seek resets rather than flying between positions");
        timeline.Clear();int packet=0;double latest=0;PosePlayback.Sample accelerated=default;
        for(int frameIndex=0;frameIndex<=360;frameIndex++)
        {
            double now=frameIndex/60.0;
            while(packet<170)
            {
                double arrival=packet<=10?packet*.1:1+(packet-10)*.1/3;
                if(arrival>now)break;
                var fast=Frame(packet*.1f);fast.speed=packet<=10?1:3;
                timeline.Push(fast,arrival);latest=packet*.1;packet++;
            }
            accelerated=timeline.Evaluate(now,true);
        }
        Require(latest-accelerated.Time<.6,"render clock catches up after training pace changes");
        string root=Directory.GetParent(Application.dataPath).Parent.FullName;
        File.WriteAllText(Path.Combine(root,"artifacts","motion-checks.json"),"{\"passed\":11,\"input_hz\":10,\"render_hz\":60,\"packet_jitter_ms\":14,\"min_frame_travel_m\":"+min.ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"max_frame_travel_m\":"+max.ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"rms_frame_travel_error_m\":"+Math.Sqrt(squared/count).ToString(System.Globalization.CultureInfo.InvariantCulture)+"}");
        Debug.Log("Render motion checks: 11 passed; jittered 10 Hz data rendered continuously at 60 Hz.");
    }
}
