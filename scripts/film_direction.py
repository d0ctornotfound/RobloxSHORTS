"""Story-independent direction preset and evaluated pose sampling.
No cast IDs, shot numbers, location names or story actions belong here.
"""
import math
from mathutils import Vector, Euler, Matrix
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
    # The face decal corners are actual evaluated surface landmarks, not
    # tiny bone-axis probes; keep the original points and threshold.
    pts.extend(list(p) for p in mesh_points(actor.face))
    return pts

def face_points(actor):
    return mesh_points(actor.face)

def center(points):
    return sum((Vector(p) for p in points),Vector((0,0,0)))/len(points)

def face_facing(actor,cam):
    p=face_points(actor)
    if len(p)<4:return -1.
    normal=(p[1]-p[0]).cross(p[3]-p[0]).normalized()
    return float(normal.dot((cam.location-center(p)).normalized()))

def direct_camera(scene,cam,actors,spec,u,frame,state=None):
    """Deterministic shot-local framing. Fit once at entry, not every sample;
    track root translation, not involuntary head wobble. Explicit authored
    camera axis is checked by actual front/visibility QC after positioning."""
    kind=spec["beat_type"]
    ids=[i for i in [spec["principal"]]+spec.get("listeners",[]) if i is not None]
    if any(i not in actors for i in ids):raise ValueError("missing directed actor")
    if not ids and not (spec.get("pure_establishing") and spec.get("camera_path")):raise ValueError("actorless camera requires explicit establishing path")
    move=spec.get("camera_move")
    if not move or (move=="locked" and not spec.get("lock_reason")):raise ValueError("camera motivation missing")
    if move=="locked":return
    if spec.get("camera_path"):
        keys=spec["camera_path"]
        if any(x["u"]>=y["u"] for x,y in zip(keys,keys[1:])):raise ValueError("camera path keys not increasing")
        a,b=keys[0],keys[-1]
        for x,y in zip(keys,keys[1:]):
            if x["u"]<=u<=y["u"]:a,b=x,y;break
        w=max(0,min(1,(u-a["u"])/max(.0001,b["u"]-a["u"])))
        frame(scene,cam,Vector(a["position"]).lerp(Vector(b["position"]),w),Vector(a["target"]).lerp(Vector(b["target"]),w),a["lens"]+(b["lens"]-a["lens"])*w)
        return
    if move not in ("push","drift","track","reframe"):raise ValueError("unknown camera move")
    if kind not in ("emotion","interview","action","geography"):raise ValueError("explicit diagram/other camera required")
    if state is None:state={}
    principal=actors[ids[0]]
    if not state:
        pts=[p for i in (ids if kind=="interview" else ids[:1]) for p in face_points(actors[i])]
        target=center(pts)
        if kind in ("action","geography"):target.z-=spec.get("action_target_drop",.65)
        target+=Vector(spec.get("target_offset",[0,0,0]))
        axis=Vector(spec.get("camera_offset",list(cam.location-target)))
        axis.z=spec.get("camera_elevation",.12)
        if axis.length<.1:raise ValueError("degenerate directed camera")
        axis.normalize();dist=spec.get("distance",4.0);lens=spec.get("lens",42)
        pos=target+axis*dist
        frame(scene,cam,pos,target,lens)
        b=project(scene,cam,pts)
        if b[4]<=0:raise ValueError("face behind camera")
        if kind=="emotion":
            desired=float(spec.get("emotion_face_target",.46))
            if not .40<=desired<=.60:raise ValueError("emotion face target outside direction contract")
            lens=max(12,min(180,lens*desired/max(.001,b[3]-b[2])))
        elif kind=="interview":
            span=max(.001,b[1]-b[0]);height=max(.001,b[3]-b[2])
            lens=max(12,min(120,lens*min(spec.get("interview_face_span",.82)/span,.54/height)))
        state.update({"target":target.copy(),"axis":axis.copy(),"distance":dist,"lens":lens,"root":principal.root.matrix_world.translation.copy()})
    target=state["target"].copy();axis=state["axis"];dist=state["distance"];lens=state["lens"]
    if move=="track":target+=principal.root.matrix_world.translation-state["root"]
    if move=="reframe":target+=Vector(spec.get("reframe_delta",[0,0,0]))*u
    pos=target+axis*(dist-spec.get("push_distance",.12)*u if move=="push" else dist)
    if move=="drift":
        lateral=Vector((-axis.y,axis.x,0));pos+=lateral*spec.get("drift_distance",.18)*(u-.5)
    frame(scene,cam,pos,target,lens)

def sample(scene,cam,actors,spec,grade,visibility=None,meshes=None):
    ids=[spec["principal"]]+spec.get("listeners",[])
    result={"beat_type":spec["beat_type"],"principal":spec["principal"],"listeners":spec.get("listeners",[]),"camera_move":spec.get("camera_move"),"grade":grade,"actors":{}}
    for cid,a in actors.items():
        f=project(scene,cam,face_points(a))
        result["actors"][cid]={"pose":pose_signature(a),"face_facing_dot":face_facing(a,cam),"face_height":max(0,min(1,f[3])-max(0,f[2])),"face_safe":f[4]>0 and .025<=f[0]<=f[1]<=.975 and .025<=f[2]<=f[3]<=.975}
    result["pure_establishing"]=bool(spec.get("pure_establishing",False))
    result["landmarks"]={}
    for landmark in spec.get("landmarks",[]):
        name=landmark["id"];objs=[]
        for ref in landmark["objects"]:
            ob=bpy.data.objects.get(ref)
            if ob is not None:objs.extend(meshes(ob) if meshes else [ob])
        objs=list(dict.fromkeys(objs))
        if not objs or visibility is None:
            result["landmarks"][name]={"pass":False,"reason":"missing landmark object or ray sampler"};continue
        v=visibility(scene,cam,objs,5);b=v["bounds"]
        width=max(0,min(1,b[1])-max(0,b[0]));height=max(0,min(1,b[3])-max(0,b[2]))
        passed=v["samples"]>0 and v["visible_fraction"]>=landmark.get("min_visible_fraction",.25) and width>=landmark.get("min_width",.06) and height>=landmark.get("min_height",.04) and (not landmark.get("require_safe",False) or v["safe"])
        result["landmarks"][name]={"pass":bool(passed),"width":width,"height":height,"ray":v}
    return result

