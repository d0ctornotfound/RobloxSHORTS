"""Round six: supervisor-authorized contact gates and phase-based hug.
No rendering in this module. Every selected pose is independently replayed."""
import math,itertools,json,bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from character_motion import D,ramp,pulse,mix,floor
from chapter1_round2 import new_params as old_params,basic
from chapter1_round4_solver import (actual,data,world,nearest,overlap,cross,ArmSolver,arm_matrices,
    mouth_anchor,matlist,restore,proximal_data,eat_face_rays,rays,eat_path,rim_distance)
from chapter1_round5_solver import pack,blend_pose,rib_surface
from chapter1_round3 import body_meshes,cross_intersections
from chapter1_articulation import DOWN

LAT=.03;GAP=.06
def components(point,anchor,n):
    d=point-anchor;normal=d.dot(n);return (d-n*normal).length,normal
def hand_contact(arm,sol,decal,n):
    # Lateral alignment is the actual distal hand bounding-centre projected
    # onto the face plane. Normal gap is measured on the inward hand surface
    # at that centre projection, not from the arm endpoint or nearest cheek.
    lm=Matrix(sol["matrices"][1]);center=lm@arm.local_center
    lateral,_=components(center,decal,n)
    q,_,_,_=sol["hand"][1].ray_cast(center-n*.5,n,1.)
    if q is None:q,_,_=nearest(sol["hand"],center-n*.5)
    _,normal=components(q,decal,n)
    return lateral,normal,list(center),list(q)
def rim_contact(cup,cm,decal,n):
    ring=[cm@cup.data.vertices[32+i].co for i in range(32)]
    center=sum(ring,Vector())/len(ring)
    lateral,normal=components(center,decal,n)
    return lateral,normal,list(center)
def cup_nonrim(cup,cm):
    # Only the real annular top face (outer ring 32..63, inner 64..95)
    # is exempt from the drink obstruction count; walls and base are not.
    verts=[v.co.copy() for v in cup.data.vertices]
    faces=[tuple(p.vertices) for p in cup.data.polygons if not all(32<=i<96 for i in p.vertices)]
    return world((verts,faces),cm)
def prep(actor,art):
    decal,anchor,n,up,side,head=mouth_anchor(actor)
    heads=[head]+[actual(o) for o in actor.accessories if o!=actor.face and o.type=="MESH" and "head" in o.name.lower()]
    other=[actual(o) for o in art.arms[1].objects];body=actual(actor.body)
    extras=[actual(o) for o in actor.accessories if o!=actor.face and o.type=="MESH" and "head" not in o.name.lower()]
    return decal,anchor,n,up,side,heads,other,body,extras
def contact_ok(lateral,normal):
    return lateral<=LAT and abs(normal)<=GAP
def eat_solve(actor,art,cam,p,old,yaw,prior):
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    decal,anchor,n,up,side,heads,other,body,extras=prep(actor,art)
    arm=ArmSolver(art.arms[0])
    base=pack(arm,*[Matrix(m) for m in old["arm_matrices"]],anchor,n)
    def evaluate(params):
        poleangle,depth,roll,clear,lower,lateral,front,drop=params
        if params==(-999,)*8:sol=base
        else:
            pole=side*math.cos(poleangle)+up*math.sin(poleangle)+n*depth
            target=anchor-up*lower+side*lateral
            sol=eat_path(arm,target,n,up,side,pole,yaw,roll,w,clear,front,drop,0)
        lat,normal,center,surface=hand_contact(arm,sol,decal,n)
        headhits=overlap(sol["upper"],heads)+overlap(sol["lower"],heads)+sum(overlap(x,heads) for x in other)
        face,exempt=eat_face_rays(cam,actor,[body]+other+[sol["upper"],sol["proximal"]],sol["hand"],contact)
        clearance=min((v-anchor).dot(n) for v in sol["hand"][0])
        valid=headhits==0 and face==0 and (not contact or (contact_ok(lat,normal) and clearance>=-.001))
        score=(int(not valid),headhits,face,max(0,lat-LAT)+max(0,abs(normal)-GAP) if contact else 0,max(0,-clearance-.001) if contact else 0)
        return score,{"geometry_pass":valid,"arm_matrices":sol["matrices"],"parameters":list(params),
          "face_body_blocked_samples":face,"mouth_only_exempt_rays":exempt,"head_surface_intersections":headhits,
          "hand_to_mouth":nearest(sol["hand"],decal)[2],"mouth_action":raw,"contact":contact,
          "lateral_alignment":lat,"normal_gap":normal,"contact_center":center,"contact_surface":surface,
          "hand_outward_clearance":clearance,"mouth_decal_anchor":list(decal)}
    # Retain exactly the old collision-free approach whenever it passes.
    base_params=(-999,)*8;best=evaluate(base_params);tested=1
    if best[1]["geometry_pass"]:return best[1]|{"search_evaluations":tested}
    # Search narrower hand profiles, lower-centre contact, and the same
    # below-front path with modest clearance offsets. Never relax collisions.
    if prior is not None and tuple(prior)!=base_params:
        v=evaluate(tuple(prior));tested+=1
        if v[0]<best[0]:best=v
    if not best[1]["geometry_pass"]:
        for params in itertools.product([i*math.tau/12 for i in range(12)],(.15,.8),
             (0,math.pi/4,-math.pi/4,math.pi/2,-math.pi/2,math.pi),(.008,.020,.035,.050),
             (0,.008,.016),(-.018,0,.018),(.20,),(.30,)):
            v=evaluate(params);tested+=1
            if v[0]<best[0]:best=v
            if v[1]["geometry_pass"]:break
    row=best[1];row["search_evaluations"]=tested;return row

