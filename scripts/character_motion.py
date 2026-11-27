"""Character-only weighted R6 motion v1. Opt-in; old story poses untouched.
No prop geometry. Rigid legs cannot bend at knees: anticipation uses hip
splay/torso compression, never squashes mesh or invents joints."""
import math
import bpy
from mathutils import Vector
from library_animation import parameters,ACTIONS,aim_at
from r6_character import mesh_points,dominant_group
from stage_b_interaction import smoothstep

MOTIONS=tuple(ACTIONS)+("jump",)
D=Vector((0,0,-1))
def ramp(t,a,b):return smoothstep(max(0,min(1,(t-a)/max(1e-8,b-a))))
def pulse(t,a,b,c,d):return ramp(t,a,b)*(1-ramp(t,c,d))
def mix(a,b,u):return Vector(a).lerp(Vector(b),u)
def blend_e(a,b,u):return tuple(x+(y-x)*u for x,y in zip(a,b))
def floor(actor):
    return min(v.z for ob in actor.skinned for v in mesh_points(ob))
def soles(actor):
    # actual evaluated sole points for the dominant leg vertex groups.
    v=mesh_points(actor.body)
    result=[]
    for b in actor.legs:
        ids=[i.index for i in actor.body.data.vertices if dominant_group(actor.body,i)==b.name]
        low=min(v[i].z for i in ids)
        ids=[i for i in ids if v[i].z<=low+.025]
        result.append(Vector((sum(v[i].x for i in ids)/len(ids),sum(v[i].y for i in ids)/len(ids),low)))
    return result
def jump_params(t):
    # Seconds, 30Hz: takeoff at .5, touchdown at 1.1, 0.6s ballistic flight.
    launch=.5;land=1.1
    crouch=pulse(t,.08,.37,.37,.5)
    absorb=pulse(t,land,land+.10,land+.15,1.65)
    thrust=pulse(t,.36,.5,.56,.70)
    air=max(0,min(1,(t-launch)/(land-launch)))
    flight=launch<t<land
    tuck=math.sin(math.pi*air) if flight else 0
    lift=.5*9.81*(t-launch)*(land-t) if flight else 0
    # Both legs are rigid. Modest symmetric hip splay compresses silhouette;
    # after touchdown return to exact neutral feet and recover through torso.
    spread=.28*crouch+.08*tuck
    legs=[(-spread,-.16*tuck,-1),(spread,.18*tuck,-1)]
    arms=[]
    for sign in (-1,1):
        back=(sign*.18,.65,-.72)
        up=(sign*.28,-.42,.83)
        base=mix(D,back,crouch)
        base=mix(base,up,max(thrust,.74*tuck))
        base=mix(base,(sign*.38,-.32,-.80),absorb)
        arms.append(base)
    return {"arms":arms,"legs":legs,"head":(-.10*thrust+.12*crouch+.13*absorb,0,0),
       "torso":(.26*crouch-.13*thrust+.25*absorb,0,0),"pitch":0,"seat":0,
       "lift":lift,"phase":"anticipation" if t<launch else "flight" if flight else "landing_recovery","flight":flight}
