"""Sleep-only supine motion. Native rigid R6, independent of fall."""
import math
import bpy
from mathutils import Matrix,Vector
from character_motion import ramp,mix,D,floor
from r6_character import group_points,mesh_points

def hip_center(actor):
    return sum((actor.armature.matrix_world@b.head for b in actor.legs),Vector((0,0,0)))/2

def rotate_world(actor,bone,axis,angle):
    # Rotate around the real pose-bone joint in world space, not whole actor.
    pb=actor.bones[bone];a=actor.armature.matrix_world
    pivot=a@pb.head
    transform=Matrix.Translation(pivot)@Matrix.Rotation(angle,4,axis)@Matrix.Translation(-pivot)
    pb.matrix=a.inverted()@transform@a@pb.matrix
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
    contacts=support_parts(actor)
    actor.root.location.z-=contacts["all"]-position[2]
    bpy.context.view_layer.update()
    phase="stand_to_ground_sit" if u<.25 else "ground_sit" if u<.27 else "backward_roll" if u<.56 else "head_settle" if u<.66 else "supine_breathing"
    return {"phase":phase,"flight":False,"lift":0,"sit_fraction":sit,"roll_fraction":roll,"head_rest_fraction":head_rest,"breath_angle":chest}

def sleep_diagnostics(actor):
    points=[actor.face.matrix_world@v.co for v in actor.face.data.vertices]
    normal=(points[1]-points[0]).cross(points[3]-points[0]).normalized()
    # Face decal vertex order gives outward -Y normal in the upright bind pose.
    torso=group_points(actor.body,actor.bones["torso"].name)
    return {"face_up_dot":normal.z,"support_z":support_parts(actor),"hip_world":list(hip_center(actor)),
            "chest_max_z":max(v.z for v in torso)}
