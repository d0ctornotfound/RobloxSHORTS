"""Reproduce harvested source geometry from verified exact float32 extraction.
No source RBXL or game logic is published. Original map terms/credit retained."""
import base64,hashlib,json,math,struct,zlib
from pathlib import Path
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial
root=Path("assets/harvest")
data=json.loads((root/"primitive_source.json").read_text())
raw=zlib.decompress(base64.b64decode(data["packed"]))
assert hashlib.sha256(raw).hexdigest()==data["raw_sha256"] and len(raw)==14212
records=iter(struct.iter_unpack("<IB15f3BfI",raw))
manifest={"source_sha256":data["source_sha256"],"creator":data["creator"],"assets":[]}
for key,source,count,expected in data["models"]:
    meshes=[]
    for _ in range(count):
        p=next(records);j,shape=p[:2];size=np.array(p[2:5]);r=np.array(p[5:14]).reshape(3,3);t=np.array(p[14:17]);rgb=tuple(p[17:20]);transparency,mat=p[20:22]
        assert shape in (1,2) and np.isfinite(size).all() and (size>0).all()
        mesh=trimesh.creation.box() if shape==1 else trimesh.creation.cylinder(radius=.5,height=1,sections=24)
        if shape==2:mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[0,1,0]))
        mesh.apply_scale(size);matrix=np.eye(4);matrix[:3,:3]=r;matrix[:3,3]=t;mesh.apply_transform(matrix)
        alpha=round(255*(1-float(transparency)))
        mesh.visual=trimesh.visual.TextureVisuals(material=PBRMaterial(name=f'Roblox material {mat} RGB {rgb}',baseColorFactor=(*rgb,alpha),roughnessFactor=.35 if mat in (1088,1056,1568) else .75,metallicFactor=.5 if mat in (1088,1056) else 0,alphaMode='BLEND' if alpha<255 else 'OPAQUE'))
        meshes.append((j,mesh))
    bounds=np.array([m.bounds for _,m in meshes]);lo=bounds[:,0].min(0);hi=bounds[:,1].max(0);origin=(lo+hi)/2;origin[1]=lo[1]
    scene=trimesh.Scene()
    for j,m in meshes:m.apply_translation(-origin);scene.add_geometry(m,node_name=f'part_{j}',geom_name=f'part_{j}')
    target=root/(key+".glb");target.parent.mkdir(exist_ok=True);target.write_bytes(scene.export(file_type="glb"))
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    assert len(trimesh.load(target,force="scene").geometry)==count
    # Byte identity is required to claim the original extraction, not just
    # geometry equivalence. Pin original exporter versions in CI.
    assert digest==expected,(key,digest,expected)
    manifest["assets"].append({"asset":key,"source_id":source,"parts":count,"sha256":digest,"source_bounds_studs":(hi-lo).tolist()})
assert next(records,None) is None
(root/"published_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print("HARVEST_PUBLISH",json.dumps(manifest),flush=True)
