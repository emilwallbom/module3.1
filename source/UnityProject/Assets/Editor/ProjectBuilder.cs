using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using CorvetteLab;

public static class ProjectBuilder
{
    public static void Prepare()
    {
        Directory.CreateDirectory("Assets/Settings");Directory.CreateDirectory("Assets/Scenes");Directory.CreateDirectory("Assets/Resources");
        if(!File.Exists("Assets/Resources/RacingPaint.mat"))AssetDatabase.CreateAsset(CarVisual.Material(Color.white),"Assets/Resources/RacingPaint.mat");
        if(!File.Exists("Assets/Resources/RacingGhost.mat"))AssetDatabase.CreateAsset(CarVisual.Material(new Color(1,1,1,.25f),true),"Assets/Resources/RacingGhost.mat");
        if(!File.Exists("Assets/Resources/RacingLine.mat"))AssetDatabase.CreateAsset(new Material(Shader.Find("CorvetteLab/SpeedLine")),"Assets/Resources/RacingLine.mat");
        var lineMaterial=AssetDatabase.LoadAssetAtPath<Material>("Assets/Resources/RacingLine.mat");
        lineMaterial.shader=Shader.Find("CorvetteLab/SpeedLine");EditorUtility.SetDirty(lineMaterial);
        const string pipelinePath="Assets/Settings/RacingURP.asset";
        var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(pipelinePath);
        if(pipeline==null)
        {
            var renderer=ScriptableObject.CreateInstance<UniversalRendererData>();
            AssetDatabase.CreateAsset(renderer,"Assets/Settings/RacingRenderer.asset");
            pipeline=UniversalRenderPipelineAsset.Create(renderer);
            pipeline.msaaSampleCount=2;pipeline.renderScale=1;pipeline.shadowDistance=65;
            pipeline.supportsHDR=false;pipeline.supportsCameraDepthTexture=false;pipeline.supportsCameraOpaqueTexture=false;
            AssetDatabase.CreateAsset(pipeline,pipelinePath);
        }
        GraphicsSettings.defaultRenderPipeline=pipeline;QualitySettings.renderPipeline=pipeline;
        pipeline.supportsHDR=true;pipeline.msaaSampleCount=2;pipeline.shadowDistance=95;
        var pipelineSettings=new SerializedObject(pipeline);pipelineSettings.FindProperty("m_SoftShadowsSupported").boolValue=true;pipelineSettings.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(pipeline);
        QualitySettings.vSyncCount=0;QualitySettings.shadowCascades=1;QualitySettings.shadowResolution=UnityEngine.ShadowResolution.Medium;
        PlayerSettings.companyName="Motion Planning Lab";PlayerSettings.productName="Corvette LMPC Racing Lab";
        PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
        PlayerSettings.runInBackground=true;PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64,new[]{GraphicsDeviceType.Direct3D11});
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        new GameObject("Corvette LMPC Laboratory",typeof(RacingApp));
        EditorSceneManager.SaveScene(scene,"Assets/Scenes/RacingLab.unity");
        EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/Scenes/RacingLab.unity",true)};
        AssetDatabase.SaveAssets();
        PresentationChecks.Run();
        Debug.Log("Racing project prepared successfully");
    }
    public static void Build()
    {
        Prepare();
        string root=Directory.GetParent(Application.dataPath).Parent.FullName;
        string output=Path.Combine(root,"builds","CorvetteLMPC","CorvetteLMPC.exe");Directory.CreateDirectory(Path.GetDirectoryName(output));
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Scenes/RacingLab.unity"},locationPathName=output,target=BuildTarget.StandaloneWindows64,options=BuildOptions.None});
        if(report.summary.result!=BuildResult.Succeeded)throw new System.Exception("Windows build failed: "+report.summary.result);
        Debug.Log("Windows build ready: "+output);
    }
}
