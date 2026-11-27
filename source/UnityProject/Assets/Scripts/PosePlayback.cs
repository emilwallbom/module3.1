using System;
using System.Collections.Generic;
using UnityEngine;

namespace CorvetteLab
{
    // Read-only render timeline. Nothing here feeds back into simulation or controls.
    public sealed class PosePlayback
    {
        public struct Sample
        {
            public double Time, Arrival;
            public Vector3 Position, Velocity;
            public float Heading, YawRate, Speed, Steer, Elapsed;
            public int Lap;
        }
        readonly List<Sample> samples=new List<Sample>(32);
        Message previous;
        double playhead,rate=1,lastWall,source;
        bool initialized;
        public int BufferedSamples=>samples.Count;
        public float PresentationLag { get; private set; }
        public void Clear(){samples.Clear();previous=null;initialized=false;}
        public void Push(Message message,double arrival)
        {
            if(message.pose==null||message.pose.Length<3)return;
            bool replay=message.mode=="replay";
            double stamp=replay?message.elapsed:message.time;
            bool reset=previous==null||previous.mode!=message.mode||message.sequence<previous.sequence||previous.paused!=message.paused;
            if(!reset&&replay)
            {
                double change=message.elapsed-previous.elapsed;
                if(change<0&&previous.elapsed>message.replay_duration-.35f&&message.elapsed<.35f&&message.lap==previous.lap)
                    change+=message.replay_duration;
                else if(change<-.001||change>.35||message.lap!=previous.lap)reset=true;
                stamp=source+change;
            }
            if(!reset&&samples.Count>0)
            {
                var last=samples[samples.Count-1];
                var position=new Vector3(message.pose[0],.02f,message.pose[1]);
                if(stamp<last.Time-.001||Vector3.Distance(position,last.Position)>Mathf.Max(5,(float)(stamp-last.Time)*60+1))reset=true;
            }
            if(reset)
            {
                samples.Clear();initialized=false;stamp=replay?message.elapsed:message.time;
                rate=Math.Max(.05,message.speed/Math.Max(1,message.slowdown));
            }
            source=stamp;previous=message;
            float heading=message.pose[2],vx=message.state!=null?message.state[0]:0,vy=message.state!=null?message.state[1]:0;
            var sample=new Sample{Time=stamp,Arrival=arrival,Position=new Vector3(message.pose[0],.02f,message.pose[1]),
                Velocity=new Vector3(vx*Mathf.Cos(heading)-vy*Mathf.Sin(heading),0,vx*Mathf.Sin(heading)+vy*Mathf.Cos(heading)),
                Heading=heading,YawRate=message.state!=null?message.state[2]:0,Speed=vx,Steer=message.control!=null?message.control[0]:0,
                Elapsed=message.elapsed,Lap=message.lap};
            if(samples.Count>0&&Math.Abs(stamp-samples[samples.Count-1].Time)<.00001)
            {
                // Pause/disconnect holds the authoritative pose, rather than coasting forever.
                samples[samples.Count-1]=sample;
                if(message.paused||!string.IsNullOrEmpty(message.failure)){playhead=stamp;initialized=false;}
                return;
            }
            samples.Add(sample);if(samples.Count>32)samples.RemoveAt(0);
        }
        public Sample Evaluate(double now,bool connected)
        {
            if(samples.Count==0)return default;
            var latest=samples[samples.Count-1];
            if(samples.Count<2||previous.paused||!string.IsNullOrEmpty(previous.failure))
            {lastWall=now;playhead=latest.Time;PresentationLag=0;return latest;}
            // Estimate actual simulation pace over several packets; rendering never assumes requested 8x was achieved.
            int first=samples.Count-1;
            while(first>0&&latest.Arrival-samples[first].Arrival<.5)first--;
            double span=latest.Arrival-samples[first].Arrival;
            double measured=span>.005?(latest.Time-samples[first].Time)/span:rate;
            double dt=initialized?Math.Max(0,Math.Min(.25,now-lastWall)):0;lastWall=now;
            rate+= (Math.Max(.02,Math.Min(12,measured))-rate)*(1-Math.Exp(-dt*3));
            // 120 ms of wall-time buffering: one telemetry interval plus modest scheduling jitter.
            double desired=latest.Time+(now-latest.Arrival)*rate-.12*rate;
            if(!initialized){playhead=Math.Max(samples[0].Time,latest.Time-.12*rate);initialized=true;}
            else
            {
                double correction=Math.Max(-rate*.30,Math.Min(rate*.30,(desired-(playhead+dt*rate))*3));
                playhead+=dt*Math.Max(0,rate+correction);
            }
            playhead=Math.Max(samples[0].Time,Math.Min(latest.Time,playhead));
            // A stale connection can only consume buffered poses, never invent future travel.
            if(!connected)playhead=Math.Min(playhead,latest.Time);
            PresentationLag=(float)Math.Max(0,latest.Time-playhead);
            for(int i=1;i<samples.Count;i++)if(samples[i].Time>=playhead)
                return Interpolate(samples[i-1],samples[i],playhead,previous.replay_duration,previous.mode=="replay");
            return latest;
        }
        public static Vector3 Hermite(Vector3 a,Vector3 b,Vector3 va,Vector3 vb,float seconds,float t)
        {
            float t2=t*t,t3=t2*t;
            return (2*t3-3*t2+1)*a+(t3-2*t2+t)*seconds*va+(-2*t3+3*t2)*b+(t3-t2)*seconds*vb;
        }
        public static Sample Interpolate(Sample a,Sample b,double time,float duration=0,bool replay=false)
        {
            float seconds=(float)(b.Time-a.Time),t=seconds>0?Mathf.Clamp01((float)(time-a.Time)/seconds):1;
            var result=b;result.Time=time;
            result.Position=Hermite(a.Position,b.Position,a.Velocity,b.Velocity,seconds,t);
            float headingEnd=a.Heading+Mathf.DeltaAngle(a.Heading*Mathf.Rad2Deg,b.Heading*Mathf.Rad2Deg)*Mathf.Deg2Rad;
            result.Heading=Hermite(new Vector3(a.Heading,0,0),new Vector3(headingEnd,0,0),new Vector3(a.YawRate,0,0),new Vector3(b.YawRate,0,0),seconds,t).x;
            result.Speed=Mathf.Lerp(a.Speed,b.Speed,t);result.Steer=Mathf.Lerp(a.Steer,b.Steer,t);
            if(replay&&duration>0)
            {
                float end=b.Elapsed;if(end<a.Elapsed)end+=duration;
                result.Elapsed=Mathf.Repeat(Mathf.Lerp(a.Elapsed,end,t),duration);
            }
            else result.Elapsed=a.Lap==b.Lap?Mathf.Lerp(a.Elapsed,b.Elapsed,t):(t<1?a.Elapsed+(float)(time-a.Time):b.Elapsed);
            return result;
        }
    }
}
