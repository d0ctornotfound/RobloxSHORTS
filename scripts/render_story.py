"""Data-driven café story renderer. Blender 4.0 compatible."""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import empty,point_at
from render_stills import configure
from stage_a_character import Character,palette
from stage_a_cafe import build_cafe,set_visible
from stage_b_interaction import aim_arm,key_arm,blend_direction,smoothstep,GripAttachment,GravityDrop,ExpressionTrack
from stage_c_props import build_plate_and_slice


def args():
    p=argparse.ArgumentParser()
    p.add_argument("--story",default="stories/the_last_slice.json")
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--output",default="render/story")
    p.add_argument("--shot",default="all")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])


def sample(track,t,discrete=False):
    value=track[0][1:]
    for a,b in zip(track,track[1:]):
        if t<b[0]:
            if discrete:
                return a[1]
            f=smoothstep((t-a[0])/(b[0]-a[0]))
            return tuple(x+(y-x)*f for x,y in zip(a[1:],b[1:]))
        value=b[1:]
    return value[0] if discrete else tuple(value)


def head_pivot(actor):
    pivot=empty(actor.root.name+" / head control",(0,0,2.10),actor.root)
    bpy.context.view_layer.update()
    for obj in actor.meshes:
        if any(k in obj.name for k in ("head","hair","fringe","decal","beanie")):
            world=obj.matrix_world.copy()
            obj.parent=pivot
            obj.matrix_world=world
    bpy.context.view_layer.update()
    return pivot


def vector_to_plate(actor,index,dx,support):
    # Existing wrist socket is .145 below the wrist. Solve exact arm length.
    shoulder=actor.arms[index].location
    dz=support+.145-shoulder.z
    dy=-math.sqrt(.70**2-dx**2-dz**2)
    return Vector((dx,dy,dz)).normalized()


def key_pose(actor,index,direction,frame,closed=False):
    aim_arm(actor,index,direction)
    key_arm(actor,index,frame,closed)


def frame_at(time,fps):
    return round(time*fps)+1


def frame_time(frame,fps):
    return (frame-1)/fps


def constant_action(obj,paths=None):
    for curve in obj.animation_data.action.fcurves:
        if paths is None or curve.data_path in paths:
            for key in curve.keyframe_points:
                key.interpolation="CONSTANT"


def linear_action(obj):
    for curve in obj.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation="LINEAR"


