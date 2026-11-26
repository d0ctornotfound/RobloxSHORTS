"""Data-driven café story renderer. Blender 4.0 compatible."""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix,Euler
from bpy_extras.object_utils import world_to_camera_view
from render_demo import empty,point_at
from stage_a_cafe import light
from render_stills import configure
from r6_character import R6Character,mesh_points,group_points,bounds,SOURCE_SHA256
from quality_cafe import build as build_cafe
from stage_a_cafe import set_visible
from stage_b_interaction import blend_direction,smoothstep,GripAttachment,GravityDrop,ExpressionTrack
from stage_c_props import build_plate_and_slice


def args():
    p=argparse.ArgumentParser()
    p.add_argument("--story",default="stories/the_last_slice.json")
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--output",default="render/story")
    p.add_argument("--shot",default="all")
    p.add_argument("--validate-only",action="store_true")
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


def shoulder(actor,index):
    return actor.armature.matrix_world@actor.arms[index].head

def arm_length(actor,index):
    return (actor.grips[index].matrix_world.translation-shoulder(actor,index)).length

def seat(actor,x,y,chair_name):
    # Native leg axes are measured from evaluated weighted vertices. Pose the
    # actual rigid leg bones forward, and place the rear thigh on the seat.
    actor.root.location=(x,y,0)
    bpy.context.view_layer.update()
    for i in range(2):actor.aim_leg(i,(0,-1,-.035))
    bpy.context.view_layer.update()
    hip=actor.armature.matrix_world@actor.legs[0].head
    points=[v for pb in actor.legs for v in group_points(actor.body,pb.name)]
    rear=[v for v in points if v.y>=hip.y-.28]
    assert rear,"no rear thigh vertices"
    actor.root.location.z=.67-min(v.z for v in rear)
    bpy.context.view_layer.update()
    chair=bpy.data.objects.get(chair_name)
    if chair:
        chair.location.x=x;chair.location.y=y-.10;chair.rotation_euler.z=0
        chair.scale.x=1.65
    return actor.root.location.z

def rim_contact(actor,index,center,radius,length,side):
    # Exact intersection of the horizontal projection of the arm reach sphere
    # with the plate rim. Arm end is at the upper edge, not plate center.
    j=shoulder(actor,index);z=center.z+.060
    dz=z-j.z
    assert dz<-.035 and abs(dz)<length,("shoulder too low/high",actor.role,list(j),length,dz)
    reach=math.sqrt(length*length-dz*dz)
    dvec=Vector((center.x-j.x,center.y-j.y));d=dvec.length
    assert abs(reach-radius)<d<reach+radius,("rim unreachable",actor.role,d,reach,radius)
    unit=dvec/d;perp=Vector((-unit.y,unit.x))
    along=(reach*reach-radius*radius+d*d)/(2*d)
    height=math.sqrt(max(0,reach*reach-along*along))
    xy=Vector((j.x,j.y))+unit*along
    opts=[Vector((q.x,q.y,z)) for q in (xy+perp*height,xy-perp*height)]
    target=min(opts,key=lambda q:side*q.x)
    direction=(target-j).normalized()
    assert direction.y<-.25 and direction.z<0,("non-forward reach",actor.role,list(direction))
    return target,direction

