"""Sleep-only supine motion. Native rigid R6, independent of fall."""
import math
import bpy
from mathutils import Matrix,Vector
from character_motion import ramp,mix,D,floor
from r6_character import group_points,mesh_points,face_material
from pathlib import Path
from tempfile import TemporaryDirectory
from r6_variant_textures import face,character_face

def hip_center(actor):
    return sum((actor.armature.matrix_world@b.head for b in actor.legs),Vector((0,0,0)))/2

def rotate_world(actor,bone,axis,angle):
    # Rotate around the real pose-bone joint in world space, not whole actor.
    pb=actor.bones[bone];a=actor.armature.matrix_world
    pivot=a@pb.head
    transform=Matrix.Translation(pivot)@Matrix.Rotation(angle,4,axis)@Matrix.Translation(-pivot)
    pb.matrix=a.inverted()@transform@a@pb.matrix
    bpy.context.view_layer.update()

def translate_world(actor,pb,delta):
    a=actor.armature.matrix_world
    pb.matrix=a.inverted()@Matrix.Translation(delta)@a@pb.matrix
    bpy.context.view_layer.update()

def sleep_face(actor,closed):
    if not closed:
        actor.pose("neutral");return
    key="sleep_closed"
    if key not in actor.face_materials:
        # Sleep-only decal: preserve all existing expression files and materials.
        with TemporaryDirectory(prefix="r6_sleep_") as tmp:
            identity={"lead":"young","dad":"dad","friend":"friend","teacher":"teacher","librarian":"teacher"}.get(actor.role,"young")
            image=character_face(key,identity) if identity in ("friend","teacher") else face(key,identity)
            image.save(Path(tmp)/(key+".png"))
            actor.face_materials[key]=face_material(key,tmp)
    actor.pose(key)

def chest_expand(actor,rise):
    # Expand only the torso front vertically about the back support plane.
    # Hold immediate child pose matrices in armature space so the head and
    # limbs do not rise, slide or acquire inherited scale. No rig edits.
    if rise<=0:return
    pb=actor.bones["torso"];a=actor.armature.matrix_world
    pts=group_points(actor.body,pb.name)
    lo=min(v.z for v in pts);hi=max(v.z for v in pts)
    assert hi-lo>.01
    children=[(b,b.matrix.copy()) for b in pb.children]
    pivot=Vector((0,0,lo))
    transform=Matrix.Translation(pivot)@Matrix.Diagonal((1,1,1+rise/(hi-lo),1))@Matrix.Translation(-pivot)
    pb.matrix=a.inverted()@transform@a@pb.matrix
    bpy.context.view_layer.update()
    for b,m in children:
        b.matrix=m
        bpy.context.view_layer.update()

def support_parts(actor):
    torso=group_points(actor.body,actor.bones["torso"].name)
    head_objects=[actor.head]+[o for o in actor.accessories if o!=actor.face and o.parent_bone==actor.bones["head"].name]
    head=[v for o in head_objects for v in mesh_points(o)]
    legs=[v for b in actor.legs for v in group_points(actor.body,b.name)]
    points=[v for o in actor.meshes if o!=actor.face for v in mesh_points(o)]
    return {"torso":min(v.z for v in torso),"head_with_hair":min(v.z for v in head),"legs":min(v.z for v in legs),"all":min(v.z for v in points)}

