using System;
using System.IO;
using UnityEngine;
using CorvetteLab;

public static class PresentationChecks
{
    static void Require(bool test,string message){if(!test)throw new Exception("Keyboard steering: "+message);}
    public static void Run()
    {
        float current=0;
        for(int i=0;i<7;i++)current=KeyboardSteering.Step(current,1,0,1/60f);
        Require(Mathf.Abs(current-.45f)<.0001f,"full low-speed lock within 117 ms");
        for(int i=0;i<4;i++)current=KeyboardSteering.Step(current,0,0,1/60f);
        Require(current==0,"release recenters within 67 ms");
        current=.45f;
        for(int i=0;i<11;i++)current=KeyboardSteering.Step(current,-1,0,1/60f);
        Require(current==-.45f,"opposite lock within 184 ms");
        Require(KeyboardSteering.Limit(25)<.1f,"reduced highway-speed sensitivity");
        Require(KeyboardSteering.Limit(0)==.45f,"retains parking steering range");
        Require(KeyboardSteering.Limit(-25)==KeyboardSteering.Limit(25),"symmetric speed response");
        float at30=0,at144=0;
        for(int i=0;i<3;i++)at30=KeyboardSteering.Step(at30,1,8,1/30f);
        for(int i=0;i<14;i++)at144=KeyboardSteering.Step(at144,1,8,1/144f);
        Require(Mathf.Abs(at30-at144)<.0001f,"frame-rate independent full-lock response");
        Require(KeyboardSteering.Step(.2f,0,0,0)==.2f,"zero delta holds input");
        string root=Directory.GetParent(Application.dataPath).Parent.FullName;
        File.WriteAllText(Path.Combine(root,"artifacts","keyboard-steering-checks.json"),"{\"passed\":8,\"low_speed_full_lock_ms\":116.67,\"release_ms\":66.67,\"opposite_lock_ms\":183.34,\"scope\":\"Unity keyboard mapping only\"}");
        Debug.Log("Keyboard steering checks: 8 passed; MPC backend unchanged.");
        MotionChecks.Run();
    }
}
