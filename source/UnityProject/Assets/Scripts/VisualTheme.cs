using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace CorvetteLab
{
    // Original procedural artwork; all randomness is local and independent of training.
    public static class VisualTheme
    {
        public static Material Surface(Color color,float smoothness=.18f,float metallic=0)
        {
            var m=CarVisual.Material(color);m.SetFloat("_Smoothness",smoothness);m.SetFloat("_Metallic",metallic);return m;
        }
        public static Material Grain(Color color,int seed,float amount,float repeat)
        {
            var m=Surface(color);var rng=new System.Random(seed);
            var tex=new Texture2D(256,256,TextureFormat.RGB24,true){name="Original circuit surface",wrapMode=TextureWrapMode.Repeat,anisoLevel=8};
            var pixels=new Color[256*256];
            for(int y=0;y<256;y++)for(int x=0;x<256;x++)
            {
                float noise=(float)rng.NextDouble()-.5f;
                float broad=Mathf.PerlinNoise(x*.045f+seed,y*.045f)*2-1;
                pixels[y*256+x]=Color.white*(1+amount*(noise+broad*.35f));
            }
            tex.SetPixels(pixels);tex.Apply();m.SetTexture("_BaseMap",tex);m.SetTextureScale("_BaseMap",Vector2.one*repeat);return m;
        }
        public static void Lighting(Camera camera)
        {
            camera.allowHDR=true;camera.backgroundColor=new Color(.54f,.66f,.76f);
            var sun=Object.FindFirstObjectByType<Light>();
            if(sun==null)sun=new GameObject("Circuit sun").AddComponent<Light>();
            sun.type=LightType.Directional;sun.intensity=2.2f;sun.color=new Color(1,.91f,.77f);
            sun.shadows=LightShadows.Soft;sun.shadowStrength=.8f;sun.shadowBias=.035f;sun.shadowNormalBias=.25f;
            sun.transform.rotation=Quaternion.Euler(32,-38,0);
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=new Color(.57f,.68f,.84f);
            RenderSettings.ambientEquatorColor=new Color(.42f,.46f,.49f);
            RenderSettings.ambientGroundColor=new Color(.21f,.24f,.17f);
            RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;
            RenderSettings.fogDensity=.0018f;RenderSettings.fogColor=new Color(.66f,.74f,.79f);
            var sky=new Material(Shader.Find("Skybox/Procedural"));
            sky.SetFloat("_SunSize",.035f);sky.SetFloat("_AtmosphereThickness",.85f);
            sky.SetColor("_SkyTint",new Color(.55f,.62f,.72f));sky.SetColor("_GroundColor",new Color(.34f,.38f,.29f));
            RenderSettings.skybox=sky;RenderSettings.sun=sun;camera.clearFlags=CameraClearFlags.Skybox;
            var volume=new GameObject("Circuit color grading").AddComponent<Volume>();volume.isGlobal=true;volume.priority=10;
            var profile=ScriptableObject.CreateInstance<VolumeProfile>();volume.profile=profile;
            var tone=profile.Add<Tonemapping>();tone.mode.Override(TonemappingMode.ACES);
            var color=profile.Add<ColorAdjustments>();color.postExposure.Override(.12f);color.contrast.Override(12);color.saturation.Override(-5);
            var bloom=profile.Add<Bloom>();bloom.threshold.Override(1.5f);bloom.intensity.Override(.12f);bloom.scatter.Override(.35f);
            var vignette=profile.Add<Vignette>();vignette.intensity.Override(.16f);vignette.smoothness.Override(.6f);
            camera.GetUniversalAdditionalCameraData().renderPostProcessing=true;
        }
        public static void Combine(Transform parent,Transform animated=null)
        {
            // Batch static primitives by material to keep four-car comparison inexpensive.
            var groups=new System.Collections.Generic.Dictionary<Material,System.Collections.Generic.List<CombineInstance>>();
            var sources=parent.GetComponentsInChildren<MeshFilter>();
            foreach(var source in sources)
            {
                if(animated!=null&&source.transform.IsChildOf(animated))continue;
                var renderer=source.GetComponent<MeshRenderer>();
                if(renderer==null||renderer.sharedMaterials.Length!=1)continue;
                var material=renderer.sharedMaterial;
                if(!groups.ContainsKey(material))groups[material]=new System.Collections.Generic.List<CombineInstance>();
                groups[material].Add(new CombineInstance{mesh=source.sharedMesh,transform=parent.worldToLocalMatrix*source.transform.localToWorldMatrix});
                renderer.enabled=false;
            }
            foreach(var pair in groups)
            {
                var mesh=new Mesh{indexFormat=IndexFormat.UInt32};mesh.CombineMeshes(pair.Value.ToArray());
                var go=new GameObject("Batched "+pair.Key.name,typeof(MeshFilter),typeof(MeshRenderer));go.transform.SetParent(parent,false);
                go.GetComponent<MeshFilter>().sharedMesh=mesh;go.GetComponent<MeshRenderer>().sharedMaterial=pair.Key;
            }
        }
    }
}