def main():
    a=args()
    spec=json.loads(Path(a.story).read_text())
    output=Path(a.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    fps,width,height,samples=(12,360,640,16) if a.profile=="preview" else (24,1080,1920,64)
    scene=configure(a.profile)
    scene.cycles.samples=samples
    scene.cycles.max_bounces=4
    scene.render.use_persistent_data=True
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.fps=fps
    scene.frame_start=1
    scene.frame_end=round(spec["duration"]*fps)
    for cup in build_cafe():
        set_visible(cup,False)
    p=palette()
    actors={name:Character(name,p,cfg["lead"]) for name,cfg in spec["characters"].items()}
    for name,actor in actors.items():
        actor.root.location=spec["characters"][name]["position"]
    pivots={name:head_pivot(actor) for name,actor in actors.items()}
    tracks={name:ExpressionTrack(actor) for name,actor in actors.items()}
    lead,friend=actors["lead"],actors["friend"]
    plate,cake=build_plate_and_slice(spec["props"]["plate"]["radius"])
    support=spec["props"]["plate"]["support_z"]
    radius=spec["props"]["plate"]["radius"]
    cake_offset=Vector(spec["props"]["slice"]["plate_offset"])
    reach_index={name:cfg["reach_arm"] for name,cfg in spec["characters"].items()}
    lead_i,friend_i=reach_index["lead"],reach_index["friend"]
    reach={name:vector_to_plate(actor,reach_index[name],-.025 if name=="lead" else .025,support)
           for name,actor in actors.items()}
    idle=Vector((0,-.11,-.69)).normalized()
    lead_socket=aim_arm(lead,lead_i,reach["lead"])
    # Plate center is offset inward from the lead's gripping palm. The rim,
    # rather than its center, lies between the fingers.
    lead_socket.location.x=.225
    bpy.context.view_layer.update()
    start_plate=lead_socket.matrix_world.translation.copy()
    assert abs(start_plate.z-support)<1e-5
    assert math.hypot(start_plate.x-.04,start_plate.y+.03)+radius<.65
    plate_bind=GripAttachment(plate,lead_socket)
    plate_top=empty("Plate / slice support",cake_offset,plate)
    slice_bind=GripAttachment(cake,plate_top)
    head_socket=empty("Lead / cake landing support",(0,.015,spec["props"]["slice"]["head_support"]-2.10),pivots["lead"])
    # A second attachment on the same prop is enabled only after landing.
    head_bind=GripAttachment(cake,head_socket)
    action=spec["actions"]
    contact=frame_at(action["lead_contact"],fps)
    friend_contact=frame_at(action["friend_contact"],fps)
    spin=frame_at(action["spin_start"],fps)
    launch=frame_at(action["launch"],fps)
    land=frame_at(action["landing"],fps)
    # Snap scheduled beats to the actual profile frame grid.
    times={k:frame_time(frame_at(v,fps),fps) for k,v in action.items()}
    launch_t,land_t=frame_time(launch,fps),frame_time(land,fps)
    flight_duration=land_t-launch_t
    start_air=None
    end_air=None
    descent=None
    apex_time=None
    plate_release=None
    max_error=0
    manifest_frames=[]
    # Slide along the table with constant wrist height; rotation is independent.
    def slide_dir(t):
        f=smoothstep((t-times["spin_start"])/(launch_t-times["spin_start"]))
        dx=-.025-.14*f
        return vector_to_plate(lead,lead_i,dx,support)
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame)
        t=frame_time(frame,fps)
        for name,actor in actors.items():
            yaw,pitch=sample(spec["head_turns"][name],t)
            pivot=pivots[name]
            pivot.rotation_euler=(pitch,0,yaw)
            pivot.keyframe_insert("rotation_euler",frame=frame)
            idx=reach_index[name]
            start=times[name+"_reach_start"]
            hit=times[name+"_contact"]
            if t<start:
                direction=idle
            elif t<hit:
                direction=blend_direction(idle,reach[name],(t-start)/(hit-start))
            elif frame<launch:
                direction=slide_dir(t) if name=="lead" and frame>=spin else reach[name]
            elif t<launch_t+.45:
                recoil=Vector((-.20 if name=="lead" else .20,-.48,.48))
                direction=blend_direction(reach[name],recoil,(t-launch_t)/.25)
            else:
                recoil=Vector((-.20 if name=="lead" else .20,-.48,.48))
                direction=blend_direction(recoil,idle,(t-launch_t-.45)/.60)
            key_pose(actor,idx,direction,frame,frame>=frame_at(action[name+"_contact"],fps) and frame<launch)
            other=1-idx
            other_dir=Vector((0,-.10,-.69))
            if name=="lead" and launch_t<=t<land_t+.4:
                other_dir=Vector((.12,-.48,.45))
            if name=="friend" and t>=times["payoff"]:
                other_dir=Vector((.08,-.4,-.57))
            key_pose(actor,other,other_dir,frame,False)
            tracks[name].key(frame,sample(spec["expressions"][name],t,True))
        # Continuous plate position: table, actual grip, then supported skid.
        lead_socket.rotation_euler.z=0 if frame<spin else 1.4*smoothstep((t-times["spin_start"])/(launch_t-times["spin_start"]))
        lead_socket.keyframe_insert("rotation_euler",frame=frame)
        if frame<contact:
            plate_bind.independent(frame,start_plate)
        elif frame<launch:
            plate.location=start_plate
            plate.rotation_euler=(0,0,0)
            plate.keyframe_insert("location",frame=frame)
            plate.keyframe_insert("rotation_euler",frame=frame)
            max_error=max(max_error,plate_bind.bind(frame))
            if frame==contact:
                assert (plate.matrix_world.translation-start_plate).length<1e-4
        else:
            if plate_release is None:
                plate_release=plate_bind.last_world.copy()
            dt=t-launch_t
            f=smoothstep(dt/.65)
            pos=plate_release.translation+Vector((-.12*f,.08*f,0))
            rot=plate_release.to_euler()
            rot.z+=2.6*f
            assert math.hypot(pos.x-.04,pos.y+.03)+radius<.65
            plate_bind.independent(frame,pos,rot)
        # Slice is on the same moving plate until launch.
        if frame<launch:
            head_bind.constraint.influence=0
            head_bind.constraint.keyframe_insert("influence",frame=frame)
            cake.location=start_plate+cake_offset
            cake.rotation_euler=(0,0,0)
            cake.keyframe_insert("location",frame=frame)
            cake.keyframe_insert("rotation_euler",frame=frame)
            max_error=max(max_error,slice_bind.bind(frame))
            state="plate"
        elif frame<land:
            if start_air is None:
                start_air=slice_bind.last_world.translation.copy()
                bpy.context.view_layer.update()
                end_air=head_socket.matrix_world.translation.copy()
                # Ballistic vertical arc with gravity; reuse GravityDrop for descent.
                g=9.81
                vz=(end_air.z-start_air.z+.5*g*flight_duration**2)/flight_duration
                apex_time=vz/g
                apex=Vector((0,0,start_air.z+.5*vz*vz/g))
                descent=GravityDrop(apex,end_air.z,gravity=g,restitution=0)
                assert abs(apex_time+descent.impact-flight_duration)<1e-5
            dt=t-launch_t
            f=dt/flight_duration
            pos=start_air.lerp(end_air,f)
            pos.z=start_air.z+(9.81*apex_time)*dt-.5*9.81*dt*dt if dt<apex_time else descent.at(dt-apex_time).z
            rot=(0,0,1.4*(1-f)+math.tau*f)
            slice_bind.independent(frame,pos,rot)
            head_bind.constraint.influence=0
            head_bind.constraint.keyframe_insert("influence",frame=frame)
            state="flight"
        else:
            # End at exact hair support, then bind to the head; no floating.
            bpy.context.view_layer.update()
            slice_bind.independent(frame,head_socket.matrix_world.translation,(0,0,0))
            max_error=max(max_error,head_bind.bind(frame))
            state="head"
        bpy.context.view_layer.update()
        assert abs(plate.matrix_world.translation.z-support)<1e-4
        pos=cake.matrix_world.translation.copy()
        if state=="head":
            assert (pos-head_socket.matrix_world.translation).length<1e-5
            assert abs(pos.z-spec["props"]["slice"]["head_support"])<1e-4
        manifest_frames.append({"frame":frame,"time":round(t,5),"slice_state":state,
            "slice_bottom":list(pos),"plate_bottom":list(plate.matrix_world.translation),
            "lead_expression":sample(spec["expressions"]["lead"],t,True),
            "friend_expression":sample(spec["expressions"]["friend"],t,True)})
    for bind in (plate_bind,slice_bind,head_bind):
        bind.constant_switches()
    for track in tracks.values():
        track.constant_switches()
    assert max_error<1e-5
    assert manifest_frames[-1]["slice_state"]=="head"
    assert (scene.frame_end-land+1)/fps>=1.5
    assert {x["slice_state"] for x in manifest_frames}=={"plate","flight","head"}

    # Every camera is built from shot data; one shared animation timeline,
    # no reconstruction or object teleport between shot cuts.
    shot_records=[]
    for shot in spec["shots"]:
        first=frame_at(shot["start"],fps)
        last=frame_at(shot["end"],fps)-1
        scene.frame_set(first)
        cfg=shot["camera"]
        bpy.ops.object.camera_add(location=cfg["position"])
        cam=bpy.context.object
        cam.name="Camera / "+shot["id"]
        cam.data.type="PERSP"
        cam.data.lens=cfg["lens"]
        point_at(cam,cfg["target"])
        subjects=[]
        for name in shot["characters"]:
            subjects.extend(o for o in actors[name].meshes if any(k in o.name for k in ("head","hair","fringe","beanie","torso" if shot["kind"]!="close_up" else "head")))
        # For the two-shots, the plate and cake at rest are part of the action.
        # Flight may intentionally leave shot 2 and enter shot 3.
        for _ in range(24):
            bounds=[]
            for f in (first,(first+last)//2,last):
                scene.frame_set(f)
                bpy.context.view_layer.update()
                objs=list(subjects)
                if shot["kind"]!="close_up":
                    objs+=list(plate.children_recursive)
                if f>=land or (f<launch and shot["kind"]!="close_up"):
                    objs+=list(cake.children_recursive)
                for obj in objs:
                    if obj.type=="MESH":
                        bounds.extend(world_to_camera_view(scene,cam,obj.matrix_world@Vector(c)) for c in obj.bound_box)
            if all(.04<=v.x<=.96 and .08<=v.y<=.96 and v.z>0 for v in bounds):
                break
            cam.data.lens*=.95
        else:
            raise RuntimeError("Could not frame shot "+shot["id"])
        marker=scene.timeline_markers.new(shot["id"],frame=first)
        marker.camera=cam
        shot_records.append({"id":shot["id"],"first":first,"last":last,"lens":cam.data.lens,
                             "bounds":[min(v.x for v in bounds),max(v.x for v in bounds),min(v.y for v in bounds),max(v.y for v in bounds)]})
    # Re-evaluate animation after all keys, not just during authoring.
    for item in manifest_frames:
        scene.frame_set(item["frame"])
        bpy.context.view_layer.update()
        assert (cake.matrix_world.translation-Vector(item["slice_bottom"])).length<.001
        assert (plate.matrix_world.translation-Vector(item["plate_bottom"])).length<.001
        for name,track in tracks.items():
            assert [n for n,o in track.decals.items() if not o.hide_render]==[item[name+"_expression"]]
    manifest={"story":spec["id"],"resolution":[width,height],"fps":fps,"duration":spec["duration"],
              "frame_count":scene.frame_end,"samples":samples,"shots":shot_records,"max_grip_error":max_error,
              "launch_frame":launch,"landing_frame":land,"head_support_z":spec["props"]["slice"]["head_support"],
              "payoff_hold_seconds":(scene.frame_end-frame_at(action["payoff"],fps)+1)/fps,
              "timeline":manifest_frames}
    (output/"story_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("STAGE_C_VALIDATED",json.dumps({k:v for k,v in manifest.items() if k!="timeline"}),flush=True)
    selected=[r for r in shot_records if a.shot=="all" or r["id"]==a.shot]
    if not selected:
        raise ValueError("Unknown shot "+a.shot)
    scene.frame_set(1)
    scene.render.filepath=str(output/"frame_")
    if a.shot in ("all",shot_records[0]["id"]):
        for image in bpy.data.images:
            if image.source=="GENERATED" and not image.packed_file:
                image.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(output/"story.blend"))
    scene.frame_start=selected[0]["first"]
    scene.frame_end=selected[-1]["last"]
    scene.frame_set(scene.frame_start)
    bpy.ops.render.render(animation=True)


if __name__=="__main__":
    main()
