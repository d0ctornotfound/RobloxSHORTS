"""Perfect Throw choreography port to the approved supplied R6 variant rig."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Euler,Matrix
from bpy_extras.object_utils import world_to_camera_view
from render_demo import empty,point_at,material
from render_stills import configure
from r6_character import R6Character,mesh_points,bounds,SOURCE_SHA256
from r6_variant_character import VariantCharacter
from classroom_set import build
from render_story import seat,shoulder,arm_length,frame_at,frame_time
from stage_b_interaction import GripAttachment,ExpressionTrack,smoothstep,blend_direction

def plane_mesh():
    root=empty("Paper plane grip origin",(0,0,0))
    # Nose points along local -Y; the grip is beneath the central folded keel.
    v=[(0,-.58,.06),(0,.42,.06),(-.48,.38,.16),(-.16,.46,.07),
       (.48,.38,.16),(.16,.46,.07),(0,.36,-.10)]
    faces=[(0,2,3,1),(0,1,5,4),(0,6,3),(0,5,6)]
    m=bpy.data.meshes.new("Four folded paper panels");m.from_pydata(v,[],faces);m.update()
    ob=bpy.data.objects.new("Folded paper plane",m);bpy.context.collection.objects.link(ob);ob.parent=root
    m.materials.append(material("White paper",(.94,.94,.87)))
    m.materials.append(material("Paper fold shadow",(.66,.75,.79)))
    for i,poly in enumerate(m.polygons):poly.material_index=int(i>=2)
    s=ob.modifiers.new("Paper thickness","SOLIDIFY");s.thickness=.009
    return root,ob

def seated(a,x,y):
    seat(a,x,y,"")
    a.pose("neutral")
    for i in (0,1):a.aim_arm(i,(.13 if i==0 else -.13,-.84,-.50))

def corners(o):
    lo,hi=bounds(mesh_points(o))
    return [Vector((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]

def desk_contact(actor,index,length,desk_x):
    # Solve actual rigid-arm reach sphere against the real desk top.
    # Rear edge y=-.375, front edge y=-1.225, top z=1.205.
    joint=shoulder(actor,index);z=1.205;dz=z-joint.z
    assert dz<0 and abs(dz)<length,("desk reach height",index,list(joint),length)
    radius=math.sqrt(length*length-dz*dz)
    opts=[]
    # Exact sphere-plane points, prefer closest to rear edge and avoid
    # crossing the torso midline. No invented IK or finger articulation.
    for n in range(720):
        a=math.tau*n/720
        x=joint.x+radius*math.cos(a);y=joint.y+radius*math.sin(a)
        if desk_x-.72<=x<=desk_x+.72 and -1.21<=y<=-.375 and y<joint.y-.03:
            opts.append(Vector((x,y,z)))
    assert opts,("no reachable desk contact",index,list(joint),length)
    target=min(opts,key=lambda p:abs(p.y+.375)+.35*abs(p.x-joint.x))
    d=actor.root.matrix_world.to_3x3().inverted()@(target-joint)
    return target,d.normalized()


def main():
    pa=argparse.ArgumentParser();pa.add_argument("--story",default="stories/the_perfect_throw.json");pa.add_argument("--profile",choices=("preview","full"),default="preview");pa.add_argument("--shot",default="all");pa.add_argument("--output",default="render/story");pa.add_argument("--validate-only",action="store_true")
    a=pa.parse_args(sys.argv[sys.argv.index("--")+1:])
    spec=json.loads(Path(a.story).read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    fps,w,h,samples=(12,432,768,24) if a.profile=="preview" else (24,1080,1920,96)
    scene=configure(a.profile);scene.cycles.samples=samples;scene.cycles.adaptive_threshold=.065 if fps==12 else .02
    scene.cycles.max_bounces=4;scene.cycles.diffuse_bounces=2;scene.render.use_persistent_data=True
    scene.view_settings.view_transform="AgX";scene.view_settings.look="AgX - Medium High Contrast";scene.view_settings.exposure=.05
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.42,.31,.21,1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.30
    scene.render.resolution_x=w;scene.render.resolution_y=h;scene.render.fps=fps;scene.frame_start=1;scene.frame_end=round(spec["duration"]*fps)
    build()
    lead=VariantCharacter("lead","lead");friend=VariantCharacter("friend","friend");teacher=VariantCharacter("teacher","teacher")
    seated(lead,-.78,0.0);seated(friend,.78,0.0)
    teacher.root.location=(0,-5.85,0);teacher.root.rotation_euler.z=0
    actors={"lead":lead,"friend":friend,"teacher":teacher}
    extras=[]
    for i,(x,y) in enumerate([(-.78,2.2),(.78,2.2),(-.78,4.4),(.78,4.4)]):
        extra=R6Character("student "+str(i),"patron_green" if i%2 else "patron_blue")
        seated(extra,x,y);extras.append(extra)
    tracks={n:ExpressionTrack(o) for n,o in actors.items()}
    plane,mesh=plane_mesh()
    # Head socket aligns the paper nose with the side of the actual bun.
    # Local nose ends at y=-.58; center lies on the visible side of the bun.
    bun=teacher.bun
    bpy.context.view_layer.update()
    nose_world=bun.matrix_world@Vector((.55,0,0))
    rotation=(.32,0,-math.pi/2)
    center=nose_world-Euler(rotation).to_matrix()@Vector((0,-.58,.06))
    support=teacher.attach_at("Teacher bun paper support","head",teacher.root.matrix_world.inverted()@center,rotation)
    bpy.context.view_layer.update()
    local=bun.matrix_world.inverted()@(support.matrix_world@Vector((0,-.58,.06)))
    assert local.length<.8,list(local)
    grip=lead.grips[0]
    paper_socket=empty("Lead paper orientation socket",(0,0,0),grip)
    paper_socket.rotation_mode="QUATERNION"
    hand=GripAttachment(plane,paper_socket);hair=GripAttachment(plane,support)
    launch=frame_at(spec["actions"]["launch"],fps);land=frame_at(spec["actions"]["landing"],fps)
    timeline=[];errors=[];start=None;start_rot=None;desk_errors=[];desk_targets={}
    lengths=[arm_length(lead,i) for i in (0,1)]
    # The teacher turns through 180 degrees during flight, then stays turned.
    def teacher_yaw(t):return (math.pi-.28)*smoothstep((t-6.4)/1.25)
    # Calculate the landing support in its final world pose in advance.
    teacher.root.rotation_euler.z=math.pi-.28;bpy.context.view_layer.update()
    end=support.matrix_world.translation.copy();end_rot=support.matrix_world.to_euler()
    teacher.root.rotation_euler.z=0
    for f in range(1,scene.frame_end+1):
        scene.frame_set(f);t=frame_time(f,fps)
        teacher.root.rotation_euler.z=teacher_yaw(t);teacher.root.keyframe_insert("rotation_euler",frame=f)
        expressions={"lead":"neutral" if t<3 else "happy" if t<10.55 else "shocked",
                     "friend":"neutral" if t<5 else "laughing" if t>=10 else "happy",
                     "teacher":"neutral" if t<7.75 else "shocked" if t<9.5 else "neutral"}
        for name,actor in actors.items():
            # Payoff-only lean, keyed throughout to preserve the earlier shots.
            if name in ("lead","friend"):
                lean=smoothstep((t-10.0)/.35) if name=="friend" else smoothstep((t-10.55)/.15)
                actor.root.rotation_euler.x=(-.12 if name=="lead" else -.16)*lean
                actor.root.keyframe_insert("rotation_euler",frame=f)
            head_rotation=(.16 if name=="lead" and t<2.7 else 0,0,-.18 if name=="friend" and t<5 else 0)
            if name=="teacher":head_rotation=(0,0,0)
            if name=="friend" and t>=9.5:head_rotation=(-.22-.05*math.sin(t*10),0,-.13)
            if name=="lead" and t>=10:head_rotation=(-.06,0,.03)
            actor.set_bone("head",head_rotation,f)
            for i in (0,1):
                d=Vector((.24 if i==0 else -.24,-.66,-.55))
                closed=False
                if name=="lead":
                    if t>=10:
                        # Aim down and forward at the rear edge of the desk; never cross the face.
                        bpy.context.view_layer.update()
                        target,d=desk_contact(actor,i,lengths[i],-.78)
                        closed=True
                    elif i==0:
                        fold=Vector((.48+.08*math.sin(t*5),-.68,-.40))
                        wind=Vector((-.15,-.25,.90))
                        throw=Vector((.12,.90,.34))
                        if t<2.8:d=fold
                        elif t<3.7:d=blend_direction(fold,wind,(t-2.8)/.9)
                        elif t<4.25:d=blend_direction(wind,throw,(t-3.7)/.55)
                        else:d=blend_direction(throw,(.15,-.22,-.9),(t-4.25)/.65)
                        closed=f<launch
                    elif t<2.8:d=Vector((-.67,-.62,-.38+.08*math.sin(t*5)))
                    elif t>=9.5:d=Vector((-.15,-.50,.60))
                elif name=="friend" and t>=10:
                    # Laugh with the head tilted back and hands below the face.
                    d=Vector((.16,-.78,-.40-.18*math.sin(t*12)) if i==0 else (.20,-.26,-.92))
                elif name=="friend" and t>=8:d=Vector((.32,-.78,-.28) if i==0 else (-.10,-.38,.72+.10*math.sin(t*8)))
                elif name=="teacher":
                    d=Vector((0,-.8,.30)) if i==1 and t<6.4 else Vector((.05 if i==0 else -.05,-.12,-1))
                    if t>=9.5:d=Vector((.38 if i==0 else -.38,-.65,-.38))
                actor.aim_arm(i,d,f)
                if name=="lead" and t>=10:
                    error=(actor.grips[i].matrix_world.translation-target).length
                    assert error<.001,("desk contact missed",f,i,error)
                    desk_errors.append(error)
                    desk_targets.setdefault(f,[]).append(list(target))
            tracks[name].key(f,expressions[name])
        bpy.context.view_layer.update()
        if f<launch:
            # Keep the folding paper horizontal and below the face while
            # preserving actual grip translation; blend to original hand
            # orientation before the throw, no release teleport.
            grip_world=grip.matrix_world.copy()
            orient=Euler((0,0,-.35)).to_quaternion().slerp(grip_world.to_quaternion(),smoothstep((t-2.65)/.35))
            paper_socket.matrix_world=Matrix.Translation(grip_world.translation)@orient.to_matrix().to_4x4()
            for field in ("location","rotation_quaternion","scale"):paper_socket.keyframe_insert(field,frame=f)
            bpy.context.view_layer.update()
            assert (paper_socket.matrix_world.translation-grip_world.translation).length<1e-5
            hair.constraint.influence=0;hair.constraint.keyframe_insert("influence",frame=f)
            plane.location=(0,0,0);plane.rotation_euler=(0,0,0)
            plane.keyframe_insert("location",frame=f);plane.keyframe_insert("rotation_euler",frame=f)
            errors.append(hand.bind(f));state="hand"
        elif f<land:
            if start is None:start=hand.release();start_rot=hand.last_world.to_euler()
            u=(f-launch)/(land-launch)
            # Smooth curved route above the rear rows, then toward the board.
            points=[start,Vector((-.78,2.2,3.05)),Vector((-.78,4.4,3.12)),Vector((2.15,3.8,3.10)),Vector((1.8,-.5,3.05)),end]
            times=[0,.22,.42,.57,.76,1]
            j=next((i for i in range(len(times)-1) if u<=times[i+1]),len(times)-2)
            v=(u-times[j])/(times[j+1]-times[j]);dt=times[j+1]-times[j]
            def tangent(i):
                if i==0:return (points[1]-points[0])/(times[1]-times[0])
                if i==len(points)-1:return (points[i]-points[i-1])/(times[i]-times[i-1])
                return (points[i+1]-points[i-1])/(times[i+1]-times[i-1])
            pos=(2*v**3-3*v*v+1)*points[j]+(v**3-2*v*v+v)*dt*tangent(j)+(-2*v**3+3*v*v)*points[j+1]+(v**3-v*v)*dt*tangent(j+1)
            velocity=(6*v*v-6*v)*points[j]+(3*v*v-4*v+1)*dt*tangent(j)+(-6*v*v+6*v)*points[j+1]+(3*v*v-2*v)*dt*tangent(j+1)
            target_rot=velocity.to_track_quat("-Y","Z")
            rot=start_rot.to_quaternion().slerp(target_rot,smoothstep(u/.12)).slerp(end_rot.to_quaternion(),smoothstep((u-.83)/.17)).to_euler()
            hand.independent(f,pos,rot);hair.constraint.influence=0;hair.constraint.keyframe_insert("influence",frame=f);state="flight"
        else:
            hand.independent(f,support.matrix_world.translation,support.matrix_world.to_euler())
            errors.append(hair.bind(f));state="hair"
        bpy.context.view_layer.update()
        timeline.append({"frame":f,"time":t,"state":state,"plane":list(plane.matrix_world.translation),"expressions":expressions})
    hand.constant_switches();hair.constant_switches()
    for track in tracks.values():track.constant_switches()
    assert max(errors)<1e-5
    assert desk_errors and max(desk_errors)<.001
    assert (scene.frame_end-land+1)/fps>=2
    assert {r["state"] for r in timeline}=={"hand","flight","hair"}
    for row in timeline:
        scene.frame_set(row["frame"]);bpy.context.view_layer.update()
        assert (plane.matrix_world.translation-Vector(row["plane"])).length<.001
        for name,track in tracks.items():assert [n for n,o in track.decals.items() if not o.hide_render]==[row["expressions"][name]]
        if row["frame"] in desk_targets:
            for i,target in enumerate(desk_targets[row["frame"]]):assert (lead.grips[i].matrix_world.translation-Vector(target)).length<.001
    # Extras appear only in throw and glide.
    from render_story import constant_action
    for extra in extras:
        for ob in extra.meshes:
            for t,visible in ((0,False),(3,True),(8,False)):
                ob.hide_render=not visible;ob.keyframe_insert("hide_render",frame=frame_at(t,fps))
            constant_action(ob,["hide_render"])
    # Preserve one animated timeline; cameras cut through timeline markers.
    # The last shot uses a teacher close-up with students behind her in depth.
    # Fixed focal lengths, no automatic lens widening. The folding camera
    # looks across the desks at a diagonal to compress their horizontal spread.
    # Fixed focal length candidates: solve camera position/target, never widen
    # to follow the flying plane. A split payoff retains one workflow chunk.
    records=[]
    for shot in spec["shots"]:
        sid=shot["id"];first=frame_at(shot["start"],fps);last=frame_at(shot["end"],fps)-1
        segments=[(first,last,sid)]
        if sid=="04_payoff":segments=[(first,frame_at(10,fps)-1,"teacher_impact"),(frame_at(10,fps),last,"boys_reaction")]
        parts=[]
        for lo,hi,kind in segments:
            heroes=["lead","friend"] if kind in ("01_fold","boys_reaction") else ["lead"] if kind=="02_throw" else ["teacher"] if kind=="teacher_impact" else []
            bpy.ops.object.camera_add();cam=bpy.context.object;cam.name=kind;cam.data.sensor_fit="HORIZONTAL"
            marker=scene.timeline_markers.new(kind,frame=lo);marker.camera=cam;scene.camera=cam
            sampleset=[]
            for f in range(lo,hi+1):
                scene.frame_set(f);bpy.context.view_layer.update()
                prop=corners(mesh);body={};safe=[]
                if kind not in ("boys_reaction",) and (kind!="02_throw" or f<=launch):safe.extend(prop)
                for n in heroes:
                    actor=actors[n]
                    body[n]=[v for ob in actor.meshes if ob.type=="MESH" and ob!=actor.face for v in corners(ob)]
                    safe.extend(v for ob in actor.meshes if any(k in ob.name for k in ("head","hair","beanie","palm","finger")) for v in corners(ob))
                sampleset.append((f,prop,body,safe,plane.matrix_world.translation.copy()))
            def measure():
                rows=[];bounds=[];widths=[]
                for f,prop,body,safe,center in sampleset:
                    if kind=="03_glide":
                        cam.location=center+Vector((-3.05,-.32,-.10));point_at(cam,center+Vector((0,0,-.85)))
                    bpy.context.view_layer.update()
                    pp=[world_to_camera_view(scene,cam,v) for v in prop]
                    widths.append(max(v.x for v in pp)-min(v.x for v in pp))
                    bounds.extend(world_to_camera_view(scene,cam,v) for v in safe)
                    row={}
                    for n,verts in body.items():
                        vs=[world_to_camera_view(scene,cam,v) for v in verts]
                        row[n]=max(0,min(1,max(v.y for v in vs))-max(0,min(v.y for v in vs)))
                    rows.append(row)
                cov={n:min(row[n] for row in rows) for n in heroes}
                ok=all(v.z>0 and .035<=v.x<=.965 and .045<=v.y<=.97 for v in bounds)
                penalty=sum(max(0,.035-v.x,v.x-.965)+max(0,.045-v.y,v.y-.97) for v in bounds)/max(1,len(bounds))
                return cov,ok,penalty,bounds,widths
            if kind=="03_glide":
                cam.data.lens=48
                result=measure()
                for f,prop,body,safe,center in sampleset:
                    scene.frame_set(f);cam.location=center+Vector((-3.05,-.32,-.10));point_at(cam,center+Vector((0,0,-.85)))
                    cam.keyframe_insert("location",frame=f);cam.keyframe_insert("rotation_euler",frame=f)
            elif kind=="teacher_impact":
                cam.location=(-1.65,-3.35,2.45);cam.data.lens=47;point_at(cam,(-.30,-5.82,2.35));result=measure()
            elif kind=="02_throw":
                # Exact known non-black camera recovered from the packed blend
                # of run 45890838253 (artifact 15152761142). No search.
                cam.data.lens=48
                cam.location=(-1.85,-4.0,2.5)
                point_at(cam,(-.78,-.15,1.65))
                result=measure()
            else:
                # Frontal compressed perspective; fixed lens throughout shot.
                # Search physical positions and aim, using the whole segment's bounds.
                cam.data.lens=52 if kind=="01_fold" else 48
                cx=-.78 if kind=="02_throw" else 0
                best=None
                for dx in (0,-.55,.55,-1.1,1.1):
                    for dist in (3.1,3.5,3.9,4.3,4.7):
                        for z in ((2.1,2.35,2.65) if kind=="01_fold" else (1.48,1.75,2.0)):
                            for aimx in (-.25,0,.25):
                                cam.location=(cx+dx,-dist,z);point_at(cam,(cx+aimx,-.15,1.73 if kind=="01_fold" else 1.40))
                                m=measure();cov,ok,penalty,_,_=m
                                score=(ok and min(cov.values())>=.40,min(cov.values())-penalty*12,ok)
                                if best is None or score>best[0]:best=(score,cam.location.copy(),cam.rotation_euler.copy(),m)
                _,pos,rot,result=best;cam.location=pos;cam.rotation_euler=rot
            cov,ok,penalty,bounds,widths=result
            parts.append({"segment":kind,"first":lo,"last":hi,"lens":cam.data.lens,"min_hero_vertical_coverage":cov,"coverage_goal_met":all(v>=.45 for v in cov.values()),"supervisor_minimum_met":all(v>=.40 for v in cov.values()),"safe_bounds_met":ok,"bounds":[min(v.x for v in bounds),max(v.x for v in bounds),min(v.y for v in bounds),max(v.y for v in bounds)],"min_plane_projected_width":min(widths)})
        combined={}
        for part in parts:
            for n,v in part["min_hero_vertical_coverage"].items():combined[n]=min(combined.get(n,1),v)
        records.append({"id":sid,"first":first,"last":last,"segments":parts,"min_hero_vertical_coverage":combined,"coverage_goal_met":all(p["coverage_goal_met"] for p in parts),"supervisor_minimum_met":all(p["supervisor_minimum_met"] for p in parts),"safe_bounds_met":all(p["safe_bounds_met"] for p in parts)})
    # Localized bounce for the last glide frames only; no change to the
    # other shots, camera, prop timeline, or final pixel acceptance gate.
    from stage_a_cafe import light
    light("Glide landing shadow fill",(-3.2,-4.4,2.6),(0,-5.85,.65),180,2.5,(1,.86,.72))
    lamp=bpy.data.objects.get("Glide landing shadow fill")
    for t,power in ((0,0),(7.0,0),(7.5,180),(8.0,0),(12,0)):
        lamp.data.energy=power;lamp.data.keyframe_insert("energy",frame=frame_at(t,fps))
    # Keep the light off at the teacher cut, not a gradual cross-shot fade.
    lamp.data.animation_data.action.fcurves[0].keyframe_points[-3].interpolation="CONSTANT"
    scene.frame_set(1)
    manifest={"story":spec["id"],"resolution":[w,h],"fps":fps,"duration":12,"frame_count":scene.frame_end,"samples":samples,"shots":records,"timeline":timeline,"max_grip_error":max(errors),"launch_frame":launch,"landing_frame":land,"payoff_hold_seconds":(scene.frame_end-land+1)/fps,"bun_contact_local":list(local),"rig":"approved source GLB R6 VariantCharacter","source_sha256":SOURCE_SHA256,"max_desk_grip_error":max(desk_errors),"desk_contact_frames":len(desk_targets),"rigid_hands":True}
    (out/"story_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("CLASSROOM_VALIDATION",json.dumps({k:v for k,v in manifest.items() if k!="timeline"}),flush=True)
    if a.validate_only:return
    scene.frame_set(1);scene.render.filepath=str(out/"frame_")
    if a.shot in ("all",records[0]["id"],"03_glide"):
        for image in bpy.data.images:
            if image.source in ("GENERATED","FILE") and not image.packed_file:image.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(out/"story.blend"))
    selected=[r for r in records if a.shot in ("all",r["id"])];assert selected
    # Pre-flight the selected shot's camera(s) before any full animation render.
    # Use a real PNG, loaded as non-color data so the threshold is the same
    # 8-bit display RGB <=24 as the encoded-video gate. Keep evidence separately
    # from the shared timeline manifest (each matrix runner owns its own tests).
    preflight=[]
    from camera_visibility import visibility_gate
    old_samples=scene.cycles.samples;old_pct=scene.render.resolution_percentage
    old_path=scene.render.filepath
    for rec in selected:
        for part in rec["segments"]:
            f=(part["first"]+part["last"])//2
            scene.frame_set(f);bpy.context.view_layer.update()
            scene.render.resolution_percentage=50;scene.cycles.samples=32
            filename=out/("preflight_"+part["segment"]+".png")
            scene.render.filepath=str(filename)
            bpy.ops.render.render(write_still=True)
            im=bpy.data.images.load(str(filename),check_existing=False)
            im.colorspace_settings.name="Non-Color"
            from array import array
            pixels=array("f",[0])*(im.size[0]*im.size[1]*4)
            im.pixels.foreach_get(pixels)
            count=len(pixels)//4
            pct=100*sum(max(pixels[i:i+3])<=24/255 for i in range(0,len(pixels),4))/count
            bpy.data.images.remove(im)
            groups={n:[o for o in actors[n].meshes if o.type=="MESH" and o!=actors[n].face] for n in part["min_hero_vertical_coverage"]}
            if part["segment"]=="03_glide":groups={"plane":[mesh]}
            visibility=visibility_gate(scene,out,part["segment"],groups)
            row={"segment":part["segment"],"frame":f,"near_black_percent":pct,"threshold_percent":10,"visibility":visibility,"pass":pct<=10 and all(v["pass"] for v in visibility.values())}
            preflight.append(row)
            print("CAMERA_PREFLIGHT",json.dumps(row),flush=True)
            (out/"preflight.json").write_text(json.dumps(preflight,indent=2)+"\n")
            if not row["pass"]:raise RuntimeError("Camera pre-flight darkness or occlusion gate failed: "+str(row))
    scene.cycles.samples=old_samples;scene.render.resolution_percentage=old_pct
    scene.render.filepath=old_path
    scene.frame_start=selected[0]["first"];scene.frame_end=selected[-1]["last"];scene.frame_set(scene.frame_start)
    bpy.ops.render.render(animation=True)
if __name__=="__main__":main()
