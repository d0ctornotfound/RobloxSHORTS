"""Absolute body reactions; no unpaired major expression swaps.
Right R6 arm index 0 is actor-local -X; left index 1 is +X."""
import math
import bpy
from mathutils import Vector
from r6_character import mesh_points,group_points
from library_animation import pose
from library_camera import project
from stage_b_interaction import smoothstep

BEATS={
 "anticipate":("worried",(.11,0,-.12),(.10,0,-.08),[(-.32,-.24,-.92),(.32,-.24,-.92)]),
 "greet":("happy",(-.06,0,.12),(-.04,0,.08),[(-.92,-.06,.38),(.15,-.12,-.98)]),
 "confident":("smug",(-.10,0,.10),(-.08,0,.06),[(-.22,-.25,-.94),(.22,-.25,-.94)]),
 "recoil":("shocked",(-.22,0,-.05),(-.18,0,-.06),[(-.83,-.15,.28),(.83,-.15,.28)]),
 "embarrassed":("sad",(.20,0,-.12),(.13,0,-.08),[(-.18,-.18,-.97),(.18,-.18,-.97)]),
 "laugh":("laughing",(-.22,0,.13),(-.12,0,.07),[(-.24,-.42,-.87),(.25,-.42,-.87)]),
 "point":("happy",(.10,0,-.18),(.07,0,-.10),[(-.65,-.48,-.55),(.12,-.1,-.99)])
}
def envelope(t,rise=.20,hold=.42,fall=.38):
    if t<rise:return smoothstep(t/rise)
    if t<rise+hold:return 1.
    return 1-smoothstep((t-rise-hold)/fall)
def act(actor,kind,t,position,yaw=0,major=True):
    expr,head,torso,arms=BEATS[kind]
    u=max(0,min(1,t));h=smoothstep(min(1,u/.16));b=smoothstep(min(1,max(0,u-.09)/.25))
    # Gesture is a brief pulse and remains lateral to the face.
    g=envelope(u) if kind=="greet" else b
    pose(actor,"idle",u,position,yaw)
    actor.set_bone("head",tuple(h*x for x in head))
    actor.set_bone("torso",tuple(b*x for x in torso))
    for i,d in enumerate(arms):
        actor.aim_arm(i,Vector((0,0,-1)).lerp(Vector(d),g if kind=="greet" and i==0 else b))
    bpy.context.view_layer.update()
    floor=min(v.z for ob in actor.skinned for v in mesh_points(ob))
    actor.root.location.z+=position[2]-floor;bpy.context.view_layer.update()
    if major and b<.25:actor.pose("neutral")
    else:actor.pose(expr)
    return {"beat":kind,"expression":expr if b>=.25 or not major else "neutral","head_weight":h,"body_weight":b,"gesture_weight":g}
def face_clear(scene,cam,actor,occluders=()):
    """Conservative projected arm overlap in the face decal rectangle, with
    camera depth. Actual ray samples confirm visible face surface; geometric
    proxy is not a recognition model. Other actor/prop occlusion also tested."""
    face=mesh_points(actor.face);fb=project(scene,cam,face)
    arms=[]
    for bone in actor.arms:arms.append(group_points(actor.body,bone.name))
    area=max(1e-10,(fb[1]-fb[0])*(fb[3]-fb[2]))
    overlap=0
    for pts in arms:
        b=project(scene,cam,pts)
        if b[4]<fb[4]+.02:
            overlap+=max(0,min(b[1],fb[1])-max(b[0],fb[0]))*max(0,min(b[3],fb[3])-max(b[2],fb[2]))/area
    # Ray toward points slightly in front of decal plane, from camera.
    # Face mesh itself is transparent and not a body occluder.
    deps=bpy.context.evaluated_depsgraph_get();c=sum(face,Vector())/len(face);visible=0;total=0
    # Use interior samples rather than transparent decal border.
    for u in (.30,.50,.70):
        for v in (.30,.50,.70):
            p=face[0].lerp(face[1],u).lerp(face[3].lerp(face[2],u),v)
            direction=p-cam.location;dist=direction.length
            hit,loc,normal,index,obj,matrix=scene.ray_cast(deps,cam.location,direction.normalized(),distance=max(.01,dist-.004))
            if not hit:visible+=1
            total+=1
    return {"arm_overlap_upper_bound":min(1,overlap),"face_ray_fraction":visible/total,"pass":overlap<=.10 and visible/total>=.78}
