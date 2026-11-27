using System.IO;
using UnityEditor;
using UnityEngine;

public static class C4Importer
{
    [MenuItem("Tools/Corvette Lab/Import licensed C4 FBX")]
    public static void Import()
    {
        string source=EditorUtility.OpenFilePanel("Select your licensed C4 FBX model","","fbx");
        if(string.IsNullOrEmpty(source))return;
        const string folder="Assets/CarModel";
        Directory.CreateDirectory(folder);Directory.CreateDirectory("Assets/Resources");
        string destination=folder+"/CorvetteC4.fbx";
        File.Copy(source,destination,true);
        foreach(string texture in Directory.GetFiles(Path.GetDirectoryName(source)))
        {
            string extension=Path.GetExtension(texture).ToLowerInvariant();
            if(extension==".png"||extension==".jpg"||extension==".jpeg"||extension==".tga")File.Copy(texture,folder+"/"+Path.GetFileName(texture),true);
        }
        AssetDatabase.Refresh();AssetDatabase.ImportAsset(destination,ImportAssetOptions.ForceSynchronousImport);
        var sourceModel=AssetDatabase.LoadAssetAtPath<GameObject>(destination);
        if(sourceModel==null)throw new System.Exception("Unity could not import the FBX model");
        var root=new GameObject("CorvetteC4");
        var model=Object.Instantiate(sourceModel,root.transform);
        Bounds bounds=BoundsOf(model);
        if(bounds.size.x>bounds.size.z)model.transform.localRotation=Quaternion.Euler(0,90,0);
        bounds=BoundsOf(model);
        model.transform.localScale*=4.48f/Mathf.Max(.01f,bounds.size.z);
        bounds=BoundsOf(model);
        model.transform.position+=new Vector3(-bounds.center.x,.04f-bounds.min.y,-bounds.center.z);
        int index=0;
        foreach(var renderer in model.GetComponentsInChildren<Renderer>())
        {
            var materials=renderer.sharedMaterials;
            for(int i=0;i<materials.Length;i++)
            {
                var original=materials[i];var material=new Material(Shader.Find("Universal Render Pipeline/Lit"));
                if(original!=null)
                {
                    material.SetColor("_BaseColor",original.HasProperty("_BaseColor")?original.GetColor("_BaseColor"):original.HasProperty("_Color")?original.color:Color.gray);
                    var texture=original.HasProperty("_BaseMap")?original.GetTexture("_BaseMap"):original.mainTexture;
                    if(texture!=null)material.SetTexture("_BaseMap",texture);
                }
                string materialPath=AssetDatabase.GenerateUniqueAssetPath(folder+"/ImportedMaterial"+(index++)+".mat");
                AssetDatabase.CreateAsset(material,materialPath);materials[i]=material;
            }
            renderer.sharedMaterials=materials;
        }
        PrefabUtility.SaveAsPrefabAsset(root,"Assets/Resources/CorvetteC4.prefab");
        Object.DestroyImmediate(root);AssetDatabase.SaveAssets();
        EditorUtility.DisplayDialog("C4 model imported","The body is normalized to 4.48 m and will be used at the next launch. Front/rear orientation and wheel mesh names should be checked in the prefab. Add the model author's attribution before sharing a build.","OK");
    }
    static Bounds BoundsOf(GameObject model)
    {
        var renderers=model.GetComponentsInChildren<Renderer>();
        if(renderers.Length==0)throw new System.Exception("Model contains no rendered geometry");
        Bounds bounds=renderers[0].bounds;foreach(var renderer in renderers)bounds.Encapsulate(renderer.bounds);return bounds;
    }
}
