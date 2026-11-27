"""Assemble resolved MCRD static geometry at original map size/orientation.
Use verified GLBs from mesh probe and attempt image textures without credentials.
No game content or stand-ins. Preserve source asset IDs and original map terms."""
import hashlib,io,json
from pathlib import Path
import numpy as np, requests, trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial
root=Path("assets/harvest")
probe=Path("mesh_probe")
records=json.loads((root/"resolved_mesh_sources.json").read_text())
manifest=[]
for r in records:
    src=probe/(str(r["id"])+".glb")
    assert hashlib.sha256(src.read_bytes()).hexdigest()==r["raw_sha"]
    mesh=trimesh.load(src,force="scene").to_mesh()
    bounds=mesh.bounds.copy();extent=mesh.extents.copy();assert (extent>0).all()
    mesh.apply_translation(-bounds.mean(0));mesh.apply_scale(np.array(r["size"])/extent)
    transform=np.eye(4);transform[:3,:3]=np.array(r["rotation"]);mesh.apply_transform(transform)
    bounds=mesh.bounds.copy();origin=bounds.mean(0);origin[1]=bounds[0,1];mesh.apply_translation(-origin)
    texture=None;status={"id":r["texture_id"],"resolved":False}
    try:
        with requests.get(f'https://assetdelivery.roblox.com/v1/asset/?id={r["texture_id"]}',timeout=(8,20),stream=True) as resp:
            status["http_status"]=resp.status_code
            if resp.status_code==200:
                data=bytearray()
                for chunk in resp.iter_content(65536):
                    data.extend(chunk)
                    if len(data)>20*1024*1024:raise ValueError("texture too large")
                im=Image.open(io.BytesIO(data));assert im.width*im.height<=16777216
                im.load();texture=im.convert("RGBA")
                status.update(resolved=True,sha256=hashlib.sha256(data).hexdigest(),size=list(im.size))
    except Exception as e:status["error"]=str(e)[:400]
    uv=mesh.visual.uv.copy()
    material=PBRMaterial(name="Source map material; texture "+("resolved" if texture is not None else "unavailable"),baseColorFactor=(*r["color"],255),baseColorTexture=texture,roughnessFactor=.75,alphaMode="BLEND" if texture is not None and texture.getextrema()[-1][0]<255 else "OPAQUE")
    mesh.visual=trimesh.visual.TextureVisuals(uv=uv,material=material)
    target=root/(r["asset"]+".glb");target.parent.mkdir(exist_ok=True);target.write_bytes(mesh.export(file_type="glb"))
    assert len(trimesh.load(target,force="scene").geometry)==1
    manifest.append(dict(r,texture=status,triangles=len(mesh.faces),bounds_studs=mesh.extents.tolist(),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
(root/"second_pass_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
(root/"mesh_resolution.json").write_bytes((probe/"resolution.json").read_bytes())
print("HARVEST_SECOND_PASS",json.dumps(manifest),flush=True)