def weighted_params(name,u,seconds):
    if name=="jump":return jump_params(seconds)
    # Reusable full gesture timing: deliberate windup, readable action,
    # follow-through, settle. Static holds remain held but breathe.
    b=parameters(name,u)
    neutral=parameters("idle",seconds*.75)
    q=pulse(u,.05,.32,.58,.96)
    pre=pulse(u,0,.13,.16,.32)
    settle=pulse(u,.56,.71,.73,.98)
    if name=="idle":
        breath=math.sin(math.tau*seconds*.75)
        b["torso"]=(.015*breath,.025*breath,.015*breath)
        b["head"]=(.025*breath,0,.028*math.sin(math.tau*seconds*.48))
        b["arms"]=[(-.06,-.035-.025*breath,-1),(.06,-.035+.025*breath,-1)]
    elif name in ("sit","stand_up"):
        f=ramp(u,.12,.63) if name=="sit" else 1-ramp(u,.17,.68)
        angle=f*math.pi/2
        b["legs"]=[(0,-math.sin(angle),-math.cos(angle))]*2
        # Empty studio mime: unsupported seated pose, no invented chair.
        b["seat"]=.62*f
        thrust=pulse(u,.04,.23,.47,.76)
        b["torso"]=(.32*thrust+.06*f,0,0);b["head"]=(-.12*thrust,0,0)
        b["arms"]=[mix(D,(-.18,-.68,-.75),thrust),mix(D,(.18,-.68,-.75),thrust)]
    elif name=="throw":
        wind=ramp(u,.06,.30);release=ramp(u,.35,.53);recover=ramp(u,.63,.98)
        arm=mix(D,(-.28,.78,.48),wind)
        arm=mix(arm,(-.12,-.92,.18),release)
        arm=mix(arm,(-.20,-.38,-.87),ramp(u,.54,.70))
        b["arms"]=[mix(arm,D,recover),mix(D,(.28,-.40,-.80),pulse(u,.05,.30,.54,.9))]
        b["torso"]=(.13*release*(1-recover),0,-.24*wind*(1-release)+.22*release*(1-recover))
        b["head"]=(.07*release*(1-recover),0,-.07*wind*(1-release))
        b["legs"]=[(-.08,-.16*release*(1-recover),-1),(.08,.10*release*(1-recover),-1)]
    elif name=="fall":
        wobble=pulse(u,0,.15,.22,.38);drop=ramp(u,.27,.68)
        b["pitch"]=-1.38*drop
        b["arms"]=[mix(D,(-.60,-.35,.65),max(wobble,drop)),mix(D,(.60,-.35,.65),max(wobble,drop))]
        b["torso"]=(-.12*wobble,0,.14*wobble);b["head"]=(-.16*wobble,0,-.10*wobble)
        b["legs"]=[(-.10,-.20*drop,-1),(.10,.20*drop,-1)]
    elif name=="sleep":
        down=ramp(u,.06,.62)
        b["pitch"]=math.pi/2*down;b["head"]=(.06*math.sin(seconds*math.tau*.65)*down,0,0)
        b["arms"]=[mix(D,(-.10,0,-1),down),mix(D,(.10,0,-1),down)]
    elif name=="wave":
        # Explicit lateral oscillation with delayed torso and head response.
        active=pulse(u,.06,.24,.74,.96)
        b["arms"]=[mix(D,(-.82-.10*math.sin(seconds*math.tau*2.6),-.10,.45+.13*math.cos(seconds*math.tau*2.6)),active),D]
        b["torso"]=(.04*pre,0,.07*active);b["head"]=(-.06*active,0,-.09*active)
    elif name.startswith("hold_"):
        hold=ramp(u,.04,.30);breath=.025*math.sin(seconds*math.tau*.7)*hold
        b["arms"]=[mix(D,a,hold) for a in b["arms"]]
        b["torso"]=(.06*hold+breath,0,.03*hold);b["head"]=(.09*hold,0,.02*math.sin(seconds*3))
    elif name in ("reach","point","hug","high_five","eat","drink"):
        if name in ("eat","drink"):q=pulse(u,.08,.35,.60,.93)
        b["arms"]=[mix(D,a,q) for a in b["arms"]]
        if name in ("reach","point","eat","drink"):
            b["arms"][0]=mix(b["arms"][0],(-.15,.16,-.95),.40*pre)
        lean=.14*q+.08*pre-.045*settle
        b["torso"]=(lean if name!="drink" else -.08*q,0,.05*q)
        b["head"]=(.11*q if name!="drink" else -.18*q,0,-.05*q)
        if name=="reach":b["legs"]=[(-.08,-.13*q,-1),(.08,.07*q,-1)]
    else:raise ValueError("Use imported StrideLock for walk/run: "+name)
    b.update(lift=0,flight=False,phase="anticipation" if u<.30 else "action" if u<.70 else "recovery")
    return b

def apply_weighted(actor,name,u,seconds,position=(0,0,0),yaw=0):
    p=weighted_params(name,u,seconds)
    actor.reset();actor.root.location=position;actor.root.rotation_euler=(p["pitch"],0,yaw)
    bpy.context.view_layer.update()
    actor.set_bone("torso",p["torso"]);actor.set_bone("head",p["head"])
    for i in range(2):
        actor.aim_arm(i,p["arms"][i]);actor.aim_leg(i,p["legs"][i])
    bpy.context.view_layer.update()
    actor.root.location.z+=position[2]+(p["seat"] or 0)+p["lift"]-floor(actor)
    bpy.context.view_layer.update()
    return p

def high_five_contact(a,b,u):
    # True socket intersection target for two rigid arms, no prop.
    ia=1;ib=0
    ja=a.armature.matrix_world@a.arms[ia].head;jb=b.armature.matrix_world@b.arms[ib].head
    ra=(a.grips[ia].matrix_world.translation-ja).length;rb=(b.grips[ib].matrix_world.translation-jb).length
    delta=jb-ja;dist=delta.length
    if not abs(ra-rb)<dist<ra+rb:return None
    axis=delta.normalized();x=(ra*ra-rb*rb+dist*dist)/(2*dist)
    up=Vector((0,0,1));up=(up-axis*up.dot(axis)).normalized()
    target=ja+axis*x+up*math.sqrt(max(0,ra*ra-x*x))
    weight=pulse(u,.08,.40,.61,.96)
    for actor,index in ((a,ia),(b,ib)):
        j=actor.armature.matrix_world@actor.arms[index].head
        cur=actor.grips[index].matrix_world.translation-j
        direction=cur.normalized().lerp((target-j).normalized(),weight)
        actor.aim_arm(index,actor.root.matrix_world.to_3x3().inverted()@direction)
    return (a.grips[ia].matrix_world.translation-b.grips[ib].matrix_world.translation).length
