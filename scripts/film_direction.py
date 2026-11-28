"""Story-independent direction preset and evaluated pose sampling.
No cast IDs, shot numbers, location names or story actions belong here.
"""
import math
from mathutils import Vector
import bpy
from library_camera import project
from r6_character import mesh_points

PRESET = "warm_saturated_v1"
def apply_grade(scene, name):
    if name != PRESET: raise ValueError("unknown grade "+str(name))
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -.12
    for ob in scene.objects:
        if ob.type != "LIGHT": continue
        d=ob.data
        if d.type=="SUN":
            d.color=(1,.84,.65);d.angle=max(d.angle,.20)
        elif d.type=="AREA":
            d.color=tuple(.65*x+.35*y for x,y in zip(d.color,(1,.87,.73)))
            d.size=max(d.size,2.0)
    scene.use_nodes=True
    nt=scene.node_tree
    # Preserve an existing composite chain: insert directly upstream of output.
    comp=next((n for n in nt.nodes if n.type=="COMPOSITE"),None)
    if comp is None: raise RuntimeError("grade requires compositor output")
    inp=comp.inputs["Image"]
    if not inp.is_linked: raise RuntimeError("grade requires existing image source")
    link=inp.links[0];src=link.from_socket;nt.links.remove(link)
    sat=nt.nodes.new("CompositorNodeHueSat");sat.name=PRESET
    sat.inputs["Saturation"].default_value=1.18
    nt.links.new(src,sat.inputs["Image"]);nt.links.new(sat.outputs["Image"],inp)
    return {"preset":name,"look":scene.view_settings.look,"exposure":-.12,"saturation":1.18}

def pose_signature(actor):
    # World-space evaluated bone landmarks (joint + three orientation points).
    # Independent of camera movement and image encoding.
    pts=[]
    for name,b in sorted(actor.bones.items()):
        m=actor.armature.matrix_world @ b.matrix
        pts.extend(list(m @ Vector(v)) for v in ((0,0,0),(.15,0,0),(0,.15,0),(0,0,.15)))
    return pts

def face_points(actor):
    return mesh_points(actor.face)

def center(points):
    return sum((Vector(p) for p in points),Vector((0,0,0)))/len(points)

def direct_camera(scene,cam,actors,spec,u,frame):
    """Absolute shot-local camera with explicit motivation; preserve the selected axis.
    A camera fit is not a landmark/visibility or continuity proof.
    """
    kind=spec["beat_type"]
    ids=[spec["principal"]]+spec.get("listeners",[])
    if any(i not in actors for i in ids): raise ValueError("missing directed actor")
    move=spec.get("camera_move")
    if not move or (move=="locked" and not spec.get("lock_reason")): raise ValueError("camera motivation missing")
    if move=="locked": return
    if move not in ("push","drift","track"): raise ValueError("unknown camera move")
    if kind in ("emotion","interview","action"):
        pts=[p for i in (ids if kind=="interview" else ids[:1]) for p in face_points(actors[i])]
        target=center(pts)
        if kind=="action": target.z-=spec.get("action_target_drop",.65)
        # Explicit authored offset is preferred; otherwise use the established camera axis.
        axis=Vector(spec.get("camera_offset",list(cam.location-target)))
        axis.z=spec.get("camera_elevation",0.12)
        if axis.length<.1:raise ValueError("degenerate directed camera")
        direction=axis.normalized()
        dist=spec.get("distance",4.0)
        lens=spec.get("lens",42)
        pos=target+direction*dist
        frame(scene,cam,pos,target,lens)
        b=project(scene,cam,pts)
        if kind=="emotion" and b[4]>0:
            desired=.44
            ratio=max(.001,b[3]-b[2])
            lens=max(12,min(120,lens*desired/ratio))
        if kind=="interview" and b[4]>0:
            span=max(.001,b[1]-b[0]);height=max(.001,b[3]-b[2])
            lens=max(12,min(100,lens*min(.78/span,.55/height)))
        if move=="push":pos-=direction*(.10*u)
        if move=="drift":
            lateral=Vector((-direction.y,direction.x,0));pos+=lateral*(.16*(u-.5))
        frame(scene,cam,pos,target,lens)
    else:
        raise ValueError("compose explicit geography/diagram camera; lock reason required for fixed registration")

def sample(scene,cam,actors,spec,grade):
    ids=[spec["principal"]]+spec.get("listeners",[])
    result={"beat_type":spec["beat_type"],"principal":spec["principal"],"listeners":spec.get("listeners",[]),"camera_move":spec.get("camera_move"),"grade":grade,"actors":{}}
    for cid,a in actors.items():
        f=project(scene,cam,face_points(a))
        result["actors"][cid]={"pose":pose_signature(a),"face_height":max(0,min(1,f[3])-max(0,f[2])),"face_safe":f[4]>0 and .025<=f[0]<=f[1]<=.975 and .025<=f[2]<=f[3]<=.975}
    return result
