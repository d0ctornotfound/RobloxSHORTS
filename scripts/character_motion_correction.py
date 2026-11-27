"""Opt-in Chapter 1 corrections, no changes to native R6 or imported cycles."""
import math
import bpy
from mathutils import Vector
from character_motion import weighted_params,jump_params,ramp,pulse,mix,D,floor,soles
from r6_character import group_points,bounds
from library_animation import parameters
from sleep_supine import apply_sleep_supine

def corrected_params(name,u,t):
    p=weighted_params(name,u,t)
    q=pulse(u,0,.30,.60,1)
    breath=math.sin(math.tau*t*.85)
    sway=math.sin(math.tau*t*.55)
    glance=pulse(u,.12,.38,.60,.91)
    if name=="jump":
        p=jump_params(t)
        if t>=1.1:
            a=pulse(t,1.1,1.27,1.36,1.96)
            p["legs"]=[(-.56*a,-.24*a,-1),(.56*a,.18*a,-1)]
            p["torso"]=(.48*a,.035*a,0);p["head"]=(-.21*a,0,.035*a)
            p["arms"]=[mix(D,(-.44,-.68,-.45),a),mix(D,(.44,-.68,-.45),a)]
        return p
    if name=="idle" or name.startswith("hold_"):
        hold=ramp(u,0,.27) if name!="idle" else 1
        p["torso"]=(.065*breath,.10*sway,.06*glance)
        p["head"]=(-.075*breath,.07*sway,.30*glance-.10*sway)
        p["arms"]=[mix(D,v,hold)+Vector((sgn*.05*sway,-.08*breath,.05*breath)) for v,sgn in zip(parameters(name,.5)["arms"],(-1,1))]
        p["legs"]=[(-.08,-.035*sway,-1),(.08,.035*sway,-1)]
    elif name in ("sit","stand_up"):
        f=ramp(u,.03,.78) if name=="sit" else 1-ramp(u,.12,.96)
        lean=pulse(u,0,.36,.63,.96)
        angle=1.05*f
        p["legs"]=[(0,-math.sin(angle),-math.cos(angle))]*2
        p["torso"]=(.33*lean*(1-f),0,0)
        p["head"]=(-.16*lean,0,.08*glance)
        p["arms"]=[mix(D,(-.19,-.60,-.76),max(.7*f,lean)),mix(D,(.19,-.60,-.76),max(.7*f,lean))]
        p["seat"]=0;p["seated_fraction"]=f
    elif name in ("reach","throw"):
        p["legs"]=[D,D]
        if name=="reach":
            p["arms"]=[mix(D,(-.20,-.91,-.37),q),mix(D,(.18,.30,-.94),q)]
            p["torso"]=(.22*q,.07*q,-.19*q);p["head"]=(-.11*q,0,.23*q)
        else:
            p["torso"]=(p["torso"][0],.10*q,p["torso"][2]*1.35)
            p["head"]=(p["head"][0],.04*q,p["head"][2]-.10*q)
    elif name=="wave":
        a=pulse(u,0,.20,.78,1);w=math.sin(math.tau*2.2*t)
        p["arms"]=[mix(D,(-.73-.18*w,-.13,.57+.18*math.cos(math.tau*2.2*t)),a),mix(D,(.16,-.18,-.96),a)]
        p["torso"]=(.06*a,.12*a+.045*sway,.24*a);p["head"]=(-.06*a,-.09*a,-.37*a+.04*breath)
    elif name=="point":
        p["arms"]=[mix(D,(-.12,-.97,.04),q),mix(D,(.24,.18,-.94),q)]
        p["torso"]=(.25*q,.11*q,-.19*q);p["head"]=(-.10*q,-.06*q,.30*q)
        p["legs"]=[(-.06,-.10*q,-1),(.06,.08*q,-1)]
    elif name=="hug":
        a=pulse(u,.16,.46,.70,1);s=pulse(u,.45,.58,.64,.75)
        p["arms"]=[mix(D,(.48,-.87,.06+.10*s),a),mix(D,(-.48,-.87,.06+.10*s),a)]
        p["torso"]=(.18*a+.07*s,0,.06*a);p["head"]=(-.08*a,.14*a,.10*a)
        walk=pulse(u,.01,.14,.20,.34)-pulse(u,.72,.83,.88,1)
        p["legs"]=[(-.08,-.4*walk,-1),(.08,.3*walk,-1)]
    elif name=="high_five":
        p["torso"]=(.13*q,.16*q,-.12*q);p["head"]=(-.13*q,-.08*q,.19*q)
        p["legs"]=[(-.08,-.07*q,-1),(.08,.07*q,-1)]
    elif name=="fall":
        slow=False;b=ramp(u,.03,.30 if slow else .20)
        lower=ramp(u,.20,.75 if slow else .60);settle=ramp(u,.63,.99);sign=1 if slow else -1
        p["pitch"]=sign*math.pi/2*lower
        p["legs"]=[(-.12,-.55*b*(1-lower),-1),(.12,.40*b*(1-lower),-1)]
        p["torso"]=(sign*.46*b*(1-lower)+.055*breath*settle,.12*b*(1-settle),.10*b*(1-settle))
        p["head"]=(-sign*.40*lower*(1-settle)+.05*breath*settle,.13*(1-settle)*lower,.07*settle)
        brace=pulse(u,.07,.29,.55,.9)
        p["arms"]=[mix(D,(-.55,-.54,.10 if slow else .62),brace),mix(D,(.55,-.54,.10 if slow else .62),brace)]
        p["arms"]=[mix(v,(sgn*.16,-.17,-1),settle) for v,sgn in zip(p["arms"],(-1,1))]
    elif name in ("eat","drink"):
        if name=="eat":
            a=pulse(u,.01,.23,.33,.46)+pulse(u,.46,.63,.73,.98)
            p["arms"]=[mix(D,(-.44,-.86,.18),a),mix(D,(.15,-.30,-.94),.55*q)]
            p["head"]=(.20*a,.08*a,-.11*a);p["torso"]=(.13*a,.045*sway,.08*a)
        else:
            a=pulse(u,.01,.32,.70,.98)
            p["arms"]=[mix(D,(-.46,-.76,.38),a),mix(D,(.14,-.18,-.97),.45*a)]
            p["head"]=(-.28*a,.07*a,-.10*a);p["torso"]=(-.13*a,.045*sway,.06*a)
    return p

