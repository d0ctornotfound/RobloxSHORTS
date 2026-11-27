"""Attempt public Roblox asset delivery, parse only verified static FileMesh geometry.
No credentials or access-control bypass. No publication of independently referenced
third-party mesh files without their licensing being established separately.
Format reference: https://devforum.roblox.com/t/roblox-filemesh-format-specification/326114
"""
import concurrent.futures,hashlib,json,re,struct
from pathlib import Path
import numpy as np
import requests
import trimesh

out=Path("render/mesh-resolution");out.mkdir(parents=True,exist_ok=True)
models=json.loads(Path("assets/harvest/mesh_priority.json").read_text())
ids=sorted({i for m in models for i in m["mesh_ids"]})
assert len(ids)==38

def decode(raw):
    sig,_,d=raw.partition(b"\n");assert re.fullmatch(rb"version [1-5]\.0[01]",sig),("unsupported payload",sig[:40])
    version=float(sig.split()[-1])
    if version<2:
        count,_,data=d.partition(b"\n");nf=int(count);assert 0<nf<=2000000
        vals=np.array([[float(x) for x in a.split(b",")] for a in re.findall(rb"\[([^\]]+)\]",data)])
        assert vals.shape==(nf*9,3)
        verts=vals[::3]*(.5 if version==1.0 else 1);norm=vals[1::3];uv=vals[2::3,:2];faces=np.arange(nf*3).reshape(-1,3);colors=None
    else:
        h=struct.unpack_from("<H",d)[0];lods=0;skin=0
        if version<3:
            _,vs,fs,nv,nf=struct.unpack_from("<HBBII",d);assert h==12
        elif version<4:
            _,vs,fs,lod_size,lods,nv,nf=struct.unpack_from("<HBBHHII",d);assert h==16 and lod_size==4
        else:
            _,_,nv,nf,lods,bones=struct.unpack_from("<HHIIHH",d)
            assert h in (24,32);assert bones==0,"skinned mesh deferred for static review"
            vs,fs=40,12
        assert vs in (36,40) and fs==12 and 0<nv<=2000000 and 0<nf<=2000000
        end=h+nv*vs;face_end=end+nf*12;assert face_end+lods*4<=len(d)
        xyz=np.ndarray((nv,8),dtype="<f4",buffer=d,offset=h,strides=(vs,4)).copy()
        verts,norm,uv=xyz[:,:3],xyz[:,3:6],xyz[:,6:8]
        colors=np.ndarray((nv,4),dtype=np.uint8,buffer=d,offset=h+36,strides=(vs,1)).copy() if vs==40 else None
        faces=np.frombuffer(d,dtype="<u4",count=nf*3,offset=end).reshape(-1,3).copy()
        if lods>=2:
            bounds=np.frombuffer(d,dtype="<u4",count=lods,offset=face_end);assert bounds[0]==0 and 0<bounds[1]<=nf
            faces=faces[:bounds[1]]
    assert np.isfinite(verts).all() and np.isfinite(uv).all() and len(faces)>0 and faces.max()<len(verts)
    assert np.ptp(verts,axis=0).max()>0
    mesh=trimesh.Trimesh(vertices=verts,faces=faces,process=False)
    # Retain the source UVs; glTF convention differs from the mesh source.
    uv=uv.copy();uv[:,1]=1-uv[:,1]
    mesh.visual=trimesh.visual.TextureVisuals(uv=uv,material=trimesh.visual.material.PBRMaterial(name="Untextured source mesh"))
    if colors is not None:mesh.visual.vertex_attributes["color"]=colors
    return mesh,sig.decode()

def attempt(i):
    url=f"https://assetdelivery.roblox.com/v1/asset/?id={i}";row={"id":i,"url":url,"resolved":False}
    try:
        with requests.get(url,timeout=(8,20),stream=True,allow_redirects=True) as response:
            row.update(status=response.status_code,content_type=response.headers.get("Content-Type"))
            if response.status_code!=200:return row
            chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>20*1024*1024:raise ValueError("payload exceeds size bound")
                chunks.append(chunk)
            raw=b"".join(chunks)
        row["bytes"]=len(raw);row["payload_sha256"]=hashlib.sha256(raw).hexdigest()
        mesh,version=decode(raw)
        target=out/(str(i)+".glb");target.write_bytes(mesh.export(file_type="glb"))
        assert len(trimesh.load(target,force="scene").geometry)==1
        row.update(resolved=True,version=version,vertices=len(mesh.vertices),faces=len(mesh.faces),file=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    except Exception as e:row["error"]=str(e)[:600]
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(attempt,ids))
byid={r["id"]:r for r in rows}
for m in models:
    m["resolved_components"]=sum(byid[i]["resolved"] for i in m["mesh_ids"])
    m["all_mesh_components_resolved"]=m["resolved_components"]==len(m["mesh_ids"])
(out/"resolution.json").write_text(json.dumps({"models":models,"requests":rows},indent=2)+"\n")
print("MESH_RESOLUTION",json.dumps({"attempted":len(rows),"resolved":sum(r["resolved"] for r in rows),"status_counts":{str(s):sum(r.get("status")==s for r in rows) for s in set(r.get("status") for r in rows)},"models":models}),flush=True)
