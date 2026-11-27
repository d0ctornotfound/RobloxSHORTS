"""Round seven targeted changes; approved motions and hug untouched."""
import math,itertools,json,bpy
from mathutils import Vector,Matrix
from character_motion import D,ramp,pulse,mix,floor
from chapter1_round2 import new_params as old_params,basic,pose as old_pose
from chapter1_round4_solver import actual,data,world,nearest,overlap,ArmSolver,arm_matrices,matlist,restore,eat_face_rays,rays,rim_distance,proximal_data
from chapter1_round5_solver import pack,flat_contact
from chapter1_round6_solver import LAT,GAP,components,prep,rim_contact,cup_nonrim,contact_ok,profile_base

def point_pose(actor,art,u,t,yaw):
    # Same neutral bookends, arm direction and pulse amplitudes. Retiming
    # only: .4s initiation, 1.2s hold (two emphases), .4s recovery.
    lead=pulse(u,0,.10,.85,1);hit=pulse(u,.015,.20,.80,1)
    hold=max(0,min(1,(u-.20)/.60))
    wave=math.sin(math.tau*2*hold)*hit if .20<=u<=.80 else 0.
    emphasis=pulse(u,.24,.29,.32,.39)+pulse(u,.54,.59,.62,.69)
    p=old_params("point",u,t)
    p.update(pitch=0,legs=[D,D],head=(.15*wave+.12*emphasis,0,.30*lead),
        torso=(.08*hit+.08*wave,0,.12*hit+.06*wave),
        arms=[mix(D,(0,-1,.055*wave),hit),mix(D,(.18,.18,-.94),hit)])
    basic(actor,p,(0,0,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))))
    return p

def eat_head(actor,p,delta):
    # Add a smooth contact-local head dip/yaw to existing bite movement.
    w=ramp(p["mouth_action"],.55,.90)
    angles=list(p["head"])
    angles[0]+=delta[0]*w;angles[2]+=delta[1]*w
    actor.set_bone("head",angles);bpy.context.view_layer.update()

def eat_metrics(actor,art,cam,p):
    decal,anchor,n,up,side,heads,other,body,extras=prep(actor,art)
    limb=art.arms[0];arm=ArmSolver(limb)
    sol=pack(arm,limb.upper.matrix_world.copy(),limb.lower.matrix_world.copy(),anchor,n)
    center=limb.lower.matrix_world@arm.local_center
    lat,_=components(center,decal,n)
    q,_,gap=nearest(sol["hand"],decal)
    inter=sum(overlap(g,heads) for g in [actual(limb.upper),actual(limb.lower)]+other)
    contact=p["mouth_action"]>=.90
    face,exempt=eat_face_rays(cam,actor,[body]+other+[actual(limb.upper),world(proximal_data(limb),limb.lower.matrix_world)],sol["hand"],contact)
    valid=inter==face==0 and (not contact or (lat<=.03 and gap<=.06))
    return {"geometry_pass":valid,"lateral_alignment":lat,"nearest_surface_gap":gap,"hand_to_mouth":gap,
        "face_body_blocked_samples":face,"mouth_only_exempt_rays":exempt,"head_surface_intersections":inter,
        "contact_center":list(center),"contact_surface":list(q),"mouth_decal_anchor":list(decal),
        "contact":contact,"mouth_action":p["mouth_action"]}

def search_eat(scene,cam,a,art,yaw,baseline,N):
    # Keep both arm matrices from the 60-frame zero-collision, zero-
    # obstruction round6 plan. One head offset over the whole cycle,
    # smoothly gated by bite weight. Recheck even approach/withdrawal.
    configs=[(math.radians(p),math.radians(y)) for p,y in itertools.product((10,7,13,5,15,0),(-15,-10,-6,0,6,10,15))]
    candidates=[];best=None
    for delta in configs:
        rows=[]
        for f in range(N):
            scene.frame_set(f+1);p,_=old_pose(a,art,"eat",f/59,f/30,yaw);a.pose("neutral")
            restore(art.arms[0],baseline[f]["arm_matrices"]);eat_head(a,p,delta)
            row=eat_metrics(a,art,cam,p);row.update(arm_matrices=baseline[f]["arm_matrices"],head_delta=list(delta))
            rows.append(row)
        contact=[x for x in rows if x["contact"]]
        # Bank zero collision/obstruction: prioritize hard safety before
        # alignment/gap, including when reporting a failed diagnostic pose.
        unsafe=sum(x["head_surface_intersections"]!=0 or x["face_body_blocked_samples"]!=0 for x in rows)
        fail=sum(not x["geometry_pass"] for x in rows)
        score=(unsafe,fail,max(x["lateral_alignment"] for x in contact),max(x["nearest_surface_gap"] for x in contact),abs(delta[0]-math.radians(10)))
        candidates.append({"head_delta_degrees":[math.degrees(x) for x in delta],"score":list(score)})
        if best is None or score<best[0]:best=(score,rows)
        if fail==0:break
    print("EAT7_HEAD_SEARCH",json.dumps({"tested":len(candidates),"best":best[0]}),flush=True)
    return best[1],candidates