def profile_base(actor,art,u,t,yaw):
    p=old_params("drink",u,t);a=p["mouth_action"]
    # Body turns three-quarter while the cup rises on the near side;
    # head rotates slightly toward the sip corner, then swallows.
    angle=yaw+.25*ramp(u,0,.18)*(1-ramp(u,.83,1))
    p["head"]=(-.20*a-.07*pulse(u,.42,.55,.60,.74),0,.14*a)
    p["torso"]=(.02*a,0,.06*a)
    basic(actor,p,(0,0,0),angle);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("neutral")
    return p,angle

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
    final=center-rot@Vector((0,0,.10))
    rest=l.transform()@l.end+side*side_sign*.12+n*.16+z*.04
    waypoint=final+side*side_sign*way+n*.12-up*drop
    if w<.55:
        b=ramp(w,0,.55);pos=rest.lerp(waypoint,b);fraction=.35*b
    else:
        b=ramp(w,.55,1);pos=waypoint.lerp(final,b);fraction=.35+.65*b
    cm=Matrix.Translation(pos)@z.rotation_difference(z).slerp(rot,fraction).to_matrix().to_4x4()
    cg=world(data(cup),cm);nonrim=cup_nonrim(cup,cm)
    lat,normal,rc=rim_contact(cup,cm,decal,n)
    radial=Vector((math.cos(grip),math.sin(grip),0));gn=(cm.to_3x3()@radial).normalized()
    origin=cm@Vector((0,0,gripz));gq,_,_,_=cg[1].ray_cast(origin+gn*.3,-gn,.5)
    if gq is None:gq,_,_=nearest(cg,origin+gn*.08)
    pole=side*math.cos(poleangle)+up*math.sin(poleangle)+n*poledepth
    sol=arm.solve(gq,gn,pole,yaw,roll,1.,.006)
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
    valid=heads_n==cup_arm==cup_body==arm_body==arm_other==face==0 and gripgap<=.02 and (not contact or (contact_ok(lat,normal) and below<=.002))
    score=(int(not valid),heads_n+cup_arm+cup_body+arm_body+arm_other,face,max(0,lat-LAT)+max(0,abs(normal)-GAP) if contact else 0,max(0,gripgap-.02))
    return score,{"geometry_pass":valid,"arm_matrices":sol["matrices"],"cup_matrix":matlist(cm),"parameters":list(params),
        "face_body_blocked_samples":face,"head_surface_intersections":heads_n,"cup_arm_intersections":cup_arm,
        "cup_body_intersections":cup_body,"arm_body_intersections":arm_body,"arm_other_intersections":arm_other,
        "cup_body_above_mouth":below,"grip_gap":gripgap,"grip_anchor":list(gq),
        "cup_rim_to_mouth":rim_distance(cup,cm,decal),"mouth_action":raw,"contact":contact,
        "lateral_alignment":lat,"normal_gap":normal,"contact_center":rc,"mouth_decal_anchor":list(decal)}
def search_drink(scene,cam,a,art,cup,yaw,N):
    # Test contact cup geometry alone before full arm search.
    scene.frame_set(30);p,angle=profile_base(a,art,29/59,29/30,yaw);prepared=prep(a,art)
    decal,anchor,n,up,side,heads,other,body,extras=prepared
    z=Vector((0,0,1));hn=n-z*n.dot(z);hn.normalize();hs=z.cross(hn)
    opts=[]
    for tilt,az,offset,corner in itertools.product(map(math.radians,(30,45,55,65,75)),(-.45,0,.45),(.035,.045,.055,.059),(-.025,0,.025)):
        axis=(z*math.cos(tilt)+(-hn*math.cos(az)+hs*math.sin(az))*math.sin(tilt)).normalized()
        rot=z.rotation_difference(axis)
        center=decal+n*offset+side*corner
        cm=Matrix.Translation(center-rot@Vector((0,0,.10)))@rot.to_matrix().to_4x4()
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
    print("DRINK6_PEAK",json.dumps(attempts[0]),flush=True)
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