def performance(actors,spec,u,t):
    """Authored gestures are piecewise-linear pose keys, not arbitrary jitter.
    Explicit actor tracks only; no contact-bearing bone may be overwritten
    without a story-adapter contact recomputation.
    """
    def interpolate(keys):
        if u<=keys[0][0]:return keys[0][1]
        for (lo,a),(hi,b) in zip(keys,keys[1:]):
            if u<=hi:
                w=(u-lo)/(hi-lo)
                return [x+(y-x)*w for x,y in zip(a,b)]
        return keys[-1][1]
    for cid,track in spec.get("performance",{}).items():
        if cid not in actors:raise ValueError("missing performance actor "+cid)
        actor=actors[cid]
        for bone in ("head","torso"):
            if bone in track:actor.set_bone(bone,tuple(interpolate(track[bone])))
        for arm,keys in track.get("arms",{}).items():actor.aim_arm(int(arm),tuple(interpolate(keys)))
        if "expressions" in track:
            expression=track["expressions"][0][1]
            for start,value in track["expressions"]:
                if u>=start:expression=value
            actor.pose(expression)
    # Non-principal background business uses explicit authored group keys.
    # Head-only so seated support and carried props are not displaced.
    for i,cid in enumerate(spec.get("background",[])):
        if cid not in actors:raise ValueError("missing background actor "+cid)
        a=actors[cid];phase=t*2.8+i*.81
        # Visible, staggered gaze shifts (not camera jitter). Batched using
        # the same bind-basis operation as the locked set_bone API.
        pb=a.bones["head"];pb.rotation_mode="XYZ"
        pb.matrix_basis=a.bind_basis[pb.name]@Euler((.14*math.sin(phase),0,.26*math.sin(phase+.9))).to_matrix().to_4x4()
    bpy.context.view_layer.update()

def directed_bounce(scene,cam,spec,actors):
    """Motivated warm plaza bounce. Opt-in and recorded, not a hidden grade.
    The broad source follows the camera-side subject area, not camera rays;
    a source outside the frame does not modify any character geometry."""
    q=spec.get("grade_fill")
    if not q:return None
    ob=bpy.data.objects.get("Directed warm bounce")
    if ob is None:
        data=bpy.data.lights.new("Directed warm bounce","AREA")
        ob=bpy.data.objects.new("Directed warm bounce",data);scene.collection.objects.link(ob)
    ids=[i for i in [spec.get("principal")]+spec.get("listeners",[]) if i in actors]
    if not ids:raise ValueError("warm bounce needs a subject")
    target=center([p for i in ids for p in face_points(actors[i])])
    axis=(cam.location-target).normalized()
    lateral=Vector((-axis.y,axis.x,0))
    ob.location=target+axis*q.get("distance",2.8)+lateral*q.get("side",.2)+Vector((0,0,q.get("height",.7)))
    ob.rotation_euler=(target-ob.location).to_track_quat("-Z","Y").to_euler()
    ob.data.energy=q["energy"];ob.data.size=q.get("size",3.5);ob.data.color=tuple(q.get("color",[1,.87,.72]))
    if "exposure" in q:scene.view_settings.exposure=q["exposure"]
    bpy.context.view_layer.update()
    return {"energy":ob.data.energy,"color":list(ob.data.color),"size":ob.data.size,"exposure":scene.view_settings.exposure,"position":list(ob.location)}

def directed_hand_props(actors,spec,t):
    """Stage a declared handheld prop along the evaluated distal arm.
    The source actor rig is unchanged. Re-aiming is explicit story data.
    Geometry and ray checks must run after this attachment."""
    records={}
    for q in spec.get("hand_props",[]):
        a=actors[q["actor"]];i=int(q["socket"]);ob=bpy.data.objects.get(q["object"])
        if ob is None:raise ValueError("missing directed hand prop "+q["object"])
        base=q["aim"];amp=q.get("shake_amplitude",[0,0,0]);freq=q.get("shake_frequency",[25,25,23])
        direction=Vector([x+y*math.sin(t*z) for x,y,z in zip(base,amp,freq)])
        a.aim_arm(i,direction);bpy.context.view_layer.update()
        grip=a.grips[i].matrix_world.translation.copy()
        shoulder=(a.armature.matrix_world@a.arms[i].matrix).translation
        axis=(grip-shoulder).normalized()
        axis=(axis+Vector(q.get("shaft_lift",[0,0,.32]))).normalized()
        offset=q.get("anchor_offset",.105)
        orient=Vector(q.get("local_shaft_axis",[0,0,-1])).rotation_difference(axis).to_matrix().to_4x4()
        ob.matrix_world=Matrix.Translation(grip+axis*offset)@orient
        bpy.context.view_layer.update()
        records[q["object"]]={"actor":q["actor"],"socket":i,"anchor_error":float((ob.matrix_world.translation-axis*offset-grip).length),"aim":list(direction)}
    return records