def cup_support(arm,gq,gn,pole,yaw,roll,clear,branch,fu,fv):
    # Exact plane solve: distal cap local -Z normal faces the cup base,
    # selected actual cap point touches an offset plane under the cup.
    sol=flat_contact(arm,gq,gn,yaw,(2,-1,fu,fv,branch,clear,Vector((0,0,0))))
    if sol is None:
        # Diagnostic/alternate rigid IK with an outward half-thickness
        # correction. Never accept unless actual end cap supports the base.
        sol=arm.solve(gq,gn,pole,yaw,roll,1.,clear)
    lm=Matrix(sol["matrices"][1])
    cap=(lm.to_3x3()@Vector((0,0,-1))).normalized()
    sol["cap_alignment"]=cap.dot(-gn)
    # Cup is above the entire distal hand surface on its base plane.
    sol["support_clearance"]=min((v-gq).dot(gn) for v in sol["hand"][0])
    return sol

def drink_eval(actor,art,cam,cup,p,yaw,params,prepared=None):
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    decal,anchor,n,up,side,heads,other,body,extras=prepared or prep(actor,art)
    side_sign,tilt,az,offset,corner,grip,gripz,poleangle,poledepth,roll,way,drop=params
    arm=ArmSolver(art.arms[0]);l=arm.l
    # Rim centre stays centred in face plane at contact. Axis tips inward
    # so the cup base remains outside and below the face. Side approach
    # comes from beside the cheek, not across the face front.
    z=Vector((0,0,1));horizontal=n-z*n.dot(z);horizontal.normalize()
    lateral=z.cross(horizontal)
    axis=(z*math.cos(tilt)+(-horizontal*math.cos(az)+lateral*math.sin(az))*math.sin(tilt)).normalized()
    rot=z.rotation_difference(axis)
    center=decal+n*offset+side*corner
    final=center-rot@Vector((0,0,.07))
    rest=l.transform()@l.end+side*side_sign*.12+n*.16+z*.04
    waypoint=final+side*side_sign*way+n*.12-up*drop
    if w<.55:
        b=ramp(w,0,.55);pos=rest.lerp(waypoint,b);fraction=.35*b
    else:
        b=ramp(w,.55,1);pos=waypoint.lerp(final,b);fraction=.35+.65*b
    cm=Matrix.Translation(pos)@z.rotation_difference(z).slerp(rot,fraction).to_matrix().to_4x4()
    cg=world(data(cup),cm);nonrim=cup_nonrim(cup,cm)
    lat,normal,rc=rim_contact(cup,cm,decal,n)
    # Grip variables now select a point on the measured bottom disc,
    # not a location inside its wall. Cup sits on the distal end cap.
    gn=-(cm.to_3x3()@Vector((0,0,1))).normalized()
    radius=.045*max(0,min(1,abs(gripz)/.07))
    gq=cm@Vector((radius*math.cos(grip),radius*math.sin(grip),-.07))
    pole=side*math.cos(poleangle)+up*math.sin(poleangle)+n*poledepth
    branch=1 if math.sin(poleangle)>=0 else -1
    fu=.15+.70*(.5+.5*math.cos(grip));fv=.15+.70*(.5+.5*math.sin(grip))
    sol=cup_support(arm,gq,gn,pole,yaw,roll,.004,branch,fu,fv)
    geoms=[sol["upper"],sol["lower"]]
    heads_n=sum(overlap(g,heads) for g in geoms+other)+overlap(cg,heads)
    cup_arm=overlap(cg,geoms+other);cup_body=overlap(cg,[body]+extras)
    # Native shoulder attachment overlap is intentional; exclude only
    # its proximal quarter against own torso. All other collisions tested.
    from chapter1_drink_path import sliced
    upper_distal=world(sliced(l.upper,-.25*l.a),Matrix(sol["matrices"][0]))
    arm_body=overlap(upper_distal,[body])+overlap(sol["lower"],[body])
    arm_other=sum(overlap(g,other+extras) for g in geoms)
    face=rays(cam,actor,[body]+other+geoms+[nonrim])
    gripgap=sol["gap"];below=max(v.z-decal.z for j,v in enumerate(cg[0]) if not 32<=j<96)
    valid=heads_n==cup_arm==cup_body==arm_body==arm_other==face==0 and gripgap<=.02 and sol["cap_alignment"]>=.90 and sol["support_clearance"]>=-.001 and (not contact or (contact_ok(lat,normal) and below<=.002))
    score=(int(not valid),heads_n+cup_arm+cup_body+arm_body+arm_other,face,max(0,lat-LAT)+max(0,abs(normal)-GAP) if contact else 0,max(0,gripgap-.02)+max(0,.90-sol["cap_alignment"])+max(0,-sol["support_clearance"]-.001))
    return score,{"geometry_pass":valid,"arm_matrices":sol["matrices"],"cup_matrix":matlist(cm),"parameters":list(params),
        "face_body_blocked_samples":face,"head_surface_intersections":heads_n,"cup_arm_intersections":cup_arm,
        "cup_body_intersections":cup_body,"arm_body_intersections":arm_body,"arm_other_intersections":arm_other,
        "cup_body_above_mouth":below,"grip_gap":gripgap,"grip_anchor":list(gq),
        "cap_alignment":sol["cap_alignment"],"support_clearance":sol["support_clearance"],"grip_normal":list(gn),
        "measured_half_thickness":sol["half_thickness"],
        "cup_rim_to_mouth":rim_distance(cup,cm,decal),"mouth_action":raw,"contact":contact,
        "lateral_alignment":lat,"normal_gap":normal,"contact_center":rc,"mouth_decal_anchor":list(decal)}
