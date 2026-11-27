"""RBXL v0 static-only harvest, using the project's RBXM binary primitives.
Requires numpy, trimesh, optional lz4. Never executes or exports Lua or game data.
The map is licensed for project use; do not place generated assets in public git."""
import argparse,collections,hashlib,json,math,re,struct
from pathlib import Path
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial
from rbxm_animation import MAGIC,u32,string,references,interleaved,floats,rotation,lz4_block

SHA="0d383e8e4ee0b3162e79f856efc22e8fa00a213b477fd2a496b36f500388eed1"
SELECT={"furniture/office_desk":56158,"furniture/wood_bench":7103,"furniture/garage_shelf":54533,
"architecture/metal_door":653,"furniture/metal_table":15844,"furniture/folding_table":61468,
"architecture/window_frame_a":46468,"architecture/window_frame_b":47700,
"furniture/locker_room_bench":136,"architecture/door_panel_a":68144}
PARTS={"Part","Seat","MeshPart","UnionOperation","IntersectOperation","WedgePart","CornerWedgePart","TrussPart","VehicleSeat","SpawnLocation"}
REFS={"MeshId","TextureID","TextureId","Texture","ColorMap","NormalMap","RoughnessMap","MetalnessMap"}
LOOK={"Name","CFrame","size","Color3uint8","Material","shape","Transparency"}|REFS
VISUAL=PARTS|{"Texture","Decal","SurfaceAppearance","SpecialMesh","Model","Folder"}
def chunks(raw):
    assert raw[:14]==MAGIC and raw[14:16]==b"\0\0"
    try:
        from lz4.block import decompress
        unpack=lambda b,n:decompress(b,uncompressed_size=n)
    except ImportError:unpack=lz4_block
    pos=32
    while pos<len(raw):
        tag,c,n,_=struct.unpack_from("<4sIII",raw,pos);pos+=16
        assert n<=128*1024*1024 and pos+(c or n)<=len(raw)
        data=raw[pos:pos+(c or n)];pos+=c or n
        # Never decode shared CSG payloads, scripts or unneeded services.
        if tag not in (b"INST",b"PROP",b"PRNT",b"END\0"):continue
        if c:data=unpack(data,n)
        yield tag,data
        if tag==b"END\0":assert pos==len(raw);return
    raise ValueError("missing END")
def cf(d,n):
    j=0;rs=[]
    for _ in range(n):
        code=d[j];j+=1
        if code:rs.append(rotation(code))
        else:rs.append(struct.unpack_from("<9f",d,j));j+=36
    assert len(d)==j+12*n
    xyz=[floats(d[j+4*n*k:j+4*n*(k+1)],n) for k in range(3)]
    return [(np.array(r).reshape(3,3),np.array([a[i] for a in xyz])) for i,r in enumerate(rs)]
def read(raw):
    cls={};props={};parent={}
    for tag,d in chunks(raw):
        if tag==b"INST":
            k=u32(d,0);name,j=string(d,4);n=u32(d,j+1);cls[k]=(name,references(d[j+5:j+5+4*n],n))
        elif tag==b"PROP":
            k=u32(d,0);name,j=string(d,4)
            if name in LOOK:props[k,name]=(d[j],d[j+1:])
        elif tag==b"PRNT":
            n=u32(d,1);parent=dict(zip(references(d[5:5+4*n],n),references(d[5+4*n:],n)))
    nodes={i:{"class":c,"parent":parent[i]} for c,ids in cls.values() for i in ids}
    assert len(cls)==u32(raw,16) and len(nodes)==u32(raw,20)==len(parent)
    for (k,name),(typ,d) in props.items():
        c,ids=cls[k];n=len(ids)
        if name!="Name" and c not in VISUAL:continue
        if typ==1:
            j=0;values=[]
            for _ in ids:v,j=string(d,j);values.append(v)
            assert j==len(d)
        elif typ==16:values=cf(d,n)
        elif typ==14:values=list(zip(*(floats(d[4*n*j:4*n*(j+1)],n) for j in range(3))))
        elif typ==26:values=np.frombuffer(d,dtype=np.uint8).reshape(3,n).T
        elif typ==18:values=interleaved(d,n)
        elif typ==4:values=floats(d,n)
        else:continue
        for i,v in zip(ids,values):nodes[i][name]=v
    return cls,nodes
