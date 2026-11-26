"""Perfect Throw continuous classroom animation, using the approved quality rig."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import empty,point_at,material
from render_stills import configure
from quality_character import Character,palette
from classroom_set import Teacher,teacher_palette,build
from render_story import head_pivot,frame_at,frame_time
from stage_b_interaction import GripAttachment,ExpressionTrack,aim_arm,key_arm,smoothstep,blend_direction

def plane_mesh():
    root=empty("Paper plane grip origin",(0,0,0))
    # Nose points along local -Y; the grip is beneath the central folded keel.
    v=[(0,-.58,.06),(0,.31,.06),(-.38,.27,.12),(-.13,.35,.07),
       (.38,.27,.12),(.13,.35,.07),(0,.27,-.10)]
    faces=[(0,2,3,1),(0,1,5,4),(0,6,3),(0,5,6)]
    m=bpy.data.meshes.new("Four folded paper panels");m.from_pydata(v,[],faces);m.update()
    ob=bpy.data.objects.new("Folded paper plane",m);bpy.context.collection.objects.link(ob);ob.parent=root
    m.materials.append(material("White paper",(.94,.94,.87)))
    m.materials.append(material("Paper fold shadow",(.66,.75,.79)))
    for i,poly in enumerate(m.polygons):poly.material_index=int(i>=2)
    s=ob.modifiers.new("Paper thickness","SOLIDIFY");s.thickness=.009
    return root,ob

def seated(a,x,y):
    a.root.location=(x,y,-.219)
    for leg in a.legs:leg.rotation_euler.x=-math.pi/2
    for i in (0,1):aim_arm(a,i,(.13 if i==0 else -.13,-.84,-.50))
    a.pose("neutral")
    for i in (0,1):aim_arm(a,i,(.13 if i==0 else -.13,-.84,-.50))

def corners(o):return [o.matrix_world@Vector(v) for v in o.bound_box]

def main():
    pa=argparse.ArgumentParser();pa.add_argument("--story",default="stories/the_perfect_throw.json");pa.add_argument("--profile",choices=("preview","full"),default="preview");pa.add_argument("--shot",default="all");pa.add_argument("--output",default="render/story")
    a=pa.parse_args(sys.argv[sys.argv.index("--")+1:])
    spec=json.loads(Path(a.story).read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    fps,w,h,samples=(12,432,768,24) if a.profile=="preview" else (24,1080,1920,96)
    scene=configure(a.profile);scene.cycles.samples=samples;scene.cycles.adaptive_threshold=.065 if fps==12 else .02
    scene.cycles.max_bounces=4;scene.cycles.diffuse_bounces=2;scene.render.use_persistent_data=True
    scene.view_settings.view_transform="AgX";scene.view_settings.look="AgX - Medium High Contrast";scene.view_settings.exposure=.25
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.35
    scene.render.resolution_x=w;scene.render.resolution_y=h;scene.render.fps=fps;scene.frame_start=1;scene.frame_end=round(spec["duration"]*fps)
    build();p=teacher_palette(palette())
    lead=Character("lead",p,True);friend=Character("friend",p,False);teacher=Teacher(p)
    seated(lead,-1.05,4.0);seated(friend,1.05,4.0)
    teacher.root.location=(0,-5.55,0);teacher.root.rotation_euler.z=0
    actors={"lead":lead,"friend":friend,"teacher":teacher}
    extras=[]
    for i,(x,y) in enumerate([(-3.2,1.8),(-1.05,1.8),(1.05,1.8),(3.2,1.8),(-3.2,4),(3.2,4)]):
        extra=Character("student "+str(i),p,False,role="patron_green" if i%2 else "patron_blue")
        seated(extra,x,y);extras.append(extra)
    pivots={n:head_pivot(o) for n,o in actors.items()}
    tracks={n:ExpressionTrack(o) for n,o in actors.items()}
    plane,mesh=plane_mesh()
    # Head socket aligns the paper nose with the side of the actual bun.
    # Local nose ends at y=-.58; center lies on the visible side of the bun.
    support=empty("Teacher bun paper support",(.28,.80,.531),pivots["teacher"])
    support.rotation_euler=(0,0,-.55)
    bpy.context.view_layer.update()
    bun=teacher.bun
    # Nose must lie inside or close to the bun geometry in its local coordinates.
    nose=support.matrix_world@Vector((0,-.58,.06))
    local=bun.matrix_world.inverted()@nose
    assert local.length<.38, list(local)
    grip=lead.grips[0];hand=GripAttachment(plane,grip);hair=GripAttachment(plane,support)
    launch=frame_at(spec["actions"]["launch"],fps);land=frame_at(spec["actions"]["landing"],fps)
    timeline=[];errors=[];start=None;start_rot=None
    # The teacher turns through 180 degrees during flight, then stays turned.
    def teacher_yaw(t):return math.pi*smoothstep((t-6.4)/1.25)
    # Calculate the landing support in its final world pose in advance.
    teacher.root.rotation_euler.z=math.pi;bpy.context.view_layer.update()
    end=support.matrix_world.translation.copy();end_rot=support.matrix_world.to_euler()
    teacher.root.rotation_euler.z=0
    for f in range(1,scene.frame_end+1):
        scene.frame_set(f);t=frame_time(f,fps)
        teacher.root.rotation_euler.z=teacher_yaw(t);teacher.root.keyframe_insert("rotation_euler",frame=f)
        expressions={"lead":"neutral" if t<3 else "happy" if t<9.5 else "shocked",
                     "friend":"neutral" if t<5 else "happy",
                     "teacher":"neutral" if t<7.75 else "shocked" if t<9.5 else "neutral"}
        for name,actor in actors.items():
            pivot=pivots[name]
            pivot.rotation_euler=(.16 if name=="lead" and t<2.7 else -.06 if name=="teacher" and t>=9.5 else 0,0,
                                  -.18 if name=="friend" and t<5 else 0)
            # Teacher support is fixed in the final head orientation, so avoid tilt after impact.
            if name=="teacher":pivot.rotation_euler=(0,0,0)
            pivot.keyframe_insert("rotation_euler",frame=f)
            for i in (0,1):
                d=Vector((.24 if i==0 else -.24,-.66,-.55))
                closed=False
                if name=="lead":
                    if i==0:
                        fold=Vector((.35+.13*math.sin(t*5),-.78,-.38))
                        wind=Vector((-.15,.30,.90))
                        throw=Vector((.12,-.92,.34))
                        if t<2.8:d=fold
                        elif t<3.7:d=blend_direction(fold,wind,(t-2.8)/.9)
                        elif t<4.25:d=blend_direction(wind,throw,(t-3.7)/.55)
                        else:d=blend_direction(throw,(.15,-.22,-.9),(t-4.25)/.65)
                        closed=f<launch
                    elif t<2.8:d=Vector((-.55,-.65,-.45+.10*math.sin(t*5)))
                    elif t>=9.5:d=Vector((-.15,-.50,.60))
                elif name=="friend" and t>=8:d=Vector((.2 if i==0 else -.2,-.65,.35+.12*math.sin(t*8)))
                elif name=="teacher":
                    d=Vector((0,-.8,.30)) if i==1 and t<6.4 else Vector((.05 if i==0 else -.05,-.12,-1))
                    if t>=9.5:d=Vector((.38 if i==0 else -.38,-.65,-.38))
                aim_arm(actor,i,d);key_arm(actor,i,f,closed)
            tracks[name].key(f,expressions[name])
        bpy.context.view_layer.update()
        if f<launch:
            hair.constraint.influence=0;hair.constraint.keyframe_insert("influence",frame=f)
            plane.location=(0,0,0);plane.rotation_euler=(0,0,0)
            plane.keyframe_insert("location",frame=f);plane.keyframe_insert("rotation_euler",frame=f)
            errors.append(hand.bind(f));state="hand"
        elif f<land:
            if start is None:start=hand.release();start_rot=hand.last_world.to_euler()
            u=(f-launch)/(land-launch)
            pos=start.lerp(end,u);pos.z+=.75*math.sin(math.pi*u)
            rot=start_rot.copy();rot.z=start_rot.z+(end_rot.z-start_rot.z)*smoothstep(u);rot.x+=.12*math.sin(math.tau*u)
            hand.independent(f,pos,rot);hair.constraint.influence=0;hair.constraint.keyframe_insert("influence",frame=f);state="flight"
        else:
            hand.independent(f,support.matrix_world.translation,support.matrix_world.to_euler())
            errors.append(hair.bind(f));state="hair"
        bpy.context.view_layer.update()
        timeline.append({"frame":f,"time":t,"state":state,"plane":list(plane.matrix_world.translation),"expressions":expressions})
    hand.constant_switches();hair.constant_switches()
    for track in tracks.values():track.constant_switches()
    assert max(errors)<1e-5
    assert (scene.frame_end-land+1)/fps>=2
    assert {r["state"] for r in timeline}=={"hand","flight","hair"}
    for row in timeline:
        scene.frame_set(row["frame"]);bpy.context.view_layer.update()
        assert (plane.matrix_world.translation-Vector(row["plane"])).length<.001
        for name,track in tracks.items():assert [n for n,o in track.decals.items() if not o.hide_render]==[row["expressions"][name]]
    # Preserve one animated timeline; cameras cut through timeline markers.
    # The last shot uses a teacher close-up with students behind her in depth.
    designs=[
        ((2.8,-.8,2.9),(-.65,3.5,1.45),38,["lead","friend"]),
        ((-3.0,1.05,2.8),(-1.05,3.6,1.85),42,["lead"]),
        ((4.8,-1.0,3.45),(0,-1,2.25),28,[]),
        ((2.5,-2.9,2.8),(0,-5.35,2.15),40,["teacher"])]
    records=[]
    for shot,(position,target,lens,heroes) in zip(spec["shots"],designs):
        first=frame_at(shot["start"],fps);last=frame_at(shot["end"],fps)-1
        bpy.ops.object.camera_add();cam=bpy.context.object;cam.name=shot["id"];cam.location=position;cam.data.sensor_fit="HORIZONTAL";cam.data.lens=lens;point_at(cam,target)
        sampleset=[]
        for f in range(first,last+1):
            scene.frame_set(f);bpy.context.view_layer.update()
            safe=corners(mesh)
            body={}
            for n in heroes:
                actor=actors[n]
                body[n]=[v for ob in actor.meshes if ob.type=="MESH" and ob!=actor.face for v in corners(ob)]
                safe.extend(v for ob in actor.meshes if any(k in ob.name for k in ("head","hair","beanie","palm","finger")) for v in corners(ob))
            sampleset.append((safe,body))
        for i in range(100):
            bpy.context.view_layer.update()
            bounds=[world_to_camera_view(scene,cam,v) for safe,_ in sampleset for v in safe]
            if all(v.z>0 and .035<=v.x<=.965 and .045<=v.y<=.97 for v in bounds):break
            cam.data.lens*=.97
        coverage={n:min(max(0,min(1,max(v.y for v in vs))-max(0,min(v.y for v in vs))) for vs in ([world_to_camera_view(scene,cam,v) for v in body[n]] for _,body in sampleset)) for n in heroes}
        marker=scene.timeline_markers.new(shot["id"],frame=first);marker.camera=cam
        records.append({"id":shot["id"],"first":first,"last":last,"lens":cam.data.lens,"min_hero_vertical_coverage":coverage,"coverage_goal_met":all(v>=.45 for v in coverage.values()),"safe_bounds_met":all(v.z>0 and .035<=v.x<=.965 and .045<=v.y<=.97 for v in bounds),"bounds":[min(v.x for v in bounds),max(v.x for v in bounds),min(v.y for v in bounds),max(v.y for v in bounds)]})
    manifest={"story":spec["id"],"resolution":[w,h],"fps":fps,"duration":12,"frame_count":scene.frame_end,"samples":samples,"shots":records,"timeline":timeline,"max_grip_error":max(errors),"launch_frame":launch,"landing_frame":land,"payoff_hold_seconds":(scene.frame_end-land+1)/fps,"bun_contact_local":list(local),"rig":"Sprint 2 quality"}
    (out/"story_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("CLASSROOM_VALIDATION",json.dumps({k:v for k,v in manifest.items() if k!="timeline"}),flush=True)
    scene.frame_set(1);scene.render.filepath=str(out/"frame_")
    if a.shot in ("all",records[0]["id"]):
        for image in bpy.data.images:
            if image.source=="GENERATED" and not image.packed_file:image.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(out/"story.blend"))
    selected=[r for r in records if a.shot in ("all",r["id"])];assert selected
    scene.frame_start=selected[0]["first"];scene.frame_end=selected[-1]["last"];scene.frame_set(scene.frame_start)
    bpy.ops.render.render(animation=True)
if __name__=="__main__":main()