def hug_phase(u):
    # Open before approach; close only after bodies are in position.
    # Release before retreat, then lower arms once apart.
    opening=ramp(u,0,.16)*(1-ramp(u,.88,1))
    approach=ramp(u,.16,.38)*(1-ramp(u,.72,.88))
    close=ramp(u,.38,.49)*(1-ramp(u,.63,.72))
    lean=ramp(u,.43,.54)*(1-ramp(u,.62,.72))
    return opening,approach,close,lean

def hug_base(a,b,aa,bb,u,t,layout):
    spacing,depth,angle,lean,headlean,k0,k1,h0,h1,surface_depth,mode,spread=layout
    op,ap,cl,ln=hug_phase(u);distance=1.35+(spacing-1.35)*ap
    yaws=(angle,-angle)
    for actor,art,sign,yaw in ((a,aa,-1,yaws[0]),(b,bb,1,yaws[1])):
        p=old_params("hug",u,t)
        # Face each other obliquely, open arms laterally into clear space,
        # then take two steps in/out. Native legs keep original proportions.
        step=math.sin(math.tau*2*ap)*.32 if 0<ap<1 else 0
        p.update(pitch=0,legs=[(0,-step,-1),(0,step,-1)],
            torso=(.055*ln,-sign*lean*ln,0),head=(0,-sign*headlean*ln,0))
        # Determine arm side from actual native shoulder positions after reset.
        p["arms"]=[mix(D,(-spread,.10,-.22),op),mix(D,(spread,.10,-.22),op)]
        basic(actor,p,(sign*distance,sign*depth*ap,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
    return cl,op,ap,ln,yaws
def hug_anchors(a,b,layout):
    return [rib_surface(b,a.root.matrix_world.translation,layout[5],layout[7],layout[9]),
            rib_surface(a,b.root.matrix_world.translation,layout[6],layout[8],1-layout[9])]
def hug_solve(a,b,aa,bb,u,t,layout,prior=None):
    cl,op,ap,ln,yaws=hug_base(a,b,aa,bb,u,t,layout)
    ix=max(range(2),key=lambda i:aa.arms[i].joint().x);iy=min(range(2),key=lambda i:bb.arms[i].joint().x)
    if layout[10]==1:ix=1-ix
    if layout[10]==2:iy=1-iy
    arms=(aa.arms[ix],bb.arms[iy]);actors=(a,b);arts=(aa,bb)
    # Inactive arms stay open through approach and release, then relax
    # outward to their own sides during close; keep all geometry in checks.
    for art,i,yaw in zip(arts,(ix,iy),yaws):
        l=art.arms[1-i]
        if cl>0:
            rest=l.transform()@l.end;shoulder=l.joint()
            outward=(shoulder-art.actor.root.matrix_world.translation);outward.z=0
            if outward.length<1e-6:outward=Vector((1,0,0))
            target=shoulder+outward.normalized()*.14+Vector((0,0,-(l.a+l.b)*.96))
            art.arm_target(1-i,rest.lerp(target,cl),outward,yaw)
    fixed=[[actual(o) for o in body_meshes(actor) if o not in l.objects] for actor,l in zip(actors,arms)]
    base=sum(cross(x,y) for x in fixed[0] for y in fixed[1]);anchors=hug_anchors(a,b,layout)
    choices=[]
    for i,l in enumerate(arms):
        anchor,n=anchors[i];arm=ArmSolver(l);rest=[matlist(l.upper.matrix_world),matlist(l.lower.matrix_world)]
        if cl<=1e-7:
            sol=pack(arm,*[Matrix(m) for m in rest],anchor,n)
            inter=overlap(sol["upper"],fixed[1-i])+overlap(sol["lower"],fixed[1-i])
            choices.append([((inter,0,0),None,sol)]);continue
        side=Vector((1 if i==0 else -1,0,0));up=Vector((0,0,1))
        opts=[];params=list(itertools.product([j*math.tau/12 for j in range(12)],(.2,.7),(0,math.pi/2,-math.pi/2,math.pi),(.004,.009,.014)))
        if prior and prior[i] is not None:params=[tuple(prior[i])]+params
        for angle,depth,roll,clear in params:
            pole=n*math.cos(angle)+up*math.sin(angle)+side*depth
            sol=arm.solve(anchor,n,pole,yaws[i],roll,1.,clear)
            if cl<1.:sol=blend_pose(arm,rest,sol,cl,anchor,n)
            inter=overlap(sol["upper"],fixed[1-i])+overlap(sol["lower"],fixed[1-i])
            score=(inter,max(0,-sol["surface_clearance"]-.001) if cl>=.90 else 0,max(0,sol["gap"]-.02) if cl>=.90 else 0)
            opts.append((score,(angle,depth,roll,clear),sol))
            if sum(o[0]==(0,0,0) for o in opts)>=8:break
        opts.sort(key=lambda o:o[0]);choices.append(opts[:10])
    best=None
    for x,y in itertools.product(*choices):
        p,q=x[2],y[2]
        inter=base+x[0][0]+y[0][0]+sum(cross(g,h) for g in (p["upper"],p["lower"]) for h in (q["upper"],q["lower"]))
        gaps=[p["gap"],q["gap"]];clear=[p["surface_clearance"],q["surface_clearance"]]
        valid=inter==0 and (cl<.90 or (max(gaps)<=.02 and min(clear)>=-.001))
        score=(int(not valid),inter,max(0,max(gaps)-.02) if cl>=.90 else 0,max(0,-min(clear)) if cl>=.90 else 0)
        if best is None or score<best[0]:best=(score,x,y,inter,valid)
        if valid:break
    _,x,y,inter,valid=best
    for l,sol in zip(arms,(x[2],y[2])):restore(l,sol["matrices"])
    bpy.context.view_layer.update()
    phase="open" if u<.16 else "step_in" if u<.38 else "close" if u<.49 else "hold" if u<.63 else "release" if u<.72 else "step_out" if u<.88 else "lower"
    return {"phase":phase,"engagement":cl,"geometry_pass":valid,"intersections":inter,
        "fixed_body_intersections":base,"hand_surface_gaps":[x[2]["gap"],y[2]["gap"]],
        "surface_clearances":[x[2]["surface_clearance"],y[2]["surface_clearance"]],
        "surface_anchors":[list(q) for q,n in anchors],"parameters":[x[1],y[1]],
        "arm_indices":[ix,iy],"arm_matrices":[x[2]["matrices"],y[2]["matrices"]],
        "all_arm_matrices":[[[matlist(l.upper.matrix_world),matlist(l.lower.matrix_world)] for l in art.arms] for art in arts],
        "opening":op,"approach":ap,"close":cl,"lean":ln}
def search_hug(a,b,aa,bb,N):
    layouts=[(s,d,ang,lean,.035,k0,k1,h0,h1,dep,mode,spread)
      for s,d,ang,lean,spread in itertools.product((.40,.50,.60,.72),(-.10,.10),(.9,1.25),(.035,.075),(.88,1.))
      for k0,k1,h0,h1,dep,mode in (("rib","rib",.50,.72,.35,0),("rib","rib",.70,.45,.65,0),("rib","shoulder",.60,.9,.40,0),("shoulder","rib",.9,.60,.60,0))]
    ranked=[];attempts=[];peak_clean=0
    for layout in layouts:
        row=hug_solve(a,b,aa,bb,.56,1.1,layout)
        score=(int(not row["geometry_pass"]),row["intersections"],max(row["hand_surface_gaps"]))
        ranked.append((score,layout,row["parameters"]));peak_clean+=int(row["geometry_pass"])
        attempts.append({"layout":list(layout),"peak_intersections":row["intersections"],"peak_hand_gaps":row["hand_surface_gaps"],"peak_pass":row["geometry_pass"]})
    ranked.sort(key=lambda x:x[0]);print("HUG6_PEAK",json.dumps({"layouts":len(layouts),"peak_clean":peak_clean,"best":ranked[:3]}),flush=True)
    best=None
    for _,layout,prior in ranked[:16]:
        rows=[]
        for f in range(N):
            q=hug_solve(a,b,aa,bb,f/(N-1),f/30,layout,prior)
            if q["parameters"][0] is not None:prior=q["parameters"]
            rows.append(q)
        score=(sum(not q["geometry_pass"] for q in rows),max(q["intersections"] for q in rows),max(max(q["hand_surface_gaps"]) for q in rows if q["engagement"]>=.90))
        attempts.append({"layout":list(layout),"full_score":list(score)})
        if best is None or score<best[0]:best=(score,layout,rows)
        if score[0]==0:break
    return best[1],best[2],attempts
