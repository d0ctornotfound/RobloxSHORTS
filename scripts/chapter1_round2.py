"""Round-two candidate motions. Only rejected clips; frozen poses untouched."""
import math,bpy
from mathutils import Vector,Matrix
from character_motion import D,ramp,pulse,mix,floor
from character_motion_correction import corrected_params,apply_corrected,rear_hip
from chapter1_articulation import Articulation,face_grid,face_hits,hug_overlap,tree_for_object

def new_params(name,u,t):
    p=corrected_params(name,u,t)
    beat=pulse(u,0,.30,.60,1)
    breath=math.sin(math.tau*t*1.4)
    if name in ("sit","stand_up"):
        f=ramp(u,0,.83) if name=="sit" else 1-ramp(u,.08,1)
        lean=math.sin(math.pi*f)
        p.update(seated_fraction=f,torso=(.42*lean,0,0),head=(-.25*lean,0,.16*math.sin(math.tau*u)),legs=[D,D])
        p["arms"]=[mix(D,(-.22,.60,-.70),f),mix(D,(.22,.60,-.70),f)]
    elif name in ("reach","point"):
        wind=pulse(u,0,.17,.25,.43);hit=pulse(u,.23,.46,.69,1)
        recoil=pulse(u,.64,.80,.86,1);bob=math.sin(math.tau*3.5*t)*hit*.055
        p["legs"]=[D,D]
        p["head"]=(-.13*hit+.11*wind+bob,0,.36*ramp(u,.01,.25)*(1-ramp(u,.75,1)))
        p["torso"]=(.32*hit-.17*wind-.12*recoil,.09*hit,-.35*wind+.34*hit-.09*recoil)
        a=mix(D,(-.23,.70,-.60),wind)
        a=mix(a,(-.18,-1,.05 if name=="point" else -.22),hit)
        p["arms"]=[a,mix(D,(.30,.48,-.78),hit)]
        if name=="point":p["arms"][0]=mix(a,(-.15,-1,.12+bob),hit)
        p["step"]=ramp(u,.10,.49)*(1-ramp(u,.62,1))
    elif name=="jump" and t>=1.1:
        a=pulse(t,1.1,1.28,1.38,1.96)
        p["legs"]=[D,D];p["torso"]=(.50*a,0,0);p["head"]=(-.23*a,0,.04*a)
        p["arms"]=[mix(D,(-.45,-.68,-.45),a),mix(D,(.45,-.68,-.45),a)]
        p["absorb"]=.90*a
    elif name=="fall":
        buckle=pulse(u,.02,.19,.29,.47);stagger=pulse(u,.05,.23,.31,.48);drop=ramp(u,.29,.74);settle=ramp(u,.70,.99)
        p["pitch"]=math.pi/2*drop
        p["torso"]=(.32*buckle+.22*drop*(1-settle),.17*stagger,.13*stagger)
        p["head"]=(-.38*drop*(1-settle)-.18*buckle,.10*stagger,.12*stagger)
        flail=pulse(u,.06,.22,.59,.91);catch=pulse(u,.30,.51,.72,.95)
        p["arms"]=[mix(mix(D,(-.76,.1,.54),flail),(-.37,-.75,-.51),catch),
                   mix(mix(D,(.78,-.24,.50),flail),(.36,-.83,-.44),catch)]
        p["legs"]=[(-.12,-.55*stagger,-1),(.10,.25*stagger,-1)]
        p["buckle"]=buckle;p["stagger"]=stagger;p["drop"]=drop
    elif name in ("eat","drink"):
        if name=="eat":
            a=pulse(u,.02,.22,.31,.48)+pulse(u,.49,.67,.76,1)
            p["head"]=(.21*a+.045*breath*a,0,-.10*a)
            p["torso"]=(.10*a,.055*a,-.10*a)
        else:
            a=pulse(u,.02,.32,.67,1)
            swallow=pulse(u,.39,.53,.57,.73)
            p["head"]=(-.35*a-.10*swallow,0,-.08*a)
            p["torso"]=(-.15*a,.055*breath,.09*a)
        p["mouth_action"]=a
        p["arms"]=[D,mix(D,(.21,-.32,-.91),a)]
    return p

