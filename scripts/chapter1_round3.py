"""Round-three candidate poses. Existing approved motions stay frozen."""
import math,bpy
from mathutils import Vector
from character_motion import D,ramp,pulse,mix,floor
from chapter1_round2 import new_params as old_params,basic,pose as old_pose,neutral_feet,seat_setup
from chapter1_articulation import Articulation,face_grid,face_hits,tree_for_object,clip
from mathutils.bvhtree import BVHTree
from r6_character import group_points,bounds,mesh_points

def new_params(name,u,t):
    p=old_params(name,u,t)
    if name=="point":
        lead=ramp(u,.02,.20)*(1-ramp(u,.78,1))
        hit=pulse(u,.22,.41,.72,.99)
        bob=.065*math.sin(math.tau*3.0*t)*hit
        p["head"]=(bob,0,-.42*(1-lead))
        p["torso"]=(.12*hit,0,-.12*(1-hit))
        # Straight rigid native R6 arm, directed forward, at shoulder height.
        # The camera sees that forward axis in three-quarter profile.
        p["arms"]=[mix(D,(0,-1,0),hit),mix(D,(.18,.30,-.92),hit)]
        p["step"]=ramp(u,.12,.43)*(1-ramp(u,.73,.99))
    return p

def pose(actor,art,name,u,t,yaw,feet=None,landing=None,seat=None):
    if name!="point":
        return old_pose(actor,art,name,u,t,yaw,feet,landing,seat)
    p=new_params(name,u,t);basic(actor,p,(0,0,0),yaw);art.rigid()
    forward=art.rot(yaw)@Vector((0,-1,0))
    step=p["step"];f=[v.copy() for v in feet];f[1]+=forward*.13*step
    f[1].z+=.04*(pulse(u,.12,.24,.29,.43)+pulse(u,.73,.82,.87,.99))
    art.planted(f,yaw,.13+.17*step)
    return p,landing

def rim_gap(mouth,cup):
    # Distance to actual polygon rim segments, not an idealized point.
    verts=[cup.matrix_world@cup.data.vertices[32+i].co for i in range(32)]
    result=[]
    for a,b in zip(verts,verts[1:]+verts[:1]):
        d=b-a;q=max(0,min(1,(mouth-a).dot(d)/d.length_squared))
        result.append((mouth-(a+d*q)).length)
    return min(result)

def hand_tree(limb):
    # Measure the real outer surfaces of the distal quarter of the lower arm.
    verts=[];faces=[]
    ob=limb.lower
    for p in ob.data.polygons:
        poly=[(ob.data.vertices[i].co.copy(),Vector((0,0))) for i in p.vertices]
        part=clip(poly,-.75*limb.b,False)
        if len(part)<3:continue
        faces.append(list(range(len(verts),len(verts)+len(part))))
        verts.extend(ob.matrix_world@v for v,uv in part)
    return BVHTree.FromPolygons(verts,faces)