def key_pose(actor,index,direction,frame):
    actor.aim_arm(index,direction,frame)

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
    fps,width,height,samples=(12,432,768,24) if a.profile=="preview" else (24,1080,1920,96)
    scene=configure(a.profile)
    scene.cycles.samples=samples
    scene.cycles.max_bounces=4
    scene.cycles.diffuse_bounces=2
    scene.cycles.adaptive_threshold=.065 if a.profile=="preview" else .02
    scene.cycles.use_denoising=False
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.05
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.42,.31,.21,1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.20
    scene.render.use_persistent_data=True
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.fps=fps
    scene.frame_start=1
    scene.frame_end=round(spec["duration"]*fps)
    for cup in build_cafe():
        set_visible(cup,False)
    # Extend the opaque envelope, keep the dressed rear wall and window.
    floor=bpy.data.objects.get("Tiled floor")
    floor.scale.y*=2.2;floor.location.y=-3.0
    for ob in bpy.data.objects:
        if ob.name.startswith(("Left enclosed café wall","Right enclosed café wall","Side wall wooden wainscot","Side wall chair rail","High café ceiling")):
            ob.scale.y*=2.1;ob.location.y=-3.4;ob.visible_camera=True
    light("Integration neutral frontal bounce",(0,-3.0,3.4),(0,1.0,1.65),290,4.2,(1,.94,.87))
    light("Integration rear set wash",(0,-.65,4.8),(0,2.4,2.5),170,3.5,(1,.93,.83))
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.30
    actors={name:R6Character(name,"lead" if cfg["lead"] else "friend") for name,cfg in spec["characters"].items()}
    lead,friend=actors["lead"],actors["friend"]
    plate,cake=build_plate_and_slice(spec["props"]["plate"]["radius"])
    support=spec["props"]["plate"]["support_z"];radius=spec["props"]["plate"]["radius"]
    cake_offset=Vector(spec["props"]["slice"]["plate_offset"])
    start_plate=Vector((.04,-.03,support))
    reach_index={}
    lengths={}
    seats={}
    for name,actor in actors.items():
        side=1 if name=="lead" else -1
        x=-.93 if name=="lead" else .93
        chair="Chair 1" if name=="lead" else "Chair 2"
        seats[name]=seat(actor,x,.80,chair)
        # Select the actual inward arm by joint position, not assumed naming.
        idx=max(range(2),key=lambda i:side*shoulder(actor,i).x)
        reach_index[name]=idx
        length=arm_length(actor,idx);lengths[name]=length
        j=shoulder(actor,idx);rimx=start_plate.x-side*radius
        dz=support+.060-j.z;dx=rimx-j.x
        assert length*length>dx*dx+dz*dz,("reach setup",name,length,dx,dz)
        desired_y=start_plate.y+math.sqrt(length*length-dx*dx-dz*dz)
        actor.root.location.y+=desired_y-j.y
        bpy.data.objects[chair].location.y=actor.root.location.y-.10
        bpy.context.view_layer.update()
        print("R6_SEATED_REACH",name,"root",list(actor.root.location),"shoulder",list(shoulder(actor,idx)),"arm length",length,flush=True)
    lead_i,friend_i=reach_index["lead"],reach_index["friend"]
    # Rest hair top derived from actual imported-rig accessory mesh vertices.
    hair_vertices=[v for ob in lead.accessories if "head hair" in ob.name or "head fringe" in ob.name for v in mesh_points(ob)]
    highest=max(hair_vertices,key=lambda v:v.z)
    headlo,headhi=bounds(mesh_points(lead.head))
    crown=(headlo+headhi)/2
    head_support_z=highest.z-.045
    cake_site=Vector((crown.x+.025,crown.y-.025,head_support_z))
    assert any(abs(v.x-cake_site.x)<.20 and abs(v.y-cake_site.y)<.20 and v.z>=head_support_z-.025 for v in hair_vertices)
    head_local=lead.root.matrix_world.inverted()@cake_site
    head_socket=lead.attach_at("Lead / bone-parented cake landing", "head",head_local,(.08,-.10,math.pi/2))
    head_bind=GripAttachment(cake,head_socket)
    patrons=[]
    for role,pos,label in [("patron_green",(-2.62,1.24,0),"Side table chair 0"),("patron_blue",(2.65,1.92,0),"Window table chair 0")]:
        patron=R6Character(role,role);seat(patron,pos[0],pos[1],label)
        patron.pose("happy");patron.aim_arm(0,(.15,-.55,-.82));patron.aim_arm(1,(-.15,-.55,-.82))
        patrons.append(patron)
    tracks={name:ExpressionTrack(actor) for name,actor in actors.items()}
    idle=Vector((0,-.18,-.98)).normalized()
    reach={name:rim_contact(actor,reach_index[name],start_plate,radius,lengths[name],1 if name=="lead" else -1)[1] for name,actor in actors.items()}
    # Bone-parented secondary socket at plate center; actual hand is measured
    # against the rim on every bound frame. Counter-rotate the plate so the
    # block hand can move without tilting the supported plate through the table.
    lead_socket=lead.attach_at("Lead / bone-parented plate center",lead.arms[lead_i],lead.root.matrix_world.inverted()@start_plate)
    plate_bind=GripAttachment(plate,lead_socket)
    plate_top=empty("Plate / slice support",cake_offset,plate)
    slice_bind=GripAttachment(cake,plate_top)
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
    max_friend_rim_error=0
    manifest_frames=[]
    max_hand_error=0
    max_lead_rim_error=0
    max_reach_z=-1
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame);t=frame_time(frame,fps)
        spin_f=smoothstep((t-times["spin_start"])/(launch_t-times["spin_start"]))
        center=start_plate+Vector((-.09*spin_f,.015*spin_f,0))
        for name,actor in actors.items():
            yaw,pitch=sample(spec["head_turns"][name],t)
            actor.set_bone("head",(pitch,0,yaw),frame)
            idx=reach_index[name];start=times[name+"_reach_start"];hit=times[name+"_contact"]
            target,exact=rim_contact(actor,idx,center,radius,lengths[name],1 if name=="lead" else -1)
            if t<start:direction=idle
            elif t<hit:direction=blend_direction(idle,reach[name],(t-start)/(hit-start))
            elif frame<launch:direction=exact
            elif t<launch_t+.45:
                recoil=Vector((-.28 if name=="lead" else .28,-.74,-.26))
                direction=blend_direction(reach[name],recoil,(t-launch_t)/.25)
            else:
                recoil=Vector((-.28 if name=="lead" else .28,-.74,-.26))
                direction=blend_direction(recoil,idle,(t-launch_t-.45)/.60)
            key_pose(actor,idx,direction,frame)
            if frame>=frame_at(action[name+"_contact"],fps) and frame<launch:
                err=(actor.grips[idx].matrix_world.translation-target).length
                max_hand_error=max(max_hand_error,err)
                max_reach_z=max(max_reach_z,direction.z)
                assert err<.001,("bone hand missed rim",name,frame,err,list(actor.grips[idx].matrix_world.translation),list(target))
            other_dir=Vector((0,-.12,-.99))
            if name=="lead" and launch_t<=t<land_t+.4:other_dir=Vector((.20,-.80,-.28))
            if name=="friend" and t>=times["payoff"]:other_dir=Vector((.08,-.48,-.78))
            key_pose(actor,1-idx,other_dir,frame)
            tracks[name].key(frame,sample(spec["expressions"][name],t,True))
        lead_socket.matrix_world=Matrix.Translation(center)@Euler((0,0,1.4*spin_f)).to_matrix().to_4x4()
        for path in ("location","rotation_euler","scale"):lead_socket.keyframe_insert(path,frame=frame)
        bpy.context.view_layer.update()
        if contact<=frame<launch:
            grip=lead.grips[lead_i].matrix_world.translation
            max_lead_rim_error=max(max_lead_rim_error,abs(math.hypot(grip.x-center.x,grip.y-center.y)-radius))
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
        if friend_contact<=frame<launch:
            friend_grip=friend.grips[friend_i].matrix_world.translation
            pc=plate.matrix_world.translation
            rim_error=abs(math.hypot(friend_grip.x-pc.x,friend_grip.y-pc.y)-radius)
            max_friend_rim_error=max(max_friend_rim_error,rim_error)
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
            assert abs(pos.z-head_support_z)<.04
        manifest_frames.append({"frame":frame,"time":round(t,5),"slice_state":state,
            "slice_bottom":list(pos),"plate_bottom":list(plate.matrix_world.translation),
            "lead_expression":sample(spec["expressions"]["lead"],t,True),
            "friend_expression":sample(spec["expressions"]["friend"],t,True)})
    for patron in patrons:
        for ob in patron.meshes:
            ob.hide_render=False;ob.keyframe_insert("hide_render",frame=1)
            ob.hide_render=True;ob.keyframe_insert("hide_render",frame=frame_at(spec["shots"][1]["start"],fps))
            constant_action(ob,["hide_render"])
    for bind in (plate_bind,slice_bind,head_bind):
        bind.constant_switches()
    for track in tracks.values():
        track.constant_switches()
    assert max_error<1e-5
    assert max_friend_rim_error<.16, max_friend_rim_error
    assert max_lead_rim_error<.001 and max_hand_error<.001 and max_reach_z<0
    assert manifest_frames[-1]["slice_state"]=="head"
    assert (scene.frame_end-land+1)/fps>=1.5
    assert {x["slice_state"] for x in manifest_frames}=={"plate","flight","head"}

    # Every camera is built from shot data; one shared animation timeline,
    # no reconstruction or object teleport between shot cuts.
    shot_records=[]
    # Keep all cameras within the physical opaque enclosure.
    for shot in spec["shots"]:
        first=frame_at(shot["start"],fps)
        last=frame_at(shot["end"],fps)-1
        scene.frame_set(first)
        # Cache true animated world bounds for all frames, so the search
        # optimizes both framing and minimum hero coverage before any render.
        two=shot["kind"]!="close_up"
        def corners(ob):
            return mesh_points(ob)
        camera_samples=[]
        for f in range(first,last+1):
            scene.frame_set(f);bpy.context.view_layer.update()
            hero={};safe=[];faces={}
            for name in shot["characters"]:
                actor=actors[name]
                hero[name]=[v for ob in actor.meshes if ob.type=="MESH" and ob!=actor.face for v in corners(ob)]
                selected=[ob for ob in actor.meshes if any(k in ob.name for k in ("head","hair","beanie"))]
                if shot["id"]=="02_reach":
                    active=actor.arms[reach_index[name]]
                    safe.extend(group_points(actor.body,active.name))
                safe.extend(v for ob in selected for v in corners(ob))
                # Face center is separate from the large hair bounds; disallow
                # a camera that puts the two face centers on top of each other.
                face=actor.face
                faces[name]=sum(corners(face),Vector())/len(corners(face))
            if two and shot["id"]!="04_payoff":
                safe.extend(v for ob in plate.children_recursive if ob.type=="MESH" for v in corners(ob))
            if f>=land or (f<launch and two):
                safe.extend(v for ob in cake.children_recursive if ob.type=="MESH" for v in corners(ob))
            camera_samples.append((hero,safe,faces))
        bpy.ops.object.camera_add();cam=bpy.context.object
        cam.name="Camera / "+shot["id"];cam.data.sensor_fit="HORIZONTAL"
        # Prioritize frontal readable two-shots, no cutaway cameras.
        candidates=[]
        if two:
            sign=-1 if shot["id"]=="02_reach" else 1
            target_z={"01_notice":1.60,"02_reach":1.65,"04_payoff":1.88}[shot["id"]]
            for angle in (0,8,15,20,25):
                r=4.4
                theta=math.radians(angle)*sign
                candidates.append(("PERSP",(r*math.sin(theta), .72-r*math.cos(theta),2.42 if shot["id"]=="02_reach" else 2.30),(0,.72,target_z),57))
        else:
            candidates=[("PERSP",(-.93,-1.85,2.25),(-.93,.72,2.12),53)]
        best=None;best_failed=None
        for mode,pos,target,lens in candidates:
            cam.location=pos;cam.data.type=mode;point_at(cam,target)
            if mode=="ORTHO":cam.data.ortho_scale=lens
            else:cam.data.lens=lens
            for _ in range(75):
                bpy.context.view_layer.update()
                bounds=[world_to_camera_view(scene,cam,v) for _,safe,_ in camera_samples for v in safe]
                if all(.035<=v.x<=.965 and .045<=v.y<=.97 and v.z>0 for v in bounds):break
                if mode=="ORTHO":cam.data.ortho_scale*=1.025
                else:cam.data.lens*=.98
            else:continue
            coverage=[];separations=[]
            for hero,safe,faces in camera_samples:
                row={}
                for name,verts in hero.items():
                    vv=[world_to_camera_view(scene,cam,v) for v in verts]
                    row[name]=min(1,max(v.y for v in vv))-max(0,min(v.y for v in vv))
                coverage.append(row)
                if two:
                    v1,v2=[world_to_camera_view(scene,cam,faces[k]) for k in shot["characters"]]
                    separations.append(abs(v1.x-v2.x))
            mincov={name:min(row[name] for row in coverage) for name in shot["characters"]}
            score=min(mincov.values())
            rec=(score,mode,pos,target,cam.data.lens,cam.data.ortho_scale,mincov,bounds,min(separations,default=1))
            if best_failed is None or score>best_failed[0]:best_failed=rec
            if rec[-1]>=.18 and score>=.45:
                best=rec;break
            if rec[-1]>=.18 and score>=.30 and best is None:
                best=rec
        if best is None:
            raise RuntimeError("Framing failed "+shot["id"]+" best="+str(best_failed[:7] if best_failed else None))
        _,mode,pos,target,lens,ortho,mincov,bounds,face_separation=best
        cam.location=pos;cam.data.type=mode;cam.data.lens=lens;cam.data.ortho_scale=ortho;point_at(cam,target)
        assert abs(pos[0])<3.70 and -6.0<pos[1]<2.30
        print("SHOT_COVERAGE",shot["id"],mincov,"mode",mode,"face separation",face_separation,"position",pos,flush=True)
        marker=scene.timeline_markers.new(shot["id"],frame=first)
        marker.camera=cam
        shot_records.append({"id":shot["id"],"first":first,"last":last,"lens":cam.data.lens,"camera_type":mode,"ortho_scale":ortho if mode=="ORTHO" else None,"min_face_separation":face_separation,"camera_position":list(pos),"patrons_visible":shot["id"]=="01_notice","coverage_goal_met":min(mincov.values())>=.45,
                             "bounds":[min(v.x for v in bounds),max(v.x for v in bounds),min(v.y for v in bounds),max(v.y for v in bounds)],"min_hero_vertical_coverage":mincov})
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
              "launch_frame":launch,"landing_frame":land,"head_support_z":head_support_z,"hair_highest_z":highest.z,"cake_embed_depth_below_tip":highest.z-head_support_z,"max_friend_rim_error":max_friend_rim_error,"rig":"source GLB R6 armature","source_sha256":SOURCE_SHA256,"seated_root_z":seats,"arm_lengths":lengths,"max_hand_target_error":max_hand_error,"max_lead_rim_error":max_lead_rim_error,"max_reach_direction_z":max_reach_z,"patrons":2,
              "payoff_hold_seconds":(scene.frame_end-frame_at(action["payoff"],fps)+1)/fps,
              "timeline":manifest_frames}
    (output/"story_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("STAGE_C_VALIDATED",json.dumps({k:v for k,v in manifest.items() if k!="timeline"}),flush=True)
    if a.validate_only:return
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