def basic(actor,p,pos,yaw):
    actor.reset();actor.root.location=pos;actor.root.rotation_euler=(p["pitch"],0,yaw);bpy.context.view_layer.update()
    actor.set_bone("torso",p["torso"]);actor.set_bone("head",p["head"])
    for i in range(2):actor.aim_arm(i,p["arms"][i]);actor.aim_leg(i,p["legs"][i])
    bpy.context.view_layer.update()

def neutral_feet(actor,art,yaw):
    p=new_params("sit",0,0);basic(actor,p,(0,0,0),yaw);art.rigid()
    art.shift(Vector((0,0,-floor(actor))))
    return [(l.lower.matrix_world@Vector((0,0,-l.b))) for l in art.legs]

def seat_setup(actor,art,yaw,feet):
    p=new_params("sit",1,59/30);basic(actor,p,(0,0,0),yaw);art.rigid();art.planted(feet,yaw,math.pi/2)
    top,lo,hi=rear_hip(actor);root=actor.root.matrix_world
    center=root@Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2+.13,0))
    return top,center,(hi.x-lo.x+.60,hi.y-lo.y+.34)

def pose(actor,art,name,u,t,yaw,feet=None,landing=None,seat=None):
    p=new_params(name,u,t);basic(actor,p,(0,0,0),yaw);art.rigid()
    rot=art.rot(yaw);forward=rot@Vector((0,-1,0))
    if name in ("sit","stand_up"):
        f=p["seated_fraction"];art.planted(feet,yaw,math.pi/2*f)
        if seat:
            top,center,wh=seat
            press=pulse(u,.01,.22,.70,.99) if name=="stand_up" else ramp(u,.12,.74)
            for i,l in enumerate(art.arms):
                sign=(-1,1)[i]
                rest=l.transform()@l.end
                target=center+rot@Vector((sign*(wh[0]/2-.08),-.05,0));target.z=top+.035
                art.arm_target(i,rest.lerp(target,press),rot@Vector((sign,.25,-.3)),yaw)
    elif name in ("reach","point"):
        step=p["step"];f=[v.copy() for v in feet];f[1]+=forward*.16*step
        f[1].z+=.055*(pulse(u,.10,.24,.31,.49)+pulse(u,.62,.75,.83,1))
        art.planted(f,yaw,.15+.23*step)
    elif name=="jump":
        if t>=1.1:
            if landing is None:
                art.shift(Vector((0,0,-floor(actor))))
                landing=[l.lower.matrix_world@Vector((0,0,-l.b)) for l in art.legs]
            art.planted(landing,yaw,p.get("absorb",0))
        else:art.shift(Vector((0,0,p["lift"]-floor(actor))))
    elif name=="fall":
        if u<.30:
            f=[v.copy() for v in feet];f[1]+=forward*.24*p["stagger"];f[1].z+=.10*p["stagger"]
            art.planted(f,yaw,.68*p["buckle"])
        else:
            # Torso/head/arms already move independently; release the legs
            # from the stagger as the weight passes beyond support.
            actor.root.location+=forward*(.24*ramp(u,.30,.70));bpy.context.view_layer.update();art.rigid()
            art.shift(Vector((0,0,-floor(actor))))
    else:
        art.shift(Vector((0,0,-floor(actor))))
    return p,landing