def apply_sleep_supine(actor,u,seconds,position=(0,0,0),yaw=0):
    # Four-second review: upright -> ground sit -> backward roll -> head rest -> breathe.
    # Negative root X pitch rotates the -Y front normal UP, never face down.
    sit=ramp(u,.01,.25);roll=ramp(u,.27,.56);head_rest=ramp(u,.51,.66)
    pitch=-math.pi/2*roll
    tuck=.30*ramp(u,.23,.43)*(1-head_rest)
    chest=.045*ramp(u,.64,.69)*(1+math.sin(math.tau*.70*(seconds-2.64)))*.5
    # At least 8x the former measured 0.00153 scene-unit chest rise.
    # 0.020 peak front expansion, independently of the old subtle torso tilt.
    breath_rise=.020*ramp(u,.64,.69)*(1+math.sin(math.tau*.70*(seconds-2.64)))*.5
    torso_delay=.19*ramp(u,.27,.38)*(1-ramp(u,.40,.56))
    actor.reset();actor.root.location=position;actor.root.rotation_euler=(0,0,yaw)
    bpy.context.view_layer.update()
    hip=hip_center(actor)
    backward=Vector((-math.sin(yaw),math.cos(yaw),0))
    target=hip+backward*(.18*sit)
    lateral=Vector((math.cos(yaw),math.sin(yaw),0))
    actor.root.rotation_euler=(pitch,0,yaw);bpy.context.view_layer.update()
    rotate_world(actor,"torso",lateral,torso_delay+chest+.16*math.sin(math.pi*sit)*(1-roll))
    rotate_world(actor,"head",lateral,tuck-chest)
    # Keep legs forward horizontally after sitting; compensate root tilt.
    inverse=Matrix.Rotation(-pitch,3,"X")
    for i,sgn in enumerate((-1,1)):
        leg_angle=math.pi/2*sit
        leg=Vector((sgn*.025*roll,-math.sin(leg_angle),-math.cos(leg_angle)))
        actor.aim_leg(i,inverse@leg)
        brace=ramp(u,.12,.32)*(1-ramp(u,.48,.65))
        arm=mix(D,(sgn*.45,.48,-.68),brace)
        arm=mix(arm,(sgn*.24,-.06,-1),ramp(u,.55,.70))
        actor.aim_arm(i,arm)
    bpy.context.view_layer.update()
    # Keep hip XY fixed through the backward roll, not a sliding whole-body tip.
    delta=target-hip_center(actor);delta.z=0
    actor.root.location+=delta;bpy.context.view_layer.update()
    # Rigid R6 hip joints are at the torso base, with 0.223 units of
    # leg thickness below the joint when horizontal. Pose-only hip socket
    # compression during the seated phase raises each thigh into the hip
    # volume, then releases it through the recline. Do not sink limbs below
    # the floor to obtain the seat number. Preserve the original hip XY path.
    seat_weight=ramp(u,.12,.25)*(1-ramp(u,.27,.55))
    seat_offsets=[]
    torso_floor=min(v.z for v in group_points(actor.body,actor.bones["torso"].name))
    for b in actor.legs:
        leg_floor=min(v.z for v in group_points(actor.body,b.name))
        offset=max(0,torso_floor-leg_floor-.012)*seat_weight
        translate_world(actor,b,Vector((0,0,offset)))
        seat_offsets.append(offset)
    # Bracing arms cannot become the lowest support and suspend the hips.
    # During the same compression window, aim them more horizontally if
    # necessary; preserve shoulder joints and leave other actions unchanged.
    for i,b in enumerate(actor.arms):
        for k in range(6):
            arm_floor=min(v.z for v in group_points(actor.body,b.name))
            if arm_floor>=torso_floor-.012 or seat_weight<.001:break
            sg=(-1,1)[i]
            # In actor coordinates, raise the brace gradually.
            actor.aim_arm(i,mix(D,(sg*.60,.50,-.15+.09*k),seat_weight))
    chest_expand(actor,breath_rise)
    contacts=support_parts(actor)
    actor.root.location.z-=contacts["all"]-position[2]
    bpy.context.view_layer.update()
    phase="stand_to_ground_sit" if u<.25 else "ground_sit" if u<.27 else "backward_roll" if u<.56 else "head_settle" if u<.66 else "supine_breathing"
    closed=head_rest>=.999
    sleep_face(actor,closed)
    return {"phase":phase,"flight":False,"lift":0,"sit_fraction":sit,"roll_fraction":roll,"head_rest_fraction":head_rest,"breath_angle":chest,"requested_chest_rise":breath_rise,"seated_hip_pose_offsets":seat_offsets,"eyes_closed":closed,"face_material":actor.face.data.materials[0].name}

def sleep_diagnostics(actor):
    points=[actor.face.matrix_world@v.co for v in actor.face.data.vertices]
    normal=(points[1]-points[0]).cross(points[3]-points[0]).normalized()
    # Face decal vertex order gives outward -Y normal in the upright bind pose.
    torso=group_points(actor.body,actor.bones["torso"].name)
    return {"face_up_dot":normal.z,"support_z":support_parts(actor),"hip_world":list(hip_center(actor)),
            "chest_max_z":max(v.z for v in torso)}
