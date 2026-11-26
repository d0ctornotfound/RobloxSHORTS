"""Five-second portrait preview: reach, grip, lift, fumble, land, react."""
import argparse
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import point_at
from render_stills import configure
from stage_a_character import Character,palette
from stage_a_cafe import build_cafe,set_visible
from stage_b_interaction import aim_arm,key_arm,blend_direction,GripAttachment,GravityDrop,ExpressionTrack


def arguments():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--output",default="render/cafe")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])


def main():
    a=arguments()
    output=Path(a.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    scene=configure(a.profile)
    fps,width,height,samples=(12,360,640,8) if a.profile=="preview" else (24,1080,1920,24)
    duration=5
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.fps=fps
    scene.cycles.samples=samples
    scene.cycles.max_bounces=4
    scene.render.use_persistent_data=True
    scene.frame_start=1
    scene.frame_end=fps*duration
    cup,spare=build_cafe()
    set_visible(spare,False)
    p=palette()
    lead=Character("Series lead",p,True)
    friend=Character("Cafe friend",p,False)
    lead.root.location=(-1.04,.30,0)
    friend.root.location=(.57,1.12,0)
    friend.root.rotation_euler.z=-.12
    lead_track=ExpressionTrack(lead)
    friend_track=ExpressionTrack(friend)

    # Find an exact, reachable tabletop position for the wrist socket.
    support_z=1.18
    dx=.24
    dz=support_z+.145-1.72
    dy=-math.sqrt(.70**2-dx**2-dz**2)
    reach=Vector((dx,dy,dz)).normalized()
    idle=Vector((.04,-.11,-.69)).normalized()
    lift=Vector((.43,-.49,.26)).normalized()
    fumble=Vector((.39,-.53,.23)).normalized()
    recoil=Vector((-.12,-.48,.49)).normalized()
    socket=aim_arm(lead,1,reach)
    start_cup=socket.matrix_world.translation.copy()
    assert abs(start_cup.z-support_z)<1e-5, start_cup
    assert math.hypot(start_cup.x-.04,start_cup.y+.03)+.151<.65
    attachment=GripAttachment(cup,socket)
    left_idle=Vector((.02,-.05,-.70))
    left_react=Vector((.25,-.50,.40))
    friend_idle=Vector((0,-.04,-.70))
    friend_react=Vector((-.20,-.55,.35))

    grip_frame=round(1.25*fps)+1
    release_frame=round(2.75*fps)+1
    drop=None
    data=[]
    max_error=0
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame)
        t=(frame-1)/fps
        if t<.40:
            direction=idle
        elif frame<grip_frame:
            direction=blend_direction(idle,reach,(t-.40)/.85)
        elif t<1.85:
            direction=blend_direction(reach,lift,(t-1.25)/.60)
        elif t<2.35:
            direction=lift
        elif frame<release_frame:
            direction=blend_direction(lift,fumble,(t-2.35)/.40)
            # Deliberate short, readable hesitation in the last held frames.
            direction=(direction+Vector((.035*math.sin((t-2.35)*34),0,0))).normalized()
        elif t<3.20:
            direction=blend_direction(fumble,recoil,(t-2.75)/.22)
        else:
            direction=blend_direction(recoil,idle,(t-3.20)/.65)
        aim_arm(lead,1,direction)
        key_arm(lead,1,frame,grip_frame<=frame<release_frame)
        alarm=release_frame<=frame and t<3.55
        left=blend_direction(left_idle,left_react,(t-2.75)/.25) if alarm else left_idle
        if t>=3.55:
            left=blend_direction(left_react,left_idle,(t-3.55)/.5)
        aim_arm(lead,0,left)
        key_arm(lead,0,frame,False)
        for i in (0,1):
            react=friend_react if i==0 else Vector((.20,-.55,.35))
            direction_friend=blend_direction(friend_idle,react,(t-2.75)/.25) if alarm else friend_idle
            if t>=3.55:
                direction_friend=blend_direction(react,friend_idle,(t-3.55)/.5)
            aim_arm(friend,i,direction_friend)
            key_arm(friend,i,frame,False)
        if frame<grip_frame:
            attachment.independent(frame,start_cup)
            state="reach" if t>=.40 else "table"
        elif frame<release_frame:
            # Key unconstrained world channels too; constraint is the actual parent.
            cup.location=start_cup
            cup.rotation_euler=(0,0,0)
            cup.keyframe_insert("location",frame=frame)
            cup.keyframe_insert("rotation_euler",frame=frame)
            max_error=max(max_error,attachment.bind(frame))
            if frame==grip_frame:
                assert (cup.matrix_world.translation-start_cup).length<1e-4
            state="grip" if frame==grip_frame else ("fumble" if t>=2.35 else "lift")
        else:
            if drop is None:
                drop=GravityDrop(attachment.release(),support_z,center=(.04,-.03),radius=.65)
            elapsed=(frame-release_frame)/fps
            attachment.independent(frame,drop.at(elapsed))
            state="rest" if elapsed>=drop.settle else "fall"
        lead_expr="neutral" if t<1.25 else ("happy" if frame<release_frame else ("shocked" if t<3.65 else "sad"))
        friend_expr="neutral" if frame<release_frame else ("shocked" if t<3.65 else "sad")
        lead_track.key(frame,lead_expr)
        friend_track.key(frame,friend_expr)
        bpy.context.view_layer.update()
        pos=cup.matrix_world.translation
        assert pos.z>=support_z-1e-4, (frame,pos.z)
        if state=="rest":
            assert abs(pos.z-support_z)<1e-5
        data.append({"frame":frame,"time":round(t,4),"state":state,
                     "cup_bottom":[round(x,5) for x in pos],
                     "lead_expression":lead_expr,"friend_expression":friend_expr})
    assert drop is not None and data[-1]["state"]=="rest"
    assert max(x["cup_bottom"][2] for x in data)>support_z+.30
    assert {"table","reach","grip","lift","fumble","fall","rest"}<=set(x["state"] for x in data)
    attachment.constant_switches()
    lead_track.constant_switches()
    friend_track.constant_switches()

    # One perspective shot. Legs may crop for medium composition, faces,
    # grip, moving cup and table top must stay within the portrait safe area.
    bpy.ops.object.camera_add(location=(-.46,-4.25,2.03))
    camera=bpy.context.object
    scene.camera=camera
    camera.data.type="PERSP"
    camera.data.lens=39
    point_at(camera,(-.42,.10,1.83))
    table=bpy.data.objects.get("Cafe table top")
    safe=[o for o in lead.meshes if any(k in o.name for k in ("head","hair","fringe","torso"))]
    safe += [o for o in friend.meshes if any(k in o.name for k in ("head","beanie"))]
    safe += list(cup.children_recursive)+[table]
    safe += [o for o in lead.meshes if o.parent==lead.wrists[1]]
    for _ in range(24):
        bounds=[]
        for frame in range(1,scene.frame_end+1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            for obj in safe:
                bounds.extend(world_to_camera_view(scene,camera,obj.matrix_world@Vector(c)) for c in obj.bound_box)
        if all(.045<=v.x<=.955 and .045<=v.y<=.955 and v.z>0 for v in bounds):
            break
        camera.data.lens*=.95
    else:
        raise RuntimeError("Stage B camera cannot fit action")
    # Validate final evaluated animation rather than just the authored positions.
    for item in data:
        scene.frame_set(item["frame"])
        bpy.context.view_layer.update()
        assert (cup.matrix_world.translation-Vector(item["cup_bottom"])).length<.001
        if item["state"] in ("grip","lift","fumble"):
            assert (cup.matrix_world.translation-socket.matrix_world.translation).length<1e-5
        for track,key in ((lead_track,"lead_expression"),(friend_track,"friend_expression")):
            assert [name for name,obj in track.decals.items() if not obj.hide_render]==[item[key]]
    manifest={"resolution":[width,height],"fps":fps,"duration_seconds":duration,
              "frames":scene.frame_end,"samples":samples,"grip_frame":grip_frame,
              "release_frame":release_frame,"max_grip_error":max_error,
              "support_z":support_z,"impact_seconds_after_release":drop.impact,
              "settle_seconds_after_release":drop.settle,
              "camera_lens_mm":camera.data.lens,
              "safe_bounds":[min(v.x for v in bounds),max(v.x for v in bounds),
                             min(v.y for v in bounds),max(v.y for v in bounds)],
              "timeline":data}
    (output/"interaction.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("STAGE_B_VALIDATED",json.dumps({k:v for k,v in manifest.items() if k!="timeline"}),flush=True)
    scene.frame_set(1)
    scene.render.filepath=str(output/"frame_")
    bpy.ops.wm.save_as_mainfile(filepath=str(output/"cafe_interaction.blend"))
    bpy.ops.render.render(animation=True)


if __name__=="__main__":
    main()
