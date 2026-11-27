"""Reusable rigid R6 actions, actor space X right, -Y forward, +Z up.
No mesh transforms. No IK/physics: contact targets use measured bone sockets."""
import math
import bpy
from mathutils import Vector
from r6_character import mesh_points
from stage_b_interaction import GripAttachment,smoothstep

ACTIONS=("idle","walk","run","sit","stand_up","reach","throw","wave","point","hug","high_five","fall","sleep","eat","drink","hold_left","hold_right","hold_both")
DEFAULT=(0,0,-1)
def parameters(name,t=.5,side="right"):
    """Return arm directions, leg directions, head/torso Euler (rad), root pitch.
    t is normalized phase 0..1; cyclic actions may use unbounded t."""
    if name not in ACTIONS:raise ValueError(name)
    a=[DEFAULT,DEFAULT];l=[DEFAULT,DEFAULT];head=(0,0,0);torso=(0,0,0);pitch=0;seat=None
    u=min(1,max(0,t));k=math.sin(math.tau*t);i=0 if side=="right" else 1
    if name=="idle":head=(.025*k,0,.025*k);a=[(.025,-.04,-1),(-.025,-.04,-1)]
    elif name in ("walk","run"):
        amp=.50 if name=="walk" else .80
        for j,sign in enumerate((1,-1)):
            q=amp*k*sign
            a[j]=(0,math.sin(q),-math.cos(q));l[j]=(0,-math.sin(q),-math.cos(q))
        head=(.03*k,0,.03*k);torso=(.04 if name=="walk" else .14,0,0)
    elif name in ("sit","stand_up"):
        f=1 if name=="sit" else 1-smoothstep(u);angle=f*math.pi/2
        l=[(0,-math.sin(angle),-math.cos(angle))]*2
        a=[(.08,-.35,-.92),(-.08,-.35,-.92)];seat=.62*f
    elif name=="reach":a[i]=(.06,-.88,-.47);head=(.12,0,0)
    elif name=="throw":
        q=smoothstep(u);a[i]=(.14, .72*(1-q)-.93*q,.62*(1-q)-.22*q);torso=(0,0,.12*(1-2*q))
    elif name=="wave":a[i]=(.35+.20*k,-.10,.90);head=(0,0,-.10)
    elif name=="point":a[i]=(.05,-.99,.06);head=(0,0,.08)
    elif name=="hug":a=[(.30,-.91,.12),(-.30,-.91,.12)];head=(.08,0,0)
    elif name=="high_five":a[i]=(.25,-.58,.77)
    elif name=="fall":pitch=-1.38*smoothstep(u);a=[(.45,-.55,.65),(-.45,-.55,.65)];l=[(.08,-.25,-.96),(-.08,.22,-.96)]
    elif name=="sleep":pitch=math.pi/2;a=[(.10,0,-1),(-.10,0,-1)]
    elif name in ("eat","drink"):
        a[i]=(.33,-.87,.36) if name=="drink" else (.40,-.87,.23);head=(.10 if name=="eat" else -.10,0,0)
    elif name.startswith("hold_"):
        if name=="hold_both":a=[(.38,-.73,-.56),(-.38,-.73,-.56)]
        else:a[1 if name=="hold_left" else 0]=(.06,-.58,-.81)
    return {"arms":a,"legs":l,"head":head,"torso":torso,"pitch":pitch,"seat":seat}

def pose(actor,name,t=.5,position=(0,0,0),yaw=0,frame=None,side="right"):
    """Apply absolute pose, ground-adjust evaluated skin, optionally key bones.
    Position means support plane, except sit/stand_up which raise hips by seat.
    R6 limbs rigid; this is stylized FK, not elbow/knee or foot-lock IK."""
    p=parameters(name,t,side);actor.reset()
    actor.root.location=position;actor.root.rotation_euler=(p["pitch"],0,yaw)
    bpy.context.view_layer.update()
    actor.set_bone("torso",p["torso"],frame);actor.set_bone("head",p["head"],frame)
    for j in range(2):
        actor.aim_arm(j,p["arms"][j],frame);actor.aim_leg(j,p["legs"][j],frame)
    bpy.context.view_layer.update()
    # Place soles / lowest body surface against support. Seated poses have
    # horizontal legs and rest on a supplied chair height.
    z=min(v.z for ob in actor.skinned for v in mesh_points(ob))
    actor.root.location.z+=position[2]+(p["seat"] or 0)-z
    bpy.context.view_layer.update()
    if frame is not None:
        for path in ("location","rotation_euler"):actor.root.keyframe_insert(path,frame=frame)
    return p

def aim_at(actor,index,target,frame=None):
    """Aim measured rigid arm to world target; returns actual socket residual."""
    joint=actor.armature.matrix_world@actor.arms[index].head
    d=actor.root.matrix_world.to_3x3().inverted()@(Vector(target)-joint)
    actor.aim_arm(index,d,frame)
    return (actor.grips[index].matrix_world.translation-Vector(target)).length

def grip(actor,prop,hand="right",frame=1):
    """Bind root at socket, world-space exact. For both use dual_grip."""
    if hand not in ("left","right"):raise ValueError(hand)
    bind=GripAttachment(prop,actor.grips[0 if hand=="right" else 1])
    error=bind.bind(frame);assert error<1e-5
    return bind,error

def dual_grip(actor,prop,frame=1):
    """Support a bar-like prop at midpoint of two actual hand sockets.
    The prop local X endpoints must be +/- returned half_span. Update every
    frame for a moving pose; primary hand is a real bone-parented socket."""
    a,b=[o.matrix_world.translation.copy() for o in actor.grips]
    mid=(a+b)/2;span=(b-a).length
    assert span>.05
    socket=actor.attach_at(actor.root.name+" dual hold",actor.arms[0],actor.root.matrix_world.inverted()@mid)
    socket.rotation_mode="QUATERNION"
    from mathutils import Matrix
    socket.matrix_world=Matrix.Translation(mid)@(b-a).to_track_quat("X","Z").to_matrix().to_4x4()
    bpy.context.view_layer.update()
    bind=GripAttachment(prop,socket);error=bind.bind(frame)
    endpoints=[prop.matrix_world@Vector((sgn*span/2,0,0)) for sgn in (-1,1)]
    err=max((endpoints[0]-a).length,(endpoints[1]-b).length);assert err<1e-4,err
    return bind,span/2,err

def walk_path(actor,start,end,first,last,fps=12,cycle_seconds=.8,run=False):
    """Key every sample along straight path, facing movement. No foot lock."""
    a,b=Vector(start),Vector(end);d=b-a;yaw=math.atan2(d.x,-d.y)
    for f in range(first,last+1):
        bpy.context.scene.frame_set(f);u=(f-first)/max(1,last-first)
        pose(actor,"run" if run else "walk",(f-first)/fps/cycle_seconds,a.lerp(b,u),yaw,f)
    return {"frames":[first,last],"distance":d.length,"yaw":yaw,"cycle_seconds":cycle_seconds}
