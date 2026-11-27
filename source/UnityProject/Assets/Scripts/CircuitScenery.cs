using UnityEngine;
using System.Collections.Generic;

namespace CorvetteLab
{
    public static class CircuitScenery
    {
        static GameObject Box(Transform parent,string name,Vector3 p,Vector3 size,Material m)
        {return CarVisual.Shape(parent,name,PrimitiveType.Cube,p,size,m);}
        public static void Build(Transform parent,TrackInfo track)
        {
            var group=new GameObject("Circuit architecture and landscape").transform;group.SetParent(parent,false);
            var steel=VisualTheme.Surface(new Color(.38f,.43f,.46f),.55f,.6f);
            var dark=VisualTheme.Surface(new Color(.055f,.075f,.085f),.25f,.25f);
            var concrete=VisualTheme.Grain(new Color(.52f,.53f,.50f),11,.25f,2);
            var white=VisualTheme.Surface(new Color(.83f,.84f,.79f),.35f);
            var teal=VisualTheme.Surface(new Color(.035f,.32f,.31f),.45f,.3f);
            var orange=VisualTheme.Surface(new Color(.95f,.32f,.08f));
            var glass=VisualTheme.Surface(new Color(.09f,.20f,.25f),.85f,.5f);
            // Armco, two rails and spaced posts, aligned with the shared road samples.
            for(int i=0;i<track.samples.Length-1;i+=4)
            {
                var p=track.samples[i];var q=track.samples[Mathf.Min(i+4,track.samples.Length-1)];
                for(int side=-1;side<=1;side+=2)
                {
                    float offset=side*(track.width/2+3);
                    var a=new Vector3(p.x-Mathf.Sin(p.heading)*offset,0,p.y+Mathf.Cos(p.heading)*offset);
                    var b=new Vector3(q.x-Mathf.Sin(q.heading)*offset,0,q.y+Mathf.Cos(q.heading)*offset);
                    if(Vector3.Distance(a,b)<.01f)continue;
                    for(int rail=0;rail<2;rail++)
                    {
                        var item=Box(group,"Armco beam",(a+b)/2+Vector3.up*(.49f+rail*.25f),new Vector3(.075f,.17f,Vector3.Distance(a,b)+.04f),steel);
                        item.transform.rotation=Quaternion.LookRotation(b-a);
                    }
                    Box(group,"Armco support",a+Vector3.up*.38f,new Vector3(.12f,.76f,.12f),dark);
                }
            }
            // A pit paddock sits outside the starting straight.
            Box(group,"Paddock concrete",new Vector3(24,-.015f,-19),new Vector3(58,.025f,20),concrete);
            for(int i=0;i<6;i++)
            {
                float x=4+i*8;
                Box(group,"Pit garage",new Vector3(x,1.7f,-21),new Vector3(7.5f,3.4f,8),white);
                Box(group,"Garage opening",new Vector3(x,1.4f,-16.98f),new Vector3(5.7f,2.7f,.04f),dark);
                Box(group,"Garage lintel",new Vector3(x,3.12f,-16.8f),new Vector3(7.5f,.35f,.45f),i%2==0?teal:orange);
                Box(group,"Garage ribbed door",new Vector3(x,2.65f,-16.94f),new Vector3(5.6f,.6f,.035f),steel);
                for(int j=0;j<6;j++)Box(group,"Door rib",new Vector3(x,2.39f+j*.10f,-16.91f),new Vector3(5.5f,.012f,.025f),dark);
                Sign(group,"0"+(i+1),new Vector3(x,3.13f,-16.54f),Quaternion.Euler(0,180,0),.12f,Color.white);
            }
            Box(group,"Pit building flat roof",new Vector3(24,3.52f,-21),new Vector3(48.5f,.20f,8.8f),dark);
            Box(group,"Race control",new Vector3(-4,3.3f,-21),new Vector3(7,6.6f,8),concrete);
            Box(group,"Control room glazing",new Vector3(-4,5.4f,-16.96f),new Vector3(6.5f,1.7f,.04f),glass);
            Box(group,"Control roof",new Vector3(-4,6.7f,-21),new Vector3(7.5f,.2f,8.5f),dark);
            // A readable start gantry, with original fictional branding.
            for(int side=-1;side<=1;side+=2)Box(group,"Timing tower",new Vector3(0,2.8f,side*5.6f),new Vector3(.45f,5.6f,.45f),dark);
            Box(group,"Timing sign",new Vector3(0,5.35f,0),new Vector3(.65f,1.1f,11.7f),dark);
            Box(group,"Timing accent",new Vector3(-.34f,4.87f,0),new Vector3(.015f,.09f,11.4f),teal);
            Sign(group,"C4  /  MOTOR CIRCUIT",new Vector3(-.345f,5.4f,0),Quaternion.Euler(0,90,0),.15f,Color.white);
            Sign(group,"CORVETTE   /   LEARNING LAB",new Vector3(24,3.98f,-16.5f),Quaternion.Euler(0,180,0),.18f,Color.white);
            // Grandstand alongside the straight. No scenery has physics colliders.
            for(int row=0;row<5;row++)
            {
                Box(group,"Grandstand terrace",new Vector3(22,.35f+row*.48f,12+row*1.1f),new Vector3(32,.28f,1.1f),concrete);
                for(int seat=0;seat<32;seat++)Box(group,"Grandstand seat",new Vector3(6.5f+seat,.64f+row*.48f,12+row*1.1f),new Vector3(.68f,.12f,.57f),(seat/8)%2==0?teal:white);
            }
            for(int x=7;x<=37;x+=10)Box(group,"Canopy column",new Vector3(x,3.1f,17.1f),new Vector3(.15f,6.2f,.15f),steel);
            Box(group,"Grandstand canopy",new Vector3(22,6.2f,14.7f),new Vector3(33,.16f,7),white);
            // Deterministic landscape. Keep trees well clear of every part of the road.
            var bark=VisualTheme.Surface(new Color(.20f,.16f,.105f));
            var leaves=new[]{VisualTheme.Grain(new Color(.12f,.20f,.08f),24,.9f,9),VisualTheme.Grain(new Color(.19f,.27f,.11f),26,.9f,9),VisualTheme.Grain(new Color(.24f,.30f,.13f),29,.9f,9)};
            Mesh canopy=null;
            var rng=new System.Random(401);float minX=0,maxX=0,minY=0,maxY=0;
            foreach(var p in track.samples){minX=Mathf.Min(minX,p.x);maxX=Mathf.Max(maxX,p.x);minY=Mathf.Min(minY,p.y);maxY=Mathf.Max(maxY,p.y);}
            for(int i=0;i<360;i++)
            {
                float x=Mathf.Lerp(minX-90,maxX+90,(float)rng.NextDouble()),z=Mathf.Lerp(minY-80,maxY+80,(float)rng.NextDouble());
                if(x>-12&&x<58&&z>-32&&z<22)continue;
                float nearest=float.MaxValue;foreach(var p in track.samples)nearest=Mathf.Min(nearest,(x-p.x)*(x-p.x)+(z-p.y)*(z-p.y));
                if(nearest<20*20)continue;
                float h=4+(float)rng.NextDouble()*5;
                var trunk=CarVisual.Shape(group,"Tree trunk",PrimitiveType.Cylinder,new Vector3(x,h*.28f,z),new Vector3(.3f,h*.28f,.3f),bark);
                for(int layer=0;layer<3;layer++)
                {
                    var crown=CarVisual.Shape(group,"Tree crown",PrimitiveType.Sphere,new Vector3(x+(layer-1)*h*.18f,h*(.59f+layer*.1f),z+Mathf.Sin(i*7+layer)*h*.10f),new Vector3(h*.49f,h*.52f,h*.48f),leaves[i%3]);
                    if(canopy==null)
                    {
                        canopy=Object.Instantiate(crown.GetComponent<MeshFilter>().sharedMesh);canopy.name="Irregular original foliage";
                        var vertices=canopy.vertices;
                        for(int j=0;j<vertices.Length;j++)
                        {
                            var p=vertices[j];float noise=Mathf.PerlinNoise(p.x*12+41,p.y*11+p.z*8+17);
                            vertices[j]*=.78f+noise*.5f;
                        }
                        canopy.vertices=vertices;canopy.RecalculateNormals();canopy.RecalculateBounds();
                    }
                    crown.GetComponent<MeshFilter>().sharedMesh=canopy;crown.transform.localRotation=Quaternion.Euler(0,i*137+layer*73,0);
                }
            }
            // A low rolling horizon beyond the circuit grounds.
            for(int i=0;i<24;i++)
            {
                float a=i*2*Mathf.PI/24,r=310+(float)rng.NextDouble()*120;
                CarVisual.Shape(group,"Distant wooded hill",PrimitiveType.Sphere,new Vector3((minX+maxX)*.5f+Mathf.Cos(a)*r,-22,(minY+maxY)*.5f+Mathf.Sin(a)*r),new Vector3(190,65+(float)rng.NextDouble()*60,170),leaves[i%3]);
            }
            VisualTheme.Combine(group);
        }
        static void Sign(Transform parent,string text,Vector3 position,Quaternion rotation,float size,Color color)
        {
            var go=new GameObject("Circuit sign");go.transform.SetParent(parent,false);go.transform.localPosition=position;go.transform.localRotation=rotation;
            var label=go.AddComponent<TextMesh>();label.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            go.GetComponent<MeshRenderer>().sharedMaterial=label.font.material;
            label.text=text;label.anchor=TextAnchor.MiddleCenter;label.alignment=TextAlignment.Center;label.characterSize=size;label.fontSize=64;label.color=color;
        }
    }
}
