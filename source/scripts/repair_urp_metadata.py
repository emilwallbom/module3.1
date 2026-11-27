"""Repair two absent .meta files in the official 6000.3.29f1 URP package.

Unity logs that these C# sources are ignored in an immutable package, then
fails to compile ReadonlyMaterialConverter. No vendor source is changed.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def repair():
    version=json.loads((ROOT/"tools-lock.json").read_text())["unity_version"]
    roots=[ROOT/".tools"/"unity"/version/"Editor"/"Data"/"Resources"/"PackageManager"/"BuiltInPackages"/"com.unity.render-pipelines.universal"]
    roots+=list((ROOT/"UnityProject"/"Library"/"PackageCache").glob("com.unity.render-pipelines.universal@*"))
    for package in roots:
        for name in ["ReadonlyMaterialConverter.MaterialReferenceBuilder.cs","ReadonlyMaterialConverter.MaterialReferenceChanger.cs"]:
            source=package/"Editor"/"Tools"/"Converters"/"ReadonlyMaterialConverter"/name
            meta=Path(str(source)+".meta")
            if source.exists() and not meta.exists():
                guid=hashlib.md5(("corvette-lab-urp-metadata-"+name).encode()).hexdigest()
                meta.write_text(f"fileFormatVersion: 2\nguid: {guid}\n",encoding="utf-8")
                print(f"Added missing metadata: {meta}")


if __name__=="__main__":repair()