def mouth_pose(actor,art,name,p,cam,cup,yaw,prior=None):
    raw=p["mouth_action"];a=min(1,raw/.90);c,dx,dz=face_grid(actor)
    mouth=c-.32*dz
    side=-dx.normalized();up=dz.normalized();normal=dx.cross(dz).normalized()
    # Actual front normal: decal orientation must point away from head.
    head_center=sum(mesh_points(actor.head),Vector())/len(mesh_points(actor.head))
    if normal.dot(mouth-head_center)<0:normal=-normal
    l=art.arms[0];rest=l.transform()@l.end
    blockers=[actor.body]+[o for limb in art.arms for o in limb.objects]+([cup] if cup else [])
    headtree=tree_for_object(actor.head)
    def evaluate(lat,depth,down,polemix,tilt):
        axis=(up+normal*tilt).normalized()
        if cup:
            # Rim lies on a plane tilted outward from the head. Choose
            # the near edge of that plane to meet the actual mouth point.
            away=(normal-axis*normal.dot(axis)).normalized()
            center=mouth+away*.085+normal*depth+side*lat-up*down
            grip_offset=axis*.12+side*.035
            target=center-grip_offset
            axis=up.lerp(axis,a).normalized()
            # Offset is tied to the cup, not independently moved to the lip.
            offset=axis*.12+side*.035
        else:
            target=mouth+side*lat+normal*depth-up*down
        end=art.arm_target(0,rest.lerp(target,a),side*polemix+normal*.60-up*.85,yaw)
        if cup:
            rim=end+offset
            cup.location=rim-axis*.10;cup.rotation_mode="QUATERNION";cup.rotation_quaternion=Vector((0,0,1)).rotation_difference(axis)
            bpy.context.view_layer.update()
            gap=rim_gap(mouth,cup)
        tree=tree_for_object(l.lower)
        hit=hand_tree(l).find_nearest(mouth)
        handgap=float(hit[3]) if hit[0] is not None else 999.
        if not cup:gap=handgap
        blocked=face_hits(cam,actor,blockers)
        # Surface intersections with head: prioritize an unobstructed face
        # and genuine lip contact, avoid hand/cup penetrating the head.
        cross=len(tree.overlap(headtree))+len(tree_for_object(l.upper).overlap(headtree))
        if cup:cross+=len(tree_for_object(cup).overlap(headtree))
        return blocked,gap,handgap,cross,end
    # A fixed default trajectory; near contact, search nearby offsets and
    # elbow pole directions. Choose deterministically, penalize occlusion
    # and head penetration first. Report failures rather than hiding them.
    if a<.35:
        candidates=[(.035,.005,.025,1.0,.45)] if cup else [(.04,.02,.10,1.0,0)]
    elif cup:
        candidates=[(lat,depth,down,pm,tilt) for lat in (0,.025,-.025) for depth in (0,.012) for down in (0,.012) for pm in (.7,1.6) for tilt in (.45,.85)]
    else:
        candidates=[(lat,depth,down,pm,0) for lat in (0,.045,.09,-.035) for depth in (.015,.065,.11) for down in (.045,.09,.13) for pm in (.7,1.6)]
    if prior is not None and a>=.35:
        candidates=[tuple(prior)]+[x for x in candidates if x!=tuple(prior)]
    best=None
    for params in candidates:
        blocked,gap,handgap,cross,end=evaluate(*params)
        score=(int(blocked>0),blocked,int(cross>0),cross,max(0,gap-.012) if a>=.90 else 0,gap if a>=.90 else sum(abs(x) for x in params[:3]))
        if best is None or score<best[0]:best=(score,params)
        if blocked==0 and cross==0 and (gap<=.012 or a<.90):break
    blocked,gap,handgap,cross,end=evaluate(*best[1])
    return {"face_body_blocked_samples":blocked,"hand_to_mouth":handgap,"cup_rim_to_mouth":gap if cup else None,
            "mouth_action":raw,"head_surface_intersections":cross,"target_parameters":list(best[1])}

def body_meshes(a):
    return [o for o in a.meshes if o.type=="MESH" and o!=a.face]

def cross_intersections(a,b):
    # Include actual evaluated body, limbs, hair and accessories, not just
    # arm/torso groups. Bounding boxes are only a broad-phase acceleration.
    def cache(actor):
        return [(o,bounds(mesh_points(o)),tree_for_object(o)) for o in body_meshes(actor)]
    aa=cache(a);bb=cache(b);total=0
    for _,(al,ah),at in aa:
        for _,(bl,bh),bt in bb:
            if any(ah[i]<bl[i] or bh[i]<al[i] for i in range(3)):continue
            total+=len(at.overlap(bt))
    return total

def back_target(actor,xfrac,zfrac,clearance):
    inv=actor.root.matrix_world.inverted()
    lo,hi=bounds(inv@v for v in group_points(actor.body,actor.bones["torso"].name))
    return actor.root.matrix_world@Vector((lo.x+(hi.x-lo.x)*xfrac,hi.y+clearance,lo.z+(hi.z-lo.z)*zfrac))