def search_drink(scene,cam,a,art,cup,yaw,N):
    # Test contact cup geometry alone before full arm search.
    scene.frame_set(30);p,angle=profile_base(a,art,29/59,29/30,yaw);prepared=prep(a,art)
    decal,anchor,n,up,side,heads,other,body,extras=prepared
    z=Vector((0,0,1));hn=n-z*n.dot(z);hn.normalize();hs=z.cross(hn)
    opts=[]
    for tilt,az,offset,corner in itertools.product(map(math.radians,(35,40,45)),(-.45,0,.45),(.035,.045,.055,.059),(-.025,0,.025)):
        axis=(z*math.cos(tilt)+(-hn*math.cos(az)+hs*math.sin(az))*math.sin(tilt)).normalized()
        rot=z.rotation_difference(axis)
        center=decal+n*offset+side*corner
        cm=Matrix.Translation(center-rot@Vector((0,0,.07)))@rot.to_matrix().to_4x4()
        cg=world(data(cup),cm);nonrim=cup_nonrim(cup,cm)
        lat,norm,rc=rim_contact(cup,cm,decal,n)
        below=max(v.z-decal.z for j,v in enumerate(cg[0]) if not 32<=j<96)
        score=(overlap(cg,heads)+overlap(cg,[body]+extras),rays(cam,a,[nonrim]),int(not contact_ok(lat,norm)),max(0,below-.002))
        opts.append((score,(tilt,az,offset,corner)))
    opts.sort();clean=[x for x in opts if x[0]==(0,0,0,0)]
    ranked=[];tested=0;peak_clean=0
    for _,cp in (clean[:18] if clean else opts[:8]):
        for ss,grip,gz,pa,pd,roll in itertools.product((-1,1),[i*math.tau/8 for i in range(8)],(-.07,-.025,.02),[i*math.tau/8 for i in range(8)],(.2,.8),(0,math.pi/2,-math.pi/2)):
            config=(ss,)+cp+(grip,gz,pa,pd,roll,.22,.22)
            score,row=drink_eval(a,art,cam,cup,p,angle,config,prepared);tested+=1
            ranked.append((score,config));peak_clean+=int(row["geometry_pass"])
            if peak_clean>=24:break
        if peak_clean>=24:break
    ranked.sort();attempts=[{"cup_candidates":len(opts),"clean_cup_candidates":len(clean),"arm_candidates":tested,"peak_clean":peak_clean,"best_peak":ranked[:3]}]
    print("DRINK7_PEAK",json.dumps(attempts[0]),flush=True)
    best=None
    for _,c in ranked[:24]:
        for way,drop in ((.22,.22),(.32,.28),(.16,.30)):
            config=c[:10]+(way,drop)
            rows=[]
            for f in range(N):
                scene.frame_set(f+1);p,angle=profile_base(a,art,f/59,f/30,yaw)
                _,row=drink_eval(a,art,cam,cup,p,angle,config);rows.append(row)
            contacts=[r for r in rows if r["contact"]]
            score=(sum(not r["geometry_pass"] for r in rows),max(r["head_surface_intersections"] for r in rows),max(r["cup_arm_intersections"] for r in rows),max(r["lateral_alignment"] for r in contacts))
            attempts.append({"parameters":list(config),"score":list(score)})
            if best is None or score<best[0]:best=(score,rows)
            if score[0]==0:break
        if best[0][0]==0:break
    return best[1],attempts

