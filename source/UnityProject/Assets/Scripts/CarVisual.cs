using UnityEngine;
using UnityEngine.Rendering;
using System.Collections.Generic;

namespace CorvetteLab
{
    public sealed class CarVisual : MonoBehaviour
    {
        public Transform[] wheels=new Transform[4];
        public Transform[] steering=new Transform[2];
        Transform shell,steeringWheel,driverInterior,driverWheel;
        Vector3 lastPosition;bool hasPose;
        float rotation;
        public static Material Material(Color color,bool ghost=false)
        {
            var saved=Resources.Load<Material>(ghost?"RacingGhost":"RacingPaint");
            var material=saved!=null?new Material(saved):new Material(Shader.Find("Universal Render Pipeline/Lit"));
            material.SetColor("_BaseColor",color);material.SetFloat("_Metallic",ghost?0:.25f);material.SetFloat("_Smoothness",.72f);
            if(ghost)
            {
                material.SetFloat("_Surface",1);material.SetFloat("_Blend",0);
                material.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);material.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);
                material.SetFloat("_ZWrite",0);material.SetOverrideTag("RenderType","Transparent");
                material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");material.renderQueue=(int)RenderQueue.Transparent;
                material.SetFloat("_Smoothness",.15f);material.SetFloat("_SpecularHighlights",0);material.EnableKeyword("_SPECULARHIGHLIGHTS_OFF");
            }
            return material;
        }
        public static GameObject Shape(Transform parent,string name,PrimitiveType type,Vector3 position,Vector3 scale,Material material)
        {
            var part=GameObject.CreatePrimitive(type);part.name=name;part.transform.SetParent(parent,false);
            part.transform.localPosition=position;part.transform.localScale=scale;Object.Destroy(part.GetComponent<Collider>());
            part.GetComponent<Renderer>().sharedMaterial=material;return part;
        }
        static GameObject MeshPart(Transform parent,string name,Vector3[] vertices,int[] indices,Material material)
        {
            var mesh=new Mesh{name=name};mesh.vertices=vertices;mesh.triangles=indices;mesh.RecalculateNormals();mesh.RecalculateBounds();
            var part=new GameObject(name,typeof(MeshFilter),typeof(MeshRenderer));part.transform.SetParent(parent,false);
            part.GetComponent<MeshFilter>().sharedMesh=mesh;part.GetComponent<MeshRenderer>().sharedMaterial=material;return part;
        }
        // Beveled cross sections preserve the long hood, low beltline and tapered C4 nose.
        static void Body(Transform parent,Material paint)
        {
            float[] zs={-2.24f,-2.12f,-1.7f,-1.22f,-.80f,.20f,1.22f,1.80f,2.13f,2.24f};
            float[] widths={.78f,.88f,.90f,.90f,.855f,.855f,.90f,.87f,.81f,.76f};
            float[] heights={.73f,.81f,.85f,.84f,.80f,.79f,.79f,.71f,.61f,.55f};
            var v=new List<Vector3>();var t=new List<int>();const int ringSize=10,steps=112;
            for(int i=0;i<=steps;i++)
            {
                float z=Mathf.Lerp(-2.24f,2.24f,i/(float)steps);int segment=0;
                while(segment<zs.Length-2&&z>zs[segment+1])segment++;
                float f=Mathf.InverseLerp(zs[segment],zs[segment+1],z);
                float w=Mathf.Lerp(widths[segment],widths[segment+1],f),h=Mathf.Lerp(heights[segment],heights[segment+1],f);
                float bottom=.30f;
                foreach(float axle in new[]{-1.22f,1.22f})
                {
                    float d=Mathf.Abs(z-axle);if(d<.365f)bottom=Mathf.Max(bottom,.325f+Mathf.Sqrt(.365f*.365f-d*d));
                }
                float shoulder=Mathf.Max(h-.055f,bottom+.006f);
                v.AddRange(new[]{new Vector3(-w+.14f,.28f,z),new Vector3(w-.14f,.28f,z),new Vector3(w,bottom,z),
                    new Vector3(w,shoulder,z),new Vector3(w-.065f,h+.014f,z),new Vector3(w*.62f,h-.018f,z),
                    new Vector3(-w*.62f,h-.018f,z),new Vector3(-w+.065f,h+.014f,z),new Vector3(-w,shoulder,z),new Vector3(-w,bottom,z)});
                if(i>0)for(int j=0;j<ringSize;j++)
                {int a=(i-1)*ringSize+j,bv=(i-1)*ringSize+(j+1)%ringSize,c=i*ringSize+j,d=i*ringSize+(j+1)%ringSize;t.AddRange(new[]{a,bv,c,bv,d,c});}
            }
            for(int j=1;j<ringSize-1;j++){t.AddRange(new[]{0,j+1,j});int end=steps*ringSize;t.AddRange(new[]{end,end+j,end+j+1});}
            MeshPart(parent,"C4 clamshell body with open wheel arches",v.ToArray(),t.ToArray(),paint);
        }

        static GameObject Quad(Transform parent,string name,Vector3 a,Vector3 b,Vector3 c,Vector3 d,Material mat)
        {return MeshPart(parent,name,new[]{a,b,c,d},new[]{0,1,2,0,2,3},mat);}
        static Transform Torus(Transform parent,string name,Vector3 position,float radius,float tube,Material mat,bool axleX=false)
        {
            const int rings=40,sides=8;var v=new Vector3[rings*sides];var t=new List<int>();
            for(int i=0;i<rings;i++)for(int j=0;j<sides;j++)
            {
                float a=2*Mathf.PI*i/rings,b=2*Mathf.PI*j/sides,r=radius+tube*Mathf.Cos(b);
                v[i*sides+j]=axleX?new Vector3(tube*Mathf.Sin(b),r*Mathf.Cos(a),r*Mathf.Sin(a)):new Vector3(r*Mathf.Cos(a),r*Mathf.Sin(a),tube*Mathf.Cos(b));
                if(!axleX)v[i*sides+j]=new Vector3(r*Mathf.Cos(a),r*Mathf.Sin(a),tube*Mathf.Sin(b));
                int p=i*sides+j,q=((i+1)%rings)*sides+j,u=i*sides+(j+1)%sides,w=((i+1)%rings)*sides+(j+1)%sides;
                t.AddRange(new[]{p,q,u,u,q,w});
            }
            var part=MeshPart(parent,name,v,t.ToArray(),mat);part.transform.localPosition=position;return part.transform;
        }
        static void Emissive(Material mat,Color color,float strength)
        {mat.EnableKeyword("_EMISSION");mat.SetColor("_EmissionColor",color*strength);}
        public static CarVisual Create(string name,Color color,bool ghost=false)
        {
            var root=new GameObject(name);var car=root.AddComponent<CarVisual>();
            car.shell=new GameObject("Body roll").transform;car.shell.SetParent(root.transform,false);
            var paint=Material(color,ghost);var glass=Material(ghost?color:new Color(.025f,.055f,.075f),ghost);
            var black=Material(ghost?color:new Color(.017f,.022f,.026f),ghost);black.SetFloat("_Metallic",0);black.SetFloat("_Smoothness",.3f);
            var rubber=Material(ghost?color:new Color(.025f,.028f,.03f),ghost);rubber.SetFloat("_Metallic",0);rubber.SetFloat("_Smoothness",.15f);
            var chrome=Material(ghost?color:new Color(.65f,.7f,.74f),ghost);chrome.SetFloat("_Metallic",.9f);
            var darkMetal=Material(ghost?color:new Color(.13f,.16f,.18f),ghost);
            Body(car.shell,paint);
            Quad(car.shell,"Sloped windshield",new Vector3(-.74f,.80f,.23f),new Vector3(.74f,.80f,.23f),new Vector3(.62f,1.19f,-.34f),new Vector3(-.62f,1.19f,-.34f),glass);
            Quad(car.shell,"Rear hatch glass",new Vector3(-.61f,1.19f,-.91f),new Vector3(.61f,1.19f,-.91f),new Vector3(.76f,.84f,-1.72f),new Vector3(-.76f,.84f,-1.72f),glass);
            Shape(car.shell,"Targa roof",PrimitiveType.Cube,new Vector3(0,1.205f,-.63f),new Vector3(1.29f,.06f,.67f),black);
            for(int side=-1;side<=1;side+=2)
            {
                // Side windows slope inward, leaving a readable C4 greenhouse silhouette.
                var a=new Vector3(side*.76f,.80f,.22f);var b=new Vector3(side*.76f,.83f,-1.44f);
                var c=new Vector3(side*.62f,1.19f,-.91f);var d=new Vector3(side*.62f,1.19f,-.34f);
                if(side>0)Quad(car.shell,"Side glass",a,d,c,b,glass);else Quad(car.shell,"Side glass",a,b,c,d,glass);
                var pillar=Shape(car.shell,"Windscreen pillar",PrimitiveType.Cube,new Vector3(side*.695f,1,-.07f),new Vector3(.065f,.04f,.72f),paint);pillar.transform.localRotation=Quaternion.Euler(34,0,0);
                Shape(car.shell,"B pillar",PrimitiveType.Cube,new Vector3(side*.69f,.995f,-.95f),new Vector3(.075f,.4f,.16f),paint);
                Shape(car.shell,"Beltline trim",PrimitiveType.Cube,new Vector3(side*.866f,.525f,-.02f),new Vector3(.024f,.045f,1.63f),black);
                Shape(car.shell,"Side skirt",PrimitiveType.Cube,new Vector3(side*.85f,.30f,-.05f),new Vector3(.07f,.10f,1.65f),black);
                Shape(car.shell,"Door seam",PrimitiveType.Cube,new Vector3(side*.887f,.62f,-.92f),new Vector3(.008f,.22f,.013f),black);
                Shape(car.shell,"Door handle",PrimitiveType.Cube,new Vector3(side*.89f,.735f,-.79f),new Vector3(.018f,.035f,.19f),black);
                Shape(car.shell,"Mirror arm",PrimitiveType.Cube,new Vector3(side*.86f,.86f,.02f),new Vector3(.20f,.035f,.07f),black);
                var mirror=Shape(car.shell,"Aero mirror",PrimitiveType.Sphere,new Vector3(side*.98f,.90f,.05f),new Vector3(.23f,.14f,.30f),paint);
                Shape(car.shell,"Mirror glass",PrimitiveType.Cube,new Vector3(side*.98f,.90f,-.09f),new Vector3(.17f,.085f,.01f),chrome);
                for(int j=0;j<3;j++)Shape(car.shell,"Fender vent",PrimitiveType.Cube,new Vector3(side*.863f,.59f,.68f-j*.085f),new Vector3(.018f,.19f,.032f),black);
                var housing=Shape(car.shell,"Raised C4 pop-up headlight",PrimitiveType.Cube,new Vector3(side*.56f,.845f,1.64f),new Vector3(.445f,.225f,.34f),paint);
                housing.transform.localRotation=Quaternion.Euler(-12,0,0);
                Shape(car.shell,"Headlight rubber surround",PrimitiveType.Cube,new Vector3(side*.56f,.865f,1.818f),new Vector3(.397f,.185f,.026f),black);
            }
            Shape(car.shell,"Front intake",PrimitiveType.Cube,new Vector3(0,.40f,2.23f),new Vector3(1.4f,.10f,.035f),black);
            Shape(car.shell,"Front splitter",PrimitiveType.Cube,new Vector3(0,.29f,2.12f),new Vector3(1.72f,.045f,.27f),black);
            Shape(car.shell,"C4 rear bumper",PrimitiveType.Cube,new Vector3(0,.47f,-2.245f),new Vector3(1.54f,.16f,.025f),paint);
            Shape(car.shell,"Rear bumper rub strip",PrimitiveType.Cube,new Vector3(0,.525f,-2.266f),new Vector3(1.56f,.042f,.016f),black);
            Shape(car.shell,"Front bumper rub strip",PrimitiveType.Cube,new Vector3(0,.505f,2.235f),new Vector3(1.50f,.036f,.016f),black);
            var amber=Material(ghost?color:new Color(1,.35f,.025f),ghost);var red=Material(ghost?color:new Color(.82f,.025f,.018f),ghost);
            var lamp=Material(ghost?color:new Color(.92f,.96f,1),ghost);
            if(!ghost){Emissive(red,new Color(1,.01f,.005f),1.2f);Emissive(amber,new Color(1,.23f,.01f),.8f);Emissive(lamp,Color.white,1.3f);}
            for(int side=-1;side<=1;side+=2)
            {
                Shape(car.shell,"Rectangular pop-up headlamp lens",PrimitiveType.Cube,new Vector3(side*.56f,.865f,1.837f),new Vector3(.36f,.151f,.015f),lamp);
                Shape(car.shell,"Front running lamp",PrimitiveType.Cube,new Vector3(side*.57f,.48f,2.235f),new Vector3(.32f,.065f,.025f),lamp);
                Shape(car.shell,"Turn indicator",PrimitiveType.Cube,new Vector3(side*.79f,.48f,2.15f),new Vector3(.12f,.065f,.10f),amber);
                for(int i=0;i<2;i++)
                {
                    var light=Shape(car.shell,"Round C4 tail lamp",PrimitiveType.Cylinder,new Vector3(side*(.33f+i*.31f),.64f,-2.265f),new Vector3(.25f,.015f,.25f),red);light.transform.localRotation=Quaternion.Euler(90,0,0);
                    var exhaust=Shape(car.shell,"Exhaust tip",PrimitiveType.Cylinder,new Vector3(side*(.45f+i*.14f),.30f,-2.29f),new Vector3(.10f,.08f,.10f),chrome);exhaust.transform.localRotation=Quaternion.Euler(90,0,0);
                }
            }
            Shape(car.shell,"Rear license plate",PrimitiveType.Cube,new Vector3(0,.43f,-2.275f),new Vector3(.31f,.12f,.012f),chrome);
            for(int side=-1;side<=1;side+=2)
            {
                Quad(car.shell,"C4 rear sail panel",new Vector3(side*.62f,1.19f,-.91f),new Vector3(side*.70f,1.16f,-1.02f),new Vector3(side*.81f,.85f,-1.72f),new Vector3(side*.76f,.84f,-1.72f),paint);
                for(int axle=0;axle<2;axle++)
                {
                    float z=axle==0?1.22f:-1.22f;
                    var well=Shape(car.shell,"Recessed wheel well",PrimitiveType.Cylinder,new Vector3(side*.72f,.325f,z),new Vector3(.715f,.015f,.715f),black);well.transform.localRotation=Quaternion.Euler(0,0,90);
                }
                Shape(car.shell,"Rear quarter rub strip",PrimitiveType.Cube,new Vector3(side*.865f,.525f,-1.96f),new Vector3(.025f,.045f,.38f),black);
                Shape(car.shell,"Front quarter rub strip",PrimitiveType.Cube,new Vector3(side*.82f,.505f,1.98f),new Vector3(.025f,.036f,.32f),black);
            }
            var badge=new GameObject("CORVETTE rear lettering");badge.transform.SetParent(car.shell,false);badge.transform.localPosition=new Vector3(0,.64f,-2.287f);
            var lettering=badge.AddComponent<TextMesh>();lettering.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");badge.GetComponent<MeshRenderer>().sharedMaterial=lettering.font.material;
            lettering.text="C O R V E T T E";lettering.anchor=TextAnchor.MiddleCenter;lettering.fontSize=64;lettering.characterSize=.012f;lettering.color=new Color(.11f,.12f,.13f);
            if(ghost)badge.SetActive(false);
            // Exterior interior details are only visible through the side windows.

            Shape(car.shell,"Dashboard",PrimitiveType.Cube,new Vector3(0,.80f,.14f),new Vector3(1.36f,.18f,.40f),black);
            Shape(car.shell,"Instrument binnacle",PrimitiveType.Cube,new Vector3(-.34f,.90f,.025f),new Vector3(.48f,.17f,.10f),black);
            var gauge=Material(ghost?color:new Color(.15f,.8f,.65f),ghost);if(!ghost)Emissive(gauge,new Color(.06f,1,.65f),1);
            for(int i=0;i<3;i++)Shape(car.shell,"Digital instrument",PrimitiveType.Cube,new Vector3(-.49f+i*.15f,.91f,-.032f),new Vector3(.105f,.045f,.007f),gauge);
            Shape(car.shell,"Center console",PrimitiveType.Cube,new Vector3(0,.53f,-.38f),new Vector3(.26f,.24f,1.06f),black);
            var leather=Material(ghost?color:new Color(.15f,.115f,.095f),ghost);leather.SetFloat("_Metallic",0);leather.SetFloat("_Smoothness",.3f);
            for(int side=-1;side<=1;side+=2)
            {
                Shape(car.shell,"Sport seat cushion",PrimitiveType.Cube,new Vector3(side*.37f,.48f,-.64f),new Vector3(.48f,.16f,.63f),leather);
                var seat=Shape(car.shell,"Sport seat back",PrimitiveType.Cube,new Vector3(side*.37f,.77f,-1.01f),new Vector3(.48f,.62f,.13f),leather);seat.transform.localRotation=Quaternion.Euler(-12,0,0);
            }
            car.steeringWheel=new GameObject("Steering wheel input").transform;car.steeringWheel.SetParent(car.shell,false);car.steeringWheel.localPosition=new Vector3(-.34f,.88f,-.22f);
            Torus(car.steeringWheel,"Leather steering rim",Vector3.zero,.155f,.018f,black);
            Shape(car.steeringWheel,"Steering hub",PrimitiveType.Cube,Vector3.zero,new Vector3(.12f,.08f,.045f),black);
            for(int i=0;i<3;i++){var spoke=Shape(car.steeringWheel,"Steering spoke",PrimitiveType.Cube,Vector3.zero,new Vector3(.022f,.28f,.015f),darkMetal);spoke.transform.localRotation=Quaternion.Euler(0,0,i*120);}
            for(int i=0;i<4;i++)
            {
                float side=i%2==0?-1:1;
                var pivot=new GameObject("Wheel pivot").transform;pivot.SetParent(root.transform,false);pivot.localPosition=new Vector3(side*.84f,.325f,i<2?1.22f:-1.22f);
                var spin=new GameObject("Wheel rotation").transform;spin.SetParent(pivot,false);car.wheels[i]=spin;if(i<2)car.steering[i]=pivot;
                // Revolved tire with broad tread and rounded shoulders.
                int segments=48;float[] xs={-.15f,-.125f,.125f,.15f},rs={.255f,.325f,.325f,.255f};
                var vertices=new List<Vector3>();var triangles=new List<int>();
                for(int ring=0;ring<4;ring++)for(int j=0;j<segments;j++)
                {
                    float a=2*Mathf.PI*j/segments;vertices.Add(new Vector3(xs[ring],Mathf.Cos(a)*rs[ring],Mathf.Sin(a)*rs[ring]));
                    if(ring>0){int p=(ring-1)*segments+j,q=(ring-1)*segments+(j+1)%segments,u=ring*segments+j,v=ring*segments+(j+1)%segments;triangles.AddRange(new[]{p,q,u,q,v,u});}
                }
                MeshPart(spin,"Performance tire",vertices.ToArray(),triangles.ToArray(),rubber);
                var disc=Shape(spin,"Brake disc",PrimitiveType.Cylinder,new Vector3(side*.10f,0,0),new Vector3(.36f,.014f,.36f),darkMetal);disc.transform.localRotation=Quaternion.Euler(0,0,90);
                Torus(spin,"Polished rim lip",new Vector3(side*.152f,0,0),.234f,.013f,chrome,true);
                var hub=Shape(spin,"Alloy hub",PrimitiveType.Cylinder,new Vector3(side*.157f,0,0),new Vector3(.10f,.02f,.10f),chrome);hub.transform.localRotation=Quaternion.Euler(0,0,90);
                for(int j=0;j<5;j++)
                {
                    float a=j*72*Mathf.Deg2Rad;float outer=a+side*.32f;
                    Vector3 p0=new Vector3(side*.155f,Mathf.Cos(a-.28f)*.065f,Mathf.Sin(a-.28f)*.065f);
                    Vector3 p1=new Vector3(side*.155f,Mathf.Cos(a+.35f)*.065f,Mathf.Sin(a+.35f)*.065f);
                    Vector3 p2=new Vector3(side*.155f,Mathf.Cos(outer+.24f)*.227f,Mathf.Sin(outer+.24f)*.227f);
                    Vector3 p3=new Vector3(side*.155f,Mathf.Cos(outer-.06f)*.227f,Mathf.Sin(outer-.06f)*.227f);
                    if(side>0)Quad(spin,"Directional C4 sawblade alloy",p0,p3,p2,p1,chrome);else Quad(spin,"Directional C4 sawblade alloy",p0,p1,p2,p3,chrome);
                }
            }
            VisualTheme.Combine(car.shell,car.steeringWheel);
            var imported=Resources.Load<GameObject>("CorvetteC4");
            if(imported!=null)
            {
                foreach(Transform child in car.shell)child.gameObject.SetActive(false);
                var model=Object.Instantiate(imported,car.shell,false);model.name="Imported C4 body";
                foreach(var renderer in model.GetComponentsInChildren<Renderer>())
                {
                    string part=renderer.name.ToLowerInvariant();if(part.Contains("wheel")||part.Contains("tire")||part.Contains("tyre")||part.Contains("rim"))renderer.enabled=false;
                    if(ghost){var materials=new Material[renderer.sharedMaterials.Length];for(int i=0;i<materials.Length;i++)materials[i]=paint;renderer.sharedMaterials=materials;}
                }
                foreach(var collider in model.GetComponentsInChildren<Collider>())Object.Destroy(collider);
                foreach(var animator in model.GetComponentsInChildren<Animator>())animator.enabled=false;
            }
            car.BuildDriverInterior();
            if(ghost)foreach(var renderer in root.GetComponentsInChildren<Renderer>()){renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;}
            return car;
        }
        void BuildDriverInterior()
        {
            driverInterior=new GameObject("Unobstructed driver interior").transform;driverInterior.SetParent(transform,false);
            var trim=VisualTheme.Surface(new Color(.028f,.033f,.038f),.25f);
            var soft=VisualTheme.Surface(new Color(.08f,.085f,.085f),.22f);
            var gauge=VisualTheme.Surface(new Color(.06f,.46f,.34f),.3f);Emissive(gauge,new Color(.02f,.5f,.28f),.5f);
            Shape(driverInterior,"Low dashboard",PrimitiveType.Cube,new Vector3(0,.70f,.49f),new Vector3(1.39f,.17f,.48f),trim);
            Shape(driverInterior,"Driver instrument pod",PrimitiveType.Cube,new Vector3(-.33f,.775f,.37f),new Vector3(.47f,.12f,.12f),soft);
            for(int i=0;i<3;i++)Shape(driverInterior,"Driver gauge",PrimitiveType.Cube,new Vector3(-.48f+i*.15f,.79f,.303f),new Vector3(.105f,.035f,.008f),gauge);
            Shape(driverInterior,"Passenger dash trim",PrimitiveType.Cube,new Vector3(.38f,.735f,.245f),new Vector3(.55f,.025f,.018f),soft);
            driverWheel=new GameObject("Driver wheel input").transform;driverWheel.SetParent(driverInterior,false);driverWheel.localPosition=new Vector3(-.34f,.755f,.03f);
            Torus(driverWheel,"Driver steering rim",Vector3.zero,.13f,.014f,trim);
            Shape(driverWheel,"C4 steering hub",PrimitiveType.Cube,new Vector3(0,-.015f,0),new Vector3(.12f,.065f,.035f),soft);
            Shape(driverWheel,"Steering cross spoke",PrimitiveType.Cube,Vector3.zero,new Vector3(.24f,.023f,.018f),soft);
            Shape(driverWheel,"Steering lower spoke",PrimitiveType.Cube,new Vector3(0,-.07f,0),new Vector3(.025f,.12f,.018f),soft);
            foreach(var renderer in driverInterior.GetComponentsInChildren<Renderer>()){renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;}
            driverInterior.gameObject.SetActive(false);
        }
        public void SetDriverView(bool enabled)
        {
            if(driverInterior==null)return;
            driverInterior.gameObject.SetActive(enabled);shell.gameObject.SetActive(!enabled);
            foreach(var wheel in wheels)wheel.parent.gameObject.SetActive(!enabled);
        }
        public void Pose(float x,float y,float heading,float speed,float steer,bool immediate=false)
        {
            var position=new Vector3(x,.02f,y);var orientation=Quaternion.Euler(0,90-heading*Mathf.Rad2Deg,0);
            // PosePlayback already interpolated this render frame. A second low-pass causes stop/start motion.
            if(hasPose&&!immediate&&Vector3.Distance(position,lastPosition)<6)
                rotation+=Vector3.Dot(position-lastPosition,orientation*Vector3.forward)/.325f*Mathf.Rad2Deg;
            transform.SetPositionAndRotation(position,orientation);lastPosition=position;hasPose=true;
            foreach(var wheel in wheels)wheel.localRotation=Quaternion.Euler(rotation,0,0);
            foreach(var wheel in steering)wheel.localRotation=Quaternion.Euler(0,-steer*Mathf.Rad2Deg,0);
            shell.localRotation=Quaternion.Euler(0,0,Mathf.Clamp(-steer*speed*.5f,-3,3));
            if(steeringWheel!=null)steeringWheel.localRotation=Quaternion.Euler(0,0,steer*Mathf.Rad2Deg*4);
            if(driverWheel!=null)driverWheel.localRotation=Quaternion.Euler(0,0,steer*Mathf.Rad2Deg*4);
        }
    }
}