def hug_pose(a,b,aa,bb,u,t,layout):
    mode,close,depth,angle,clearance=layout
    eng=pulse(u,.07,.40,.72,.99);arms=pulse(u,.01,.31,.76,.99)
    spacing=1.08+(close-1.08)*eng
    if mode=="asymmetric":
        yaws=(math.pi/2-angle,-math.pi/2-angle)
        locations=((-spacing,-depth*eng,0),(spacing,depth*eng,0))
    else:
        yaws=(angle,-angle)
        locations=((-spacing,-depth*eng,0),(spacing,depth*eng,0))
    for actor,art,loc,yaw in zip((a,b),(aa,bb),locations,yaws):
        p=old_params("hug",u,t);p["arms"]=[D,D];p["torso"]=(.035*eng,0,0);p["head"]=(-.05*eng,0,0)
        basic(actor,p,loc,yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
    # Asymmetric wrap, or a single side-hug arm behind partner's upper back.
    idx=0 if mode=="asymmetric" else max(range(2),key=lambda i:aa.arms[i].joint().x)
    other=1 if mode=="asymmetric" else min(range(2),key=lambda i:bb.arms[i].joint().x)
    active=[(a,aa,idx,b,.23,.82,yaws[0])]
    if mode=="asymmetric":active.append((b,bb,other,a,.75,.35,yaws[1]))
    # In side hug, partner's inside arm moves forward out of the wrap path.
    if mode=="side":
        l=bb.arms[other];rot=bb.rot(yaws[1]);rest=l.transform()@l.end
        target=l.joint()+rot@Vector((0,-.34,-.53))
        bb.arm_target(other,rest.lerp(target,arms),rot@Vector((0,-1,-.25)),yaws[1])
    gaps=[]
    for actor,art,i,partner,xf,zf,yaw in active:
        l=art.arms[i];rest=l.transform()@l.end
        target=back_target(partner,xf,zf,clearance)
        back=partner.root.matrix_world.to_3x3()@Vector((0,1,0))
        art.arm_target(i,rest.lerp(target,arms),back+Vector((0,0,.35 if zf>.5 else -.35)),yaw)
        # Distance from actual hand end to target torso surface (and
        # nearest evaluated surface point). This is evidence, not approval.
        end=l.lower.matrix_world@Vector((0,0,-l.b))
        near=hand_tree(l).find_nearest(target)
        gaps.append(float(near[3]) if near[0] is not None else 999.)
    overlap=cross_intersections(a,b)
    return {"phase":"side_hug" if mode=="side" else "asymmetric_hug","flight":False,"lift":0,"engagement":eng,
            "intersections":overlap,"hand_surface_gaps":gaps,"spacing":spacing,"spread":angle,"hug_variant":mode,
            "max_segment_length_change":max(aa.length_metrics()["max_segment_length_change"],bb.length_metrics()["max_segment_length_change"]),
            "max_joint_gap":max(aa.length_metrics()["max_joint_gap"],bb.length_metrics()["max_joint_gap"])}

def choose_hug(a,b,aa,bb,N):
    # Select a single layout for the whole clip; never switch layouts on
    # individual frames. Asymmetric first, side fallback if it clips.
    diagnostics=[]
    for mode in ("asymmetric","side"):
        candidates=[(mode,spacing,depth,angle,clearance) for spacing in ((.40,.48,.56) if mode=="asymmetric" else (.58,.66,.74,.82)) for depth in ((.12,.24) if mode=="asymmetric" else (.08,.22)) for angle in (.12,.26) for clearance in (.055,)]
        sampled=[]
        for layout in candidates:
            rows=[hug_pose(a,b,aa,bb,f/(N-1),f/30,layout) for f in (0,10,20,30,40,50,59)]
            score=(max(x["intersections"] for x in rows),max(max(x["hand_surface_gaps"]) for x in rows if x["engagement"]>.85))
            sampled.append((score,layout))
        for _,layout in sorted(sampled)[:4]:
            rows=[hug_pose(a,b,aa,bb,f/(N-1),f/30,layout) for f in range(N)]
            count=max(x["intersections"] for x in rows)
            gap=max(max(x["hand_surface_gaps"]) for x in rows if x["engagement"]>.85)
            joint=max(x["max_joint_gap"] for x in rows)
            diagnostics.append({"layout":list(layout),"max_intersections":count,"max_engaged_hand_gap":gap,"max_joint_gap":joint})
            if count==0 and gap<=.18 and joint<=.002:return layout,diagnostics
        # If asymmetric is not clear across the entire sequence, test side.
    side=[d for d in diagnostics if d["layout"][0]=="side"]
    best=min(side,key=lambda d:(d["max_intersections"],d["max_engaged_hand_gap"],d["max_joint_gap"]))
    return tuple(best["layout"]),diagnostics