def mouth_pose(actor,art,name,p,cam,cup,yaw):
    a=p["mouth_action"];c,dx,dz=face_grid(actor)
    mouth=c-.32*dz
    normal=dx.cross(dz).normalized()
    side=-dx.normalized()
    up=dz.normalized()
    rest=art.arms[0].transform()@art.arms[0].end
    # Contact comes from below and far side. The target is the actual lip
    # location, not a hard-coded arm orientation near the cheek.
    if name=="eat":
        target=mouth+side*.095-up*.10+normal*.045
    else:
        axis=up.lerp((up-normal*.65).normalized(),a)
        offset=axis*.16-side*.055
        target=mouth+normal*.075-offset
    end=art.arm_target(0,rest.lerp(target,a),side+normal*.20-up*.35,yaw)
    if cup:
        # Cup rim center and true nearest point on the rim circumference;
        # the hand stays on the side, not in front of the eyes.
        rim=end+offset
        cup.location=rim-axis*.10;cup.rotation_mode="QUATERNION";cup.rotation_quaternion=Vector((0,0,1)).rotation_difference(axis)
        bpy.context.view_layer.update()
        v=mouth-rim;plane=v-axis*v.dot(axis)
        rim_gap=math.hypot(v.dot(axis),plane.length-.085)
    else:rim_gap=None
    blockers=[actor.body]+[o for limb in art.arms for o in limb.objects]+([cup] if cup else [])
    blocked=face_hits(cam,actor,blockers)
    nearest=tree_for_object(art.arms[0].lower).find_nearest(mouth)
    return {"face_body_blocked_samples":blocked,"hand_to_mouth":float(nearest[3]) if nearest[0] is not None else None,
            "cup_rim_to_mouth":rim_gap,"mouth_action":a}

def hug(a,b,u,t):
    p=new_params("hug",u,t);eng=pulse(u,.10,.40,.72,1);squeeze=pulse(u,.42,.55,.65,.76)
    # Facing across X, not oblique crossing shoulders. Right and left arm
    # tracks are asymmetric in elevation so the two rigid arms pass at sides.
    best=None
    for spread in (.32,.48,.64,.80):
        for spacing in (.39,.44,.49):
            distance=.98-(.98-spacing)*eng
            for actor,sign in ((a,1),(b,-1)):
                actor.reset();actor.root.location=(-sign*distance,0,0);actor.root.rotation_euler=(0,0,sign*math.pi/2);bpy.context.view_layer.update()
                actor.set_bone("torso",(.065*eng+.025*squeeze,0,0));actor.set_bone("head",(-.10*eng,.11*eng,0))
                for i,sg in enumerate((-1,1)):
                    # One higher/outward arm, opposite lower/inside arm.
                    z=-.48 if i==0 else -.84
                    x=sg*(spread if i==0 else spread*.58)
                    actor.aim_arm(i,mix(D,(x,-.87,z),eng))
                    actor.aim_leg(i,p["legs"][i])
                actor.root.location.z-=floor(actor);actor.pose("happy")
            bpy.context.view_layer.update()
            overlaps=hug_overlap(a,b)
            score=(overlaps,abs(spacing-.39)+.15*spread)
            if best is None or score<best[0]:best=(score,spread,spacing)
            if overlaps==0:break
        if best[0][0]==0:break
    # Reapply winning arrangement, since final evaluated candidate may differ.
    _,spread,spacing=best;distance=.98-(.98-spacing)*eng
    for actor,sign in ((a,1),(b,-1)):
        actor.reset();actor.root.location=(-sign*distance,0,0);actor.root.rotation_euler=(0,0,sign*math.pi/2);bpy.context.view_layer.update()
        actor.set_bone("torso",(.065*eng+.025*squeeze,0,0));actor.set_bone("head",(-.10*eng,.11*eng,0))
        for i,sg in enumerate((-1,1)):
            actor.aim_arm(i,mix(D,(sg*(spread if i==0 else spread*.58),-.87,-.48 if i==0 else -.84),eng))
            actor.aim_leg(i,p["legs"][i])
        actor.root.location.z-=floor(actor);actor.pose("happy")
    bpy.context.view_layer.update()
    p.update(engagement=eng,intersections=hug_overlap(a,b),spread=spread,spacing=spacing)
    return p