def harvest(raw,out):
    assert hashlib.sha256(raw).hexdigest()==SHA,"different source, review selection IDs"
    cls,nodes=read(raw);children=collections.defaultdict(list)
    for i,n in nodes.items():children[n["parent"]].append(i)
    def desc(i):
        todo=children[i].copy()
        while todo:
            x=todo.pop();yield x;todo.extend(children[x])
    def path(i):
        ns=[]
        while i in nodes and len(ns)<30:ns.append(nodes[i]["Name"]);i=nodes[i]["parent"]
        return "/".join(reversed(ns))
    out.mkdir(parents=True,exist_ok=True)
    manifest={"source_sha256":SHA,"source_bytes":len(raw),"creator":"LoneWolf_Alfa","units":"studs, glTF Y-up","assets":[]}
    for key,i in SELECT.items():
        assert path(i).startswith("Workspace/")
        scene=trimesh.Scene();items=[];omitted=[];records=[]
        for j in desc(i):
            n=nodes[j];c=n["class"]
            if c not in PARTS:continue
            if n["Transparency"]>=.999:omitted.append(j);continue
            shape=n.get("shape",1)
            assert c in ("Part","Seat") and shape in (0,1,2),(j,c,shape)
            mesh=trimesh.creation.box() if shape==1 else trimesh.creation.icosphere(subdivisions=2,radius=.5) if shape==0 else trimesh.creation.cylinder(radius=.5,height=1,sections=24)
            if shape==2:mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[0,1,0]))
            r,t=n["CFrame"];size=np.asarray(n["size"]);assert np.isfinite(size).all() and (size>0).all() and np.isfinite(t).all() and np.max(np.abs(r.T@r-np.eye(3)))<.002
            matrix=np.eye(4);matrix[:3,:3]=r;matrix[:3,3]=t;mesh.apply_scale(size);mesh.apply_transform(matrix)
            rgb=tuple(int(v) for v in n["Color3uint8"]);alpha=round(255*(1-n["Transparency"]));mat=n["Material"]
            mesh.visual=trimesh.visual.TextureVisuals(material=PBRMaterial(name=f"Roblox {mat} RGB {rgb}",baseColorFactor=(*rgb,alpha),roughnessFactor=.35 if mat in (1088,1056,1568) else .75,metallicFactor=.5 if mat in (1088,1056) else 0,alphaMode="BLEND" if alpha<255 else "OPAQUE"))
            items.append((j,mesh));records.append({"id":j,"name":n["Name"],"shape":shape,"size":size.tolist(),"rotation":r.tolist(),"translation":t.tolist(),"color":rgb,"transparency":n["Transparency"],"material":mat})
        bounds=np.array([m.bounds for _,m in items]);lo=bounds[:,0].min(0);hi=bounds[:,1].max(0);origin=(lo+hi)/2;origin[1]=lo[1]
        for j,mesh in items:mesh.apply_translation(-origin);scene.add_geometry(mesh,node_name=f"part_{j}",geom_name=f"part_{j}")
        target=out/(key+".glb");target.parent.mkdir(exist_ok=True);target.write_bytes(scene.export(file_type="glb"))
        assert len(trimesh.load(target,force="scene").geometry)==len(items)
        manifest["assets"].append({"asset":key,"file":key+".glb","source_id":i,"source_path":path(i),"parts":len(items),"omitted":omitted,"source_bounds_studs":(hi-lo).tolist(),"source_parts":records})
    manifest["class_counts"]={c:len(ids) for c,ids in cls.values()}
    manifest["external_refs"]={k:sorted({n[k] for n in nodes.values() if isinstance(n.get(k),str) and n[k]}) for k in REFS}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("HARVEST",len(manifest["assets"]),sum(x["parts"] for x in manifest["assets"]))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args();harvest(a.source.read_bytes(),a.output)