def apply_corrected(actor,name,u,t,position=(0,0,0),yaw=0,anchor=None):
    if name=="sleep":return apply_sleep_supine(actor,u,t,position,yaw)
    p=corrected_params(name,u,t)
    actor.reset();actor.root.location=position;actor.root.rotation_euler=(p["pitch"],0,yaw)
    if name in ("sit","stand_up"):
        actor.root.location+=Vector((-.20*math.sin(yaw),.20*math.cos(yaw),0))*p["seated_fraction"]
    bpy.context.view_layer.update()
    actor.set_bone("torso",p["torso"]);actor.set_bone("head",p["head"])
    for i in range(2):
        actor.aim_arm(i,p["arms"][i]);actor.aim_leg(i,p["legs"][i])
    actor.root.location.z+=position[2]+p["lift"]-floor(actor)
    bpy.context.view_layer.update()
    if name in ("reach","throw") and anchor is not None:
        delta=anchor-soles(actor)[0];delta.z=0
        actor.root.location+=delta;bpy.context.view_layer.update()
    return p

def rear_hip(actor):
    pts=group_points(actor.body,actor.bones["torso"].name)
    inv=actor.root.matrix_world.inverted();lo,hi=bounds(inv@v for v in pts)
    rear=[v for v in pts if (inv@v).y>(lo.y+hi.y)/2-.01]
    return min(v.z for v in rear),lo,hi

def seat_geometry(actor,yaw):
    apply_corrected(actor,"sit",1,59/30,yaw=yaw)
    top,lo,hi=rear_hip(actor)
    center=actor.root.matrix_world@Vector(((lo.x+hi.x)/2,hi.y-.055,0))
    return top,center,(hi.x-lo.x+.12,.30)

def sole_tilt(actor):
    result=[]
    for i,b in enumerate(actor.legs):
        v=(actor.armature.matrix_world@b.matrix).to_3x3()@actor.leg_axes[i]
        result.append(math.degrees(math.acos(max(-1,min(1,-v.normalized().z)))))
    return result

def face_blocked(scene,cam,actor):
    pts=[actor.face.matrix_world@v.co for v in actor.face.data.vertices]
    c=sum(pts,Vector((0,0,0)))/len(pts);dx=(pts[1]-pts[0])*.5;dz=(pts[3]-pts[0])*.5
    direction=(cam.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    dg=bpy.context.evaluated_depsgraph_get();count=0
    for x in (-.55,-.275,0,.275,.55):
        for z in (-.52,-.26,0,.26,.52):
            target=c+dx*x+dz*z
            hit,loc,n,idx,obj,m=scene.ray_cast(dg,target-direction*20,direction,distance=19.999)
            if hit and obj and obj.original==actor.body:count+=1
    return count
