using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace CorvetteLab
{
    public sealed class RacingApp : MonoBehaviour
    {
        Wire wire;
        Message frame;
        readonly PosePlayback playback=new PosePlayback();
        PosePlayback.Sample presented;
        TrackInfo track;
        CarVisual car;
        readonly List<CarVisual> ghosts=new List<CarVisual>();
        GhostInfo[] ghostData=Array.Empty<GhostInfo>();
        Camera view;
        LineRenderer prediction;
        readonly List<GameObject> safeMarkers=new List<GameObject>();
        readonly List<LineRenderer> racingLines=new List<LineRenderer>();
        GameObject circuit;
        bool overlays, showGhosts=true, help, showHistory;
        int cameraIndex, focusIndex;
        float steering, nextControl, fps=60, orbitAngle=25, zoom=12;
        Vector2 historyScroll;
        GUIStyle label, heading, small, button, speedStyle;
        Texture2D buttonIdle,buttonHover,buttonSelected;
        Texture2D white,trackMap;
        Vector2 mapMin;float mapSpan;
        readonly Color mint=new Color(.30f,.94f,.72f);
        readonly Color[] ghostColors={new Color(.23f,.70f,1,.25f),new Color(.35f,1,.64f,.25f),new Color(1,.56f,.25f,.25f),new Color(.8f,.4f,1,.25f)};
        readonly List<float> frameTimes=new List<float>();
        int comparisonCars,motionFrames,motionHeldFrames;
        double lastDisplayTime=double.NaN;float motionMinStep=1000,motionMaxStep;string lastDisplayMode;
        float started;
        string capturePath, performancePath;
        bool captured, demoRequested, smoke, startDemo;
        bool captureAll;
        int captureStage;
        bool capturePrepared;
        bool manualExerciseObserved;
        static readonly string[] cameras={"CHASE","COCKPIT","HOOD","OVERHEAD","ORBIT"};

        void Start()
        {
            Application.targetFrameRate=60; QualitySettings.vSyncCount=0;
            Screen.SetResolution(1280,720,FullScreenMode.Windowed);
            started=Time.realtimeSinceStartup;
            foreach(string argument in Environment.GetCommandLineArgs())
            {
                if(argument.StartsWith("--capture="))capturePath=argument.Substring(10);
                if(argument.StartsWith("--performance="))performancePath=argument.Substring(14);
                if(argument=="--smoke")smoke=true;
                if(argument=="--demo")startDemo=true;
                if(argument=="--capture-all")captureAll=true;
            }
            view=Camera.main;
            if(view==null)view=new GameObject("Main Camera",typeof(Camera),typeof(AudioListener)).GetComponent<Camera>();
            view.tag="MainCamera"; view.backgroundColor=new Color(.47f,.62f,.73f);
            view.clearFlags=CameraClearFlags.SolidColor; view.nearClipPlane=.05f; view.farClipPlane=900; view.fieldOfView=65;
            view.GetUniversalAdditionalCameraData().antialiasing=AntialiasingMode.FastApproximateAntialiasing;
            VisualTheme.Lighting(view);
            car=CarVisual.Create("Corvette C4 - active",new Color(.78f,.055f,.035f));
            car.Pose(0,0,0,0,0,true);
            prediction=MakeLine("Prediction",mint,.095f);
            wire=new Wire();
        }

        LineRenderer MakeLine(string name,Color color,float width)
        {
            var line=new GameObject(name).AddComponent<LineRenderer>();
            var saved=Resources.Load<Material>("RacingLine");
            line.sharedMaterial=saved!=null?new Material(saved):new Material(Shader.Find("CorvetteLab/SpeedLine"));
            line.sharedMaterial.SetColor("_BaseColor",Color.white); line.startColor=line.endColor=color;
            line.startWidth=line.endWidth=width; line.shadowCastingMode=ShadowCastingMode.Off;
            line.receiveShadows=false; return line;
        }

        void Update()
        {
            fps=Mathf.Lerp(fps,1/Mathf.Max(Time.unscaledDeltaTime,.0001f),.05f);
            if(Time.realtimeSinceStartup-started>8&&frame!=null&&frame.mode=="replay"&&showGhosts&&ghosts.Count==3&&ghosts.TrueForAll(g=>g.gameObject.activeInHierarchy)
                &&(!captureAll||Time.realtimeSinceStartup-started<39))
            {frameTimes.Add(Time.unscaledDeltaTime*1000);comparisonCars=ghosts.Count+1;}
            int processed=0;
            while(processed++<40 && wire.Incoming.TryDequeue(out Wire.Packet packet))
            {
                try
                {
                    var message=JsonUtility.FromJson<Message>(packet.Json);
                    if(message.protocol!=1){wire.Status="Incompatible simulation protocol";continue;}
                    if(message.type=="hello")
                    {
                        if(track==null || track.name!=message.track.name){track=message.track;BuildTrack();}
                        if((smoke||startDemo)&&!demoRequested){wire.Command("demo");wire.Command("mode",",\"value\":\"replay\"");demoRequested=true;}
                    }
                    else if(message.type=="ghosts")SetGhosts(message.ghosts);
                    else if(message.type=="frame"){frame=message;playback.Push(message,packet.Arrival);}
                }
                catch(Exception error){Debug.LogWarning("Bridge packet: "+error.Message);}
            }
            if(Input.GetKeyDown(KeyCode.C))cameraIndex=(cameraIndex+1)%cameras.Length;
            if(Input.GetKeyDown(KeyCode.Tab))focusIndex=(focusIndex+1)%(ghosts.Count+1);
            if(Input.GetKeyDown(KeyCode.G))showGhosts=!showGhosts;
            if(Input.GetKeyDown(KeyCode.L))overlays=!overlays;
            if(Input.GetKeyDown(KeyCode.H)||Input.GetKeyDown(KeyCode.Escape))help=!help;
            if(Input.GetKeyDown(KeyCode.P))wire.Command("pause");
            if(Input.GetKeyDown(KeyCode.R))ResetCar();
            if(Input.GetKeyDown(KeyCode.M))wire.Command("mode",",\"value\":\""+(frame!=null&&frame.mode=="drive"?"learn":"drive")+"\"");
            float steerTarget=(Input.GetKey(KeyCode.A)||Input.GetKey(KeyCode.LeftArrow)?1:0)-(Input.GetKey(KeyCode.D)||Input.GetKey(KeyCode.RightArrow)?1:0);
            steering=KeyboardSteering.Step(steering,frame!=null&&frame.mode=="drive"?steerTarget:0,frame?.state!=null?frame.state[0]:0,Time.unscaledDeltaTime);
            float throttle=Input.GetKey(KeyCode.W)||Input.GetKey(KeyCode.UpArrow)?3:0;
            if(Input.GetKey(KeyCode.S)||Input.GetKey(KeyCode.DownArrow)||Input.GetKey(KeyCode.Space))throttle=-7;
            if(!captureAll&&frame!=null&&frame.mode=="drive"&&Time.realtimeSinceStartup>nextControl)
            {
                wire.Command("control",",\"value\":["+Number(steering)+","+Number(throttle)+"]");
                nextControl=Time.realtimeSinceStartup+.02f;
            }
            if(frame!=null&&frame.pose!=null)
            {
                presented=playback.Evaluate(Wire.Now,wire.Connected);
                double displayStep=presented.Time-lastDisplayTime;
                if(frame.mode=="replay"&&lastDisplayMode=="replay"&&!frame.paused&&Time.realtimeSinceStartup-started>8&&Time.realtimeSinceStartup-started<39&&displayStep>=0)
                {
                    motionFrames++;if(displayStep<.00001)motionHeldFrames++;
                    motionMinStep=Mathf.Min(motionMinStep,(float)displayStep);motionMaxStep=Mathf.Max(motionMaxStep,(float)displayStep);
                }
                lastDisplayTime=presented.Time;lastDisplayMode=frame.mode;
                car.Pose(presented.Position.x,presented.Position.z,presented.Heading,presented.Speed,presented.Steer);
                for(int i=0;i<ghosts.Count;i++)
                {
                    ghosts[i].gameObject.SetActive(showGhosts);
                    var data=ghostData[i];
                    if(data.poses==null||data.poses.Length<2)continue;
                    float t=Mathf.Clamp(presented.Elapsed,0,data.seconds)/data.dt;
                    int index=Mathf.Clamp((int)t,0,data.poses.Length-2); float f=Mathf.Clamp01(t-index);
                    var a=data.poses[index];var b=data.poses[index+1];
                    float velocity=data.speeds!=null&&index<data.speeds.Length?data.speeds[index]:0;
                    float yaw=a.yaw+Mathf.DeltaAngle(a.yaw*Mathf.Rad2Deg,b.yaw*Mathf.Rad2Deg)*Mathf.Deg2Rad*f;
                    var pa=new Vector3(a.x,0,a.y);var pb=new Vector3(b.x,0,b.y);
                    var before=data.poses[Mathf.Max(0,index-1)];var after=data.poses[Mathf.Min(data.poses.Length-1,index+2)];
                    var va=(pb-new Vector3(before.x,0,before.y))/(data.dt*(index>0?2:1));
                    var vb=(new Vector3(after.x,0,after.y)-pa)/(data.dt*(index+2<data.poses.Length?2:1));
                    var ghostPose=PosePlayback.Hermite(pa,pb,va,vb,data.dt,f);
                    ghosts[i].Pose(ghostPose.x,ghostPose.z,yaw,velocity,0);
                    Transform focused=focusIndex>0&&focusIndex<=ghosts.Count?ghosts[focusIndex-1].transform:car.transform;
                    bool nearCockpit=(cameraIndex==1||cameraIndex==2)&&Vector3.Distance(ghosts[i].transform.position,focused.position)<5;
                    ghosts[i].gameObject.SetActive(showGhosts&&(!nearCockpit||(cameraIndex==1&&focusIndex==i+1)));
                }
                DrawLearning();
            }
            if(cameraIndex==4)
            {
                if(Input.GetMouseButton(1))orbitAngle+=Input.GetAxis("Mouse X")*3;
                zoom=Mathf.Clamp(zoom-Input.mouseScrollDelta.y*2,4,80);
            }
            if(!captured&&capturePath!=null&&frame!=null&&Time.realtimeSinceStartup-started>18)
            {Directory.CreateDirectory(Path.GetDirectoryName(capturePath));ScreenCapture.CaptureScreenshot(capturePath);captured=true;}
            if(captureAll&&frame!=null)
            {
                float age=Time.realtimeSinceStartup-started;
                if(captureStage<6&&age>20+captureStage*3)
                {
                    if(!capturePrepared)
                    {
                        cameraIndex=Mathf.Min(captureStage,4);
                        if(captureStage==4)orbitAngle=145;
                        if(captureStage==5)overlays=true;
                        capturePrepared=true;
                    }
                    if(age>21+captureStage*3)
                    {
                        string path=Path.Combine(Path.GetDirectoryName(capturePath),"view-"+captureStage+".png");
                        ScreenCapture.CaptureScreenshot(path);captureStage++;capturePrepared=false;
                    }
                }
                if(age>40&&age<41)wire.Command("mode",",\"value\":\"drive\"");
                if(age>41&&age<45)wire.Command("control",",\"value\":[0,3]");
                if(age>45&&age<47)wire.Command("control",",\"value\":[0.10,1]");
                if(age>47&&age<50)wire.Command("control",",\"value\":[0,-7]");
                if(age>44&&age<47&&frame.mode=="drive"&&frame.state[0]>1)manualExerciseObserved=true;
            }
            if(performancePath!=null&&Time.realtimeSinceStartup-started>75)
            {
                frameTimes.Sort();
                float p95=frameTimes.Count>0?frameTimes[Mathf.Min(frameTimes.Count-1,(int)(frameTimes.Count*.95f))]:0;
                float totalMs=0;foreach(float milliseconds in frameTimes)totalMs+=milliseconds;
                float comparisonFps=totalMs>0?1000*frameTimes.Count/totalMs:0;
                string json="{\"measurement\":\"four-car-replay-after-warmup\",\"frames\":"+frameTimes.Count+",\"p95_frame_ms\":"+Number(p95)+",\"fps_smoothed\":"+Number(fps)+",\"comparison_fps\":"+Number(comparisonFps)+",\"rendered_cars\":"+comparisonCars+",\"width\":"+Screen.width+",\"height\":"+Screen.height+",\"ghosts_visible\":"+(showGhosts?"true":"false")+",\"captured_views\":"+captureStage+",\"manual_exercise_observed\":"+(manualExerciseObserved?"true":"false")+"}";
                json=json.Substring(0,json.Length-1)+",\"motion_frames\":"+motionFrames+",\"motion_held_frames\":"+motionHeldFrames+",\"motion_min_sim_step\":"+Number(motionMinStep)+",\"motion_max_sim_step\":"+Number(motionMaxStep)+"}";
                Directory.CreateDirectory(Path.GetDirectoryName(performancePath));File.WriteAllText(performancePath,json);
                performancePath=null;if(smoke)Application.Quit();
            }
        }

        void ResetCar(){playback.Clear();wire.Command("reset");}

        void OnApplicationFocus(bool focused){if(!focused&&wire!=null){steering=0;wire.Command("control",",\"value\":[0,-7]");}}
        static string Number(float number)=>number.ToString("0.####",CultureInfo.InvariantCulture);

        void LateUpdate()
        {
            Transform target=focusIndex>0&&focusIndex<=ghosts.Count?ghosts[focusIndex-1].transform:car.transform;
            car.SetDriverView(cameraIndex==1&&focusIndex==0);
            for(int i=0;i<ghosts.Count;i++)ghosts[i].SetDriverView(cameraIndex==1&&focusIndex==i+1);
            Vector3 wanted,look=target.position+Vector3.up*.8f;
            Quaternion rotation;
            if(cameraIndex==1||cameraIndex==2)
            {
                wanted=target.TransformPoint(cameraIndex==1?new Vector3(-.31f,1.10f,-.42f):new Vector3(0,1.0f,1.24f));
                rotation=target.rotation*Quaternion.Euler(cameraIndex==1?1.5f:0,0,0);view.fieldOfView=cameraIndex==1?68:74;
                view.transform.SetPositionAndRotation(wanted,rotation);return;
            }
            if(cameraIndex==3)wanted=target.position+new Vector3(0,65,-.01f);
            else if(cameraIndex==4)wanted=target.position+Quaternion.Euler(28,orbitAngle,0)*new Vector3(0,0,-zoom);
            else wanted=target.TransformPoint(new Vector3(0,2.65f,-7.2f));
            // Follow the interpolated car directly: a second positional low-pass adds visible lag.
            rotation=Quaternion.LookRotation(look-wanted,Vector3.up);
            view.transform.SetPositionAndRotation(wanted,rotation);view.fieldOfView=65;
        }

        void SetGhosts(GhostInfo[] data)
        {
            foreach(var ghost in ghosts)Destroy(ghost.gameObject);ghosts.Clear();
            foreach(var line in racingLines)Destroy(line.gameObject);racingLines.Clear();
            ghostData=data??Array.Empty<GhostInfo>();
            for(int i=0;i<ghostData.Length;i++)
            {
                ghosts.Add(CarVisual.Create(ghostData[i].label+" ghost",ghostColors[i%ghostColors.Length],true));
                var line=MakeLine(ghostData[i].label+" racing line",ghostColors[i%ghostColors.Length],.10f);
                var poses=ghostData[i].poses;
                if(poses!=null)
                {
                    line.positionCount=poses.Length;
                    for(int j=0;j<poses.Length;j++)line.SetPosition(j,new Vector3(poses[j].x,.035f,poses[j].y));
                    var gradient=new Gradient();
                    var colors=new List<GradientColorKey>();
                    for(int j=0;j<8;j++)
                    {
                        int at=Mathf.Min(poses.Length-1,j*(poses.Length-1)/7);
                        float v=ghostData[i].speeds!=null&&at<ghostData[i].speeds.Length?ghostData[i].speeds[at]:8;
                        colors.Add(new GradientColorKey(Color.Lerp(new Color(.2f,.45f,1),new Color(1,.25f,.06f),Mathf.InverseLerp(6,25,v)),j/7f));
                    }
                    gradient.SetKeys(colors.ToArray(),new[]{new GradientAlphaKey(.75f,0),new GradientAlphaKey(.75f,1)});line.colorGradient=gradient;
                }
                racingLines.Add(line);
            }
            focusIndex=0;
        }

        void DrawLearning()
        {
            prediction.gameObject.SetActive(overlays);
            var path=frame.prediction??Array.Empty<Point>();prediction.positionCount=path.Length;
            for(int i=0;i<path.Length;i++)prediction.SetPosition(i,new Vector3(path[i].x,.12f,path[i].y));
            var samples=frame.safe_samples??Array.Empty<Point>();
            while(safeMarkers.Count<samples.Length)
            {
                var marker=CarVisual.Shape(null,"Projected terminal sample",PrimitiveType.Sphere,Vector3.zero,Vector3.one*.25f,CarVisual.Material(new Color(.4f,1,.6f)));
                safeMarkers.Add(marker);
            }
            for(int i=0;i<safeMarkers.Count;i++)
            {
                safeMarkers[i].SetActive(overlays&&i<samples.Length);
                if(i<samples.Length)safeMarkers[i].transform.position=new Vector3(samples[i].x,.32f,samples[i].y);
            }
            foreach(var line in racingLines)line.gameObject.SetActive(overlays);
        }

        void BuildTrack()
        {
            if(circuit!=null)Destroy(circuit);circuit=new GameObject("Circuit - shared control geometry");
            CarVisual.Shape(circuit.transform,"Circuit grass",PrimitiveType.Plane,new Vector3(0,-.045f,40),new Vector3(120,1,120),VisualTheme.Grain(new Color(.24f,.30f,.15f),17,.38f,190));
            var asphalt=VisualTheme.Grain(new Color(.19f,.205f,.215f),73,.35f,5);
            var shoulder=VisualTheme.Grain(new Color(.39f,.36f,.28f),19,.4f,3);
            Ribbon("Left gravel shoulder",track.width/2+.45f,track.width/2+1.7f,-.013f,new[]{shoulder});
            Ribbon("Right gravel shoulder",-track.width/2-1.7f,-track.width/2-.45f,-.013f,new[]{shoulder});
            Ribbon("Asphalt",-track.width/2,track.width/2,.001f,new[]{asphalt});
            var red=VisualTheme.Grain(new Color(.60f,.065f,.045f),3,.15f,2);
            var cream=VisualTheme.Grain(new Color(.82f,.82f,.74f),4,.15f,2);
            Ribbon("Left curb",track.width/2,track.width/2+.40f,.025f,new[]{red,cream});
            Ribbon("Right curb",-track.width/2-.40f,-track.width/2,.025f,new[]{cream,red});
            Ribbon("Left edge paint",track.width/2-.11f,track.width/2,.009f,new[]{cream});
            Ribbon("Right edge paint",-track.width/2,-track.width/2+.11f,.009f,new[]{cream});
            var black=VisualTheme.Surface(new Color(.025f,.03f,.035f));
            for(int row=0;row<2;row++)for(int column=0;column<16;column++)
                CarVisual.Shape(circuit.transform,"Finish checker",PrimitiveType.Cube,new Vector3(.30f+row*.6f,.015f,-3.75f+column*.5f),new Vector3(.6f,.008f,.5f),(row+column)%2==0?cream:black);
            for(int i=0;i<6;i++)
            {
                float x=-5-i*6;
                for(int side=-1;side<=1;side+=2)
                {
                    CarVisual.Shape(circuit.transform,"Starting grid line",PrimitiveType.Cube,new Vector3(x,.012f,side*2.1f),new Vector3(.08f,.008f,1.55f),cream);
                    CarVisual.Shape(circuit.transform,"Starting grid side",PrimitiveType.Cube,new Vector3(x-.7f,.012f,side*2.85f),new Vector3(1.4f,.008f,.08f),cream);
                }
            }
            CircuitScenery.Build(circuit.transform,track);
            var probe=new GameObject("Circuit reflections").AddComponent<ReflectionProbe>();probe.transform.SetParent(circuit.transform,false);
            probe.transform.position=new Vector3(0,3,0);probe.mode=ReflectionProbeMode.Realtime;probe.refreshMode=ReflectionProbeRefreshMode.ViaScripting;
            probe.timeSlicingMode=ReflectionProbeTimeSlicingMode.IndividualFaces;probe.resolution=128;probe.size=Vector3.one*900;probe.farClipPlane=650;probe.intensity=.7f;probe.RenderProbe();
            BuildMap();

        }

        void Ribbon(string name,float left,float right,float height,Material[] materials)
        {
            int n=track.samples.Length;
            var vertices=new Vector3[n*2];var uv=new Vector2[n*2];
            var indices=new List<int>[materials.Length];for(int j=0;j<indices.Length;j++)indices[j]=new List<int>();
            for(int i=0;i<n;i++)
            {
                var p=track.samples[i];Vector3 center=new Vector3(p.x,height,p.y),normal=new Vector3(-Mathf.Sin(p.heading),0,Mathf.Cos(p.heading));
                vertices[i*2]=center+normal*left;vertices[i*2+1]=center+normal*right;
                uv[i*2]=new Vector2(0,p.s/5);uv[i*2+1]=new Vector2(1,p.s/5);
                if(i<n-1)
                {
                    int k=i*2;var list=indices[(int)(p.s/4)%materials.Length];
                    list.AddRange(new[]{k,k+1,k+2,k+1,k+3,k+2});
                }
            }
            var mesh=new Mesh{name=name};mesh.vertices=vertices;mesh.uv=uv;mesh.subMeshCount=materials.Length;
            for(int j=0;j<materials.Length;j++)mesh.SetTriangles(indices[j],j);mesh.RecalculateNormals();
            var go=new GameObject(name,typeof(MeshFilter),typeof(MeshRenderer));go.transform.SetParent(circuit.transform,false);
            go.GetComponent<MeshFilter>().sharedMesh=mesh;go.GetComponent<MeshRenderer>().sharedMaterials=materials;
        }

        void BuildMap()
        {
            float minX=float.MaxValue,maxX=float.MinValue,minY=float.MaxValue,maxY=float.MinValue;
            foreach(var p in track.samples){minX=Mathf.Min(minX,p.x);maxX=Mathf.Max(maxX,p.x);minY=Mathf.Min(minY,p.y);maxY=Mathf.Max(maxY,p.y);}
            mapSpan=Mathf.Max(maxX-minX,maxY-minY)+20;mapMin=new Vector2((minX+maxX-mapSpan)/2,(minY+maxY-mapSpan)/2);
            if(trackMap!=null)Destroy(trackMap);trackMap=new Texture2D(256,256,TextureFormat.RGBA32,false);
            trackMap.SetPixels(new Color[256*256]);
            for(int i=1;i<track.samples.Length;i++)
            {
                var a=track.samples[i-1];var b=track.samples[i];
                Vector2 start=(new Vector2(a.x,a.y)-mapMin)/mapSpan*255,end=(new Vector2(b.x,b.y)-mapMin)/mapSpan*255;
                int count=Mathf.Max(1,Mathf.CeilToInt(Vector2.Distance(start,end)*2));
                for(int j=0;j<=count;j++)
                {
                    var q=Vector2.Lerp(start,end,(float)j/count);
                    for(int dx=-2;dx<=2;dx++)for(int dy=-2;dy<=2;dy++)trackMap.SetPixel(Mathf.Clamp((int)q.x+dx,0,255),Mathf.Clamp((int)q.y+dy,0,255),new Color(.55f,.66f,.68f));
                }
            }
            trackMap.Apply();
        }
        void MapDot(Vector3 position,Color color,float size)
        {
            float x=(position.x-mapMin.x)/mapSpan,y=(position.z-mapMin.y)/mapSpan;
            GUI.color=color;GUI.DrawTexture(new Rect(1090+x*150-size/2,666-y*150-size/2,size,size),white);GUI.color=Color.white;
        }
        void MapPanel()
        {
            if(trackMap==null)return;
            Panel(new Rect(1075,485,180,193),new Color(.035f,.055f,.065f,.86f));
            GUI.Label(new Rect(1090,496,150,20),"TRACK POSITION",small);GUI.DrawTexture(new Rect(1090,516,150,150),trackMap);
            if(showGhosts)for(int i=0;i<ghosts.Count;i++)MapDot(ghosts[i].transform.position,new Color(ghostColors[i%ghostColors.Length].r,ghostColors[i%ghostColors.Length].g,ghostColors[i%ghostColors.Length].b),4);
            MapDot(car.transform.position,mint,6);
        }

        void Styles()
        {
            if(label!=null)return;white=Texture2D.whiteTexture;
            var font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label=new GUIStyle{font=font,fontSize=16,normal={textColor=new Color(.9f,.94f,.96f)}};
            small=new GUIStyle(label){fontSize=12,wordWrap=true};heading=new GUIStyle(label){fontSize=24,fontStyle=FontStyle.Bold};
            speedStyle=new GUIStyle(heading){fontSize=50};
            buttonIdle=Swatch(new Color(.09f,.125f,.145f,.96f));buttonHover=Swatch(new Color(.18f,.25f,.28f));buttonSelected=Swatch(new Color(.08f,.39f,.33f));
            button=new GUIStyle(GUI.skin.button){font=font,fontSize=12,fontStyle=FontStyle.Bold,padding=new RectOffset(8,8,7,7),border=new RectOffset(0,0,0,0)};
            button.normal.background=buttonIdle;button.normal.textColor=new Color(.81f,.87f,.89f);
            button.hover.background=buttonHover;button.hover.textColor=Color.white;
            button.active.background=buttonSelected;button.active.textColor=Color.white;
            button.focused.background=buttonIdle;button.focused.textColor=Color.white;
        }
        static Texture2D Swatch(Color color){var t=new Texture2D(1,1);t.SetPixel(0,0,color);t.Apply();return t;}
        void Panel(Rect rect,Color color)
        {
            GUI.color=new Color(0,0,0,.18f);GUI.DrawTexture(new Rect(rect.x+2,rect.y+3,rect.width,rect.height),white);
            GUI.color=color;GUI.DrawTexture(rect,white);
            GUI.color=new Color(.65f,.85f,.85f,.18f);GUI.DrawTexture(new Rect(rect.x,rect.y,rect.width,1),white);GUI.color=Color.white;
        }
        bool Button(Rect rect,string text,bool active=false)
        {
            button.normal.background=active?buttonSelected:buttonIdle;
            bool pressed=GUI.Button(rect,text,button);
            if(active){GUI.color=mint;GUI.DrawTexture(new Rect(rect.x,rect.y+rect.height-2,rect.width,2),white);GUI.color=Color.white;}
            return pressed;
        }

        void OnGUI()
        {
            Styles();GUI.matrix=Matrix4x4.Scale(new Vector3(Screen.width/1280f,Screen.height/720f,1));
            Panel(new Rect(0,0,1280,70),new Color(.035f,.055f,.065f,.95f));
            GUI.Label(new Rect(25,13,345,34),"C4  /  MOTORSPORT LAB",heading);
            GUI.color=mint;GUI.DrawTexture(new Rect(0,0,5,70),white);GUI.color=Color.white;
            string profile=frame?.controller_profile??"robust-lmpc";
            GUI.Label(new Rect(27,47,490,20),profile.StartsWith("LEGACY")?"LEGACY RECORDING · REPLAY ONLY":"LMPC · FULL-SIZE ADAPTATION · "+profile.ToUpperInvariant(),small);
            string mode=frame?.mode??"learn";
            string[] modes={"learn","drive","replay"};
            for(int i=0;i<modes.Length;i++)if(Button(new Rect(530+i*104,18,96,35),modes[i].ToUpperInvariant(),mode==modes[i]))wire.Command("mode",",\"value\":\""+modes[i]+"\"");
            if(Button(new Rect(864,18,92,35),frame!=null&&frame.paused?"RESUME":"PAUSE"))wire.Command("pause");
            if(Button(new Rect(965,18,115,35),overlays?"HIDE DATA":"SHOW DATA",overlays))overlays=!overlays;
            if(Button(new Rect(1088,18,80,35),"LAPS"))showHistory=!showHistory;
            if(Button(new Rect(1176,18,78,35),"HELP"))help=!help;
            Panel(new Rect(22,88,345,84),new Color(.035f,.055f,.065f,.88f));
            GUI.Label(new Rect(38,99,320,25),frame==null?wire.Status:(frame.phase=="warmup"?"BUILDING SAFE WARM-UP LAPS":frame.phase=="learn"?"OPTIMIZING LAP TIME":mode.ToUpperInvariant()),label);
            GUI.Label(new Rect(38,129,320,35),track==null?"Waiting for local simulation":$"L-CIRCUIT  {track.length:F0} m   /   LAP {frame?.lap??1}   /   {(frame==null?0:presented.Elapsed):F1}s",small);
            GUI.Label(new Rect(38,151,320,20),"TRACK LIMIT: HALF-WIDTH OVERHANG",small);
            Panel(new Rect(22,594,360,92),new Color(.035f,.055f,.065f,.92f));
            float velocity=frame?.state!=null?frame.state[0]*3.6f:0;
            GUI.Label(new Rect(37,592,145,64),$"{velocity:F0}",speedStyle);GUI.Label(new Rect(155,627,60,20),"KM/H",small);
            GUI.Label(new Rect(228,611,150,22),cameras[cameraIndex],label);
            GUI.Label(new Rect(228,641,150,22),$"{fps:F0} FPS  ·  {(mode=="drive"?1:frame?.speed??1):F1}×",small);
            // Compact live steering bar: input response is visible without opening research data.
            Panel(new Rect(38,668,170,3),new Color(.25f,.32f,.34f));
            float shownSteer=frame?.control!=null?frame.control[0]:0;
            GUI.color=mint;GUI.DrawTexture(new Rect(121-Mathf.Clamp(shownSteer/.5f,-1,1)*82,663,3,13),white);GUI.color=Color.white;
            GUI.Label(new Rect(26,696,1210,22),"WASD / ARROWS  drive     SPACE  brake     C  camera     TAB  focus     G  ghosts     L  data     P  pause     R  reset / retry     M  learn / drive",small);
            for(int i=0;i<ghostData.Length;i++)
            {
                Panel(new Rect(1040,88+i*38,215,31),new Color(.035f,.055f,.065f,.85f));GUI.color=ghostColors[i%ghostColors.Length];GUI.DrawTexture(new Rect(1051,98+i*38,10,10),white);GUI.color=Color.white;
                GUI.Label(new Rect(1072,94+i*38,180,23),$"{ghostData[i].label}    {ghostData[i].seconds:F1}s",small);
            }
            if(mode!="drive")
            {
                float[] speeds={.5f,1,2,4,8};for(int i=0;i<speeds.Length;i++)if(Button(new Rect(420+i*60,646,55,30),speeds[i]+"×"))wire.Command("speed",",\"value\":"+Number(speeds[i]));
                if(Button(new Rect(735,646,100,30),"LOAD SAVED"))wire.Command("load");
                if(Button(new Rect(843,646,100,30),"LOAD DEMO"))wire.Command("demo");
                if(Button(new Rect(951,646,88,30),"OLD v1"))wire.Command("legacy_demo");
            }
            if(frame!=null&&frame.slowdown>1.2f&&!frame.paused&&mode=="learn")GUI.Label(new Rect(420,615,570,25),$"Simulation running at {1/frame.slowdown:F2}× requested pace; physics steps are preserved.",small);
            if(mode=="replay"&&ghostData.Length>0)
            {
                float duration=frame!=null?frame.replay_duration:0;
                float value=GUI.HorizontalSlider(new Rect(420,601,520,20),frame?.elapsed??0,0,duration);
                if(frame!=null&&Mathf.Abs(value-frame.elapsed)>.12f)wire.Command("seek",",\"value\":"+Number(value));
            }
            MapPanel();
            if(overlays)ResearchPanel();
            if(showHistory)HistoryPanel();
            if(frame!=null&&!string.IsNullOrEmpty(frame.message))GUI.Label(new Rect(420,92,600,55),frame.message,small);
            if(frame!=null&&mode=="replay"&&frame.controller_profile!=null&&frame.controller_profile.StartsWith("LEGACY"))
                GUI.Label(new Rect(420,145,600,35),"LEGACY RECORDING · REPLAY ONLY",small);
            if(frame!=null&&!wire.Connected)GUI.Label(new Rect(420,145,600,35),"Local simulation disconnected. Reconnecting; last pose held.",label);
            if(frame!=null&&!string.IsNullOrEmpty(frame.failure))
            {
                Panel(new Rect(395,250,530,146),new Color(.13f,.045f,.035f,.96f));
                GUI.Label(new Rect(416,266,485,28),"ATTEMPT PAUSED",heading);
                GUI.Label(new Rect(416,303,485,44),frame.failure,small);
                if(Button(new Rect(416,354,485,28),"RETRY FROM LAP START — KEEP SUCCESSFUL DATA"))ResetCar();
            }
            if(help)
            {
                Panel(new Rect(360,155,570,430),new Color(.035f,.055f,.065f,.98f));
                GUI.Label(new Rect(385,175,520,35),"DRIVE. WATCH. COMPARE.",heading);
                GUI.Label(new Rect(385,225,520,300),"ROBUST-LMPC is an explicit full-size adaptation: 2.4 s prediction, nonlinear bicycle model with local residual learning, and penalized terminal mismatch. PAPER-HARD retains the paper's 1.2 s/data-only/hard-terminal controller for comparison.\n\nTRACK LIMIT: up to half the car width (0.9 m) may extend beyond either road edge. Rotation and front/rear corners count.\n\nLOAD DEMO replays the current benchmark. OLD v1 opens historical data read-only. Replays and manual laps never enter current AI training.\n\nKeyboard steering responds in ~0.11 s at standstill; release recenters faster. Sensitivity reduces with speed.\n\nC changes camera; TAB changes focus. Right-drag/scroll controls orbit. L toggles data; G toggles ghosts.\n\nSee docs/PAPER_ALIGNMENT.md for the prediction and safety adaptations.",small);
                if(Button(new Rect(385,537,520,30),"BACK TO CIRCUIT"))help=false;
            }
        }

        void ResearchPanel()
        {
            Panel(new Rect(22,185,345,393),new Color(.035f,.055f,.065f,.94f));
            GUI.Label(new Rect(38,200,315,30),"LEARNING TELEMETRY",label);
            var solver=frame?.solver;
            GUI.Label(new Rect(38,234,310,55),solver==null?"Waiting for first solve":$"QP  {solver.milliseconds:F1} ms    {solver.status}\nTerminal residual {solver.terminal_residual:F4} / slack {solver.terminal_slack:F4}\nN={solver.horizon} / samples={solver.terminal_samples} / tire slack {solver.tire_range_slack:F3}",small);
            GUI.Label(new Rect(38,292,310,24),frame?.control!=null?$"Steering  {frame.control[0]*Mathf.Rad2Deg:F1}°    Accel  {frame.control[1]:F1} m/s²":"",small);
            GUI.Label(new Rect(38,318,310,32),"Dots: projected terminal state samples\nRecorded lines: blue 6 → red 25 m/s",small);
            GUI.Label(new Rect(38,347,310,22),"LAP TIME  /  EVERY ATTEMPT",small);
            var history=frame?.learning_history;
            Panel(new Rect(39,379,305,131),new Color(.10f,.14f,.16f));
            if(history!=null&&history.Length>0)
            {
                float max=1,min=1000;foreach(var lap in history)if(lap.valid){max=Mathf.Max(max,lap.seconds);min=Mathf.Min(min,lap.seconds);}
                for(int i=0;i<history.Length;i++)
                {
                    var lap=history[i];float x=45+i*290f/Mathf.Max(1,history.Length-1);
                    float y=lap.valid?Mathf.Lerp(495,390,Mathf.InverseLerp(Mathf.Max(0,min-2),max+2,lap.seconds)):502;
                    GUI.color=lap.valid?(lap.kind=="warmup"?new Color(.3f,.7f,1):mint):new Color(1,.3f,.15f);
                    GUI.DrawTexture(new Rect(x-2,y-2,5,5),white);GUI.color=Color.white;
                }
                GUI.Label(new Rect(40,516,300,22),$"{history.Length} attempts  /  last {history[history.Length-1].seconds:F1}s",small);
            }
            GUI.Label(new Rect(38,546,310,26),"Data updates after each completed lap.",small);
        }

        void HistoryPanel()
        {
            Panel(new Rect(760,235,495,350),new Color(.035f,.055f,.065f,.96f));
            GUI.Label(new Rect(780,251,450,25),"RECORDED LAPS — SELECT TO REPLAY",label);
            if(Button(new Rect(1085,264,145,23),"LATEST GHOST"))wire.Command("ghost",",\"lap\":0");
            var history=frame?.learning_history??Array.Empty<LapInfo>();
            historyScroll=GUI.BeginScrollView(new Rect(780,290,455,275),historyScroll,new Rect(0,0,430,history.Length*36));
            for(int i=0;i<history.Length;i++)
            {
                var lap=history[i];
                if(Button(new Rect(0,i*36,325,31),$"{lap.number:00}  {lap.kind.ToUpperInvariant()}   {lap.seconds:F1}s   {(lap.valid?"REPLAY":"REJECTED")}"))
                    if(lap.valid){wire.Command("replay",",\"lap\":"+lap.number);wire.Command("mode",",\"value\":\"replay\"");}
                if(lap.valid&&Button(new Rect(332,i*36,90,31),"GHOST"))wire.Command("ghost",",\"lap\":"+lap.number);
            }
            GUI.EndScrollView();
        }
        void OnDestroy(){wire?.Dispose();}
    }
}
