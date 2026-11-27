"""Round 5 contact geometry. Exact rigid two-link plane IK; no image calls."""
import math,itertools,json,bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from character_motion import D,ramp,pulse,floor
from chapter1_round2 import new_params as old_params,basic,pose as old_pose
from chapter1_round4_solver import (actual,data,world,nearest,overlap,cross,ArmSolver,
    mouth_anchor,matlist,restore,proximal_data,eat_face_rays)
from chapter1_round3 import body_meshes
from chapter1_articulation import DOWN
from r6_character import bounds,mesh_points,dominant_group

def basis(a,b):
    return Matrix((a,b,a.cross(b))).transposed()
def pack(arm,um,lm,anchor,n):
    hand=world(arm.hd,lm);q,_,gap=nearest(hand,anchor)
    return {"matrices":[matlist(um),matlist(lm)],"upper":world(arm.ud,um),"lower":world(arm.ld,lm),
            "hand":hand,"proximal":world(proximal_data(arm.l),lm),"gap":gap,
            "surface_clearance":min((v-anchor).dot(n) for v in hand[0]),
            "half_thickness":max((lm@arm.local_center-v).dot(n) for v in hand[0]),
            "endpoint":list(lm@Vector((0,0,-arm.l.b))),"hand_surface_point":list(q)}

def flat_contact(arm,anchor,n,yaw,config):
    # A selected actual distal surface point v is constrained to T; the
    # corresponding local face normal maps to -n. Thus the hand plane is
    # parallel to the target surface, its thickness accounted for exactly.
    # Elbow is the intersection of two circles on its required plane.
    ax,sg,fu,fv,branch,cl,offset=config
    lo,hi=bounds(arm.hd[0]);out=Vector((0,0,0));out[ax]=sg
    dims=[i for i in range(3) if i!=ax];v=Vector((0,0,0))
    v[ax]=hi[ax] if sg>0 else lo[ax]
    v[dims[0]]=lo[dims[0]]+(hi[dims[0]]-lo[dims[0]])*fu
    v[dims[1]]=lo[dims[1]]+(hi[dims[1]]-lo[dims[1]])*fv
    local_tree=BVHTree.FromPolygons(arm.hd[0],arm.hd[1])
    vp,_,_,dist=local_tree.find_nearest(v)
    if vp is None or dist>.0015:return None
    v=vp
    # Local plane support uses actual mesh extent, not a guessed half-width.
    h=v.dot(out);vt=v-out*h;rad=vt.length
    if rad<1e-7:return None
    T=anchor+n*cl+offset
    C=T+n*h;S=arm.l.joint()
    plane=(C-S).dot(n);r2=arm.l.a**2-plane**2
    if r2<0:return None
    P=S+n*plane;delta=P-C;d=delta.length
    if d<1e-7:return None
    x=(rad*rad-r2+d*d)/(2*d);y2=rad*rad-x*x
    if y2<-1e-7:return None
    u=delta/d;E=C+u*x+n.cross(u)*math.sqrt(max(0,y2))*branch
    W=T-E+n*h
    if W.length<1e-7:return None
    R=basis(-n,W.normalized())@basis(out,vt.normalized()).transposed()
    lm=Matrix.Translation(E)@R.to_4x4()
    rot=Matrix.Rotation(yaw,3,"Z")
    ur=(rot@DOWN).rotation_difference((E-S).normalized()).to_matrix()@rot
    um=Matrix.Translation(S)@ur.to_4x4()
    return pack(arm,um,lm,anchor,n)
def blend_pose(arm,baseline,sol,w,anchor,n):
    # Blend segment ROTATIONS, not disconnected world-space endpoints.
    a,b=[Matrix(m) for m in baseline];c,d=[Matrix(m) for m in sol["matrices"]]
    S=arm.l.joint();q=a.to_quaternion().slerp(c.to_quaternion(),w)
    um=Matrix.Translation(S)@q.to_matrix().to_4x4()
    E=um@Vector((0,0,-arm.l.a));lm=Matrix.Translation(E)@b.to_quaternion().slerp(d.to_quaternion(),w).to_matrix().to_4x4()
    return pack(arm,um,lm,anchor,n)
def hand_configs():
    # Both side-face normals, along either lateral axis, and distal cap.
    # Move mouth contact toward upper/lower edge of actual hand surface,
    # retaining an exact face-plane normal rather than arbitrary angle keys.
    for ax,sg in ((0,1),(0,-1),(1,1),(1,-1),(2,-1)):
        for fu,fv,branch,cl in itertools.product((.12,.50,.88),(.08,.45,.85),(-1,1),(.0025,.006,.012)):
            yield (ax,sg,fu,fv,branch,cl)
def eat_eval(scene,cam,a,art,yaw,f,baseline,config,prepared=None):
    if prepared is None:
        scene.frame_set(f+1);p,_=old_pose(a,art,"eat",f/59,f/30,yaw);a.pose("neutral");bpy.context.view_layer.update()
        decal,anchor,n,up,side,head=mouth_anchor(a)
        limb=art.arms[0];arm=ArmSolver(limb)
        heads=[head]+[actual(o) for o in a.accessories if o!=a.face and o.type=="MESH" and "head" in o.name.lower()]
        other=[actual(o) for o in art.arms[1].objects];body=actual(a.body)
    else:p,decal,anchor,n,up,side,arm,heads,other,body=prepared
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    plane,loweredge,depth=config[:6],config[6],config[7]
    old=baseline[f]["arm_matrices"]
    if w<=.55:
        um,lm=[Matrix(m) for m in old];sol=pack(arm,um,lm,anchor,n)
    else:
        # Last segment (w>=.75) moves along the moving face normal.
        # Preserve previously collision-free below-front approach up to .55,
        # then rotate continuously into the face-parallel contact branch.
        extra=depth*(1-ramp(w,.75,1.))
        sol=flat_contact(arm,anchor,n,yaw,plane+( -up*loweredge+n*extra,))
        if sol is None:return (2,999,999),None
        if w<.75:sol=blend_pose(arm,old,sol,ramp(w,.55,.75),anchor,n)
    headhits=overlap(sol["upper"],heads)+overlap(sol["lower"],heads)+sum(overlap(o,heads) for o in other)
    face,exempt=eat_face_rays(cam,a,[body]+other+[sol["upper"],sol["proximal"]],sol["hand"],contact)
    gap=nearest(sol["hand"],decal)[2]
    clear=sol["surface_clearance"]
    valid=headhits==0 and face==0 and (not contact or (gap<=.02 and clear>=-.001))
    score=(int(not valid),headhits+face,max(0,gap-.02) if contact else 0,max(0,-clear-.001) if contact else 0)
    row={"geometry_pass":valid,"arm_matrices":sol["matrices"],"parameters":list(config),
         "face_body_blocked_samples":face,"mouth_only_exempt_rays":exempt,"head_surface_intersections":headhits,
         "hand_to_mouth":gap,"cup_rim_to_mouth":None,"mouth_action":raw,"contact":contact,
         "hand_outward_clearance":clear,"measured_half_thickness":sol["half_thickness"],
         "mouth_decal_anchor":list(decal),"head_surface_anchor":list(anchor),"hand_surface_point":sol["hand_surface_point"]}
    return score,row
def search_eat(scene,cam,a,art,yaw,baseline,N):
    # First evaluate exact bite contact for each plane branch. Then test
    # full motion with one fixed branch, not independently jumping elbows.
    f=15;scene.frame_set(f+1);p,_=old_pose(a,art,"eat",f/59,f/30,yaw);a.pose("neutral");bpy.context.view_layer.update()
    decal,anchor,n,up,side,head=mouth_anchor(a)
    prep=(p,decal,anchor,n,up,side,ArmSolver(art.arms[0]),
          [head]+[actual(o) for o in a.accessories if o!=a.face and o.type=="MESH" and "head" in o.name.lower()],
          [actual(o) for o in art.arms[1].objects],actual(a.body))
    ranked=[];attempts=[];tested=0;peak_clean=0
    for plane,lower in itertools.product(hand_configs(),(0,.008,.015)):
        config=plane+(lower,.06);score,row=eat_eval(scene,cam,a,art,yaw,f,baseline,config,prep)
        tested+=1
        if row is None:continue
        ranked.append((score,config))
        peak_clean+=int(row["geometry_pass"])
    ranked.sort(key=lambda x:x[0])
    print("EAT_PEAK",json.dumps({"tested":tested,"solvable":len(ranked),"clean":peak_clean,"best":ranked[:4]}),flush=True)
    if not ranked:raise RuntimeError("No exact hand-plane contact solution in sampled branches")
    best=None
    for _,c in ranked[:48]:
        for depth in (.035,.060,.090,.120):
            config=c[:7]+(depth,)
            # Check all frames for each retained candidate. No render until
            # independent mesh validation has passed all sixty.
            rows=[];missing=0
            for i in range(N):
                sc,row=eat_eval(scene,cam,a,art,yaw,i,baseline,config)
                if row is None:
                    missing+=1
                    # Keep the prior valid collision-free geometry for this
                    # diagnostic only; mark unsolved branch as failed.
                    old=dict(baseline[i]);old.update(geometry_pass=False,plane_unsolved=True,parameters=list(config));row=old
                rows.append(row)
            bad=sum(not r["geometry_pass"] for r in rows)
            score=(bad,missing,max(r["head_surface_intersections"] for r in rows),
                   max(r["face_body_blocked_samples"] for r in rows),
                   max(r["hand_to_mouth"] for r in rows if r["contact"]))
            attempts.append({"parameters":list(config),"score":list(score)})
            if best is None or score<best[0]:best=(score,config,rows)
            if bad==0:break
        if best[0][0]==0:break
    _,config,rows=best
    for row in rows:row["search_evaluations"]=0
    attempts.insert(0,{"peak_tested":tested,"peak_clean":peak_clean,"peak_solvable":len(ranked),"selected":list(config),"full_candidates":len(attempts)})
    return rows,attempts

def rib_surface(actor,toward,kind,height,depth):
    ob=actor.body;pts=mesh_points(ob);name=actor.bones["torso"].name
    faces=[tuple(p.vertices) for p in ob.data.polygons if dominant_group(ob,ob.data.vertices[p.vertices[0]])==name]
    tree=BVHTree.FromPolygons(pts,faces)
    inv=actor.root.matrix_world.inverted();local=[inv@pts[i] for f in faces for i in f];lo,hi=bounds(local)
    other=inv@toward;sign=1 if other.x>(lo.x+hi.x)/2 else -1
    if kind=="rib":
        q0=Vector(((hi.x if sign>0 else lo.x)+sign*.55,lo.y+(hi.y-lo.y)*depth,lo.z+(hi.z-lo.z)*height))
        direction=Vector((-sign,0,0));out=Vector((sign,0,0))
    else:
        # Top edge of shoulder nearest partner; away from head centre.
        x=lo.x+(hi.x-lo.x)*(.82 if sign>0 else .18)
        q0=Vector((x,lo.y+(hi.y-lo.y)*depth,hi.z+.55))
        direction=Vector((0,0,-1));out=Vector((0,0,1))
    root=actor.root.matrix_world;direction=(root.to_3x3()@direction).normalized();out=(root.to_3x3()@out).normalized()
    q,n,_,_=tree.ray_cast(root@q0,direction,1.5)
    if q is None:q,n,_,_=tree.find_nearest(root@q0)
    if n.dot(out)<0:n=-n
    return q,n
def hug_base(a,b,aa,bb,u,t,layout):
    spacing,depth,angle,lean,headlean,kind0,kind1,height0,height1,surface_depth,armmode=layout
    eng=pulse(u,.05,.38,.69,.99);w=min(1.,eng/.90)
    distance=1.12+(spacing-1.12)*eng
    # Both face front at rest. Angled torsos approach, waist and head lean
    # inward with bounded layout search; no full back wrap.
    yaws=(-angle*eng,angle*eng)
    for actor,art,sign,yaw in ((a,aa,-1,yaws[0]),(b,bb,1,yaws[1])):
        p=old_params("hug",u,t);p.update(pitch=0,legs=[D,D],arms=[D,D],torso=(.02*eng,-sign*lean*eng,0),head=(0,-sign*headlean*eng,0))
        basic(actor,p,(sign*distance,sign*depth*eng,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
    return eng,w,yaws
def hug_anchors(a,b,layout):
    return [rib_surface(b,a.root.matrix_world.translation,layout[5],layout[7],layout[9]),
            rib_surface(a,b.root.matrix_world.translation,layout[6],layout[8],1-layout[9])]
def hug_solve(a,b,aa,bb,u,t,layout,prior=None):
    eng,w,yaws=hug_base(a,b,aa,bb,u,t,layout)
    ix=max(range(2),key=lambda i:aa.arms[i].joint().x);iy=min(range(2),key=lambda i:bb.arms[i].joint().x)
    if layout[10]==1:ix=1-ix
    if layout[10]==2:iy=1-iy
    arms=(aa.arms[ix],bb.arms[iy]);actors=(a,b);arts=(aa,bb)
    fixed=[[actual(o) for o in body_meshes(actor) if o not in l.objects] for actor,l in zip(actors,arms)]
    base=sum(cross(x,y) for x in fixed[0] for y in fixed[1]);anchors=hug_anchors(a,b,layout)
    choices=[]
    for i,l in enumerate(arms):
        anchor,n=anchors[i];arm=ArmSolver(l);rest=[matlist(l.upper.matrix_world),matlist(l.lower.matrix_world)]
        opts=[];cfgs=list(hand_configs())
        if prior and prior[i] is not None:cfgs=[tuple(prior[i])]+cfgs
        for cfg in cfgs:
            sol=flat_contact(arm,anchor,n,yaws[i],cfg+(Vector((0,0,0)),))
            if sol is None:continue
            if w<1.:sol=blend_pose(arm,rest,sol,w,anchor,n)
            inter=overlap(sol["upper"],fixed[1-i])+overlap(sol["lower"],fixed[1-i])
            gap=sol["gap"];clear=sol["surface_clearance"]
            score=(inter,int(eng>=.90 and clear<-.001),max(0,gap-.02) if eng>=.90 else 0,gap if eng>=.90 else 0)
            opts.append((score,cfg,sol))
            if sum(o[0][:3]==(0,0,0) for o in opts)>=8:break
        if not opts:
            # Diagnostic only, never declare unreachable pose clean.
            um,lm=[Matrix(m) for m in rest];sol=pack(arm,um,lm,anchor,n)
            inter=overlap(sol["upper"],fixed[1-i])+overlap(sol["lower"],fixed[1-i])
            opts=[((inter,1,999,sol["gap"]),None,sol)]
        opts.sort(key=lambda x:x[0]);choices.append(opts[:10])
    best=None
    for x,y in itertools.product(*choices):
        p,q=x[2],y[2]
        inter=base+x[0][0]+y[0][0]+sum(cross(g,h) for g in (p["upper"],p["lower"]) for h in (q["upper"],q["lower"]))
        gaps=[p["gap"],q["gap"]];clear=[p["surface_clearance"],q["surface_clearance"]]
        valid=inter==0 and (eng<.90 or (max(gaps)<=.02 and min(clear)>=-.001 and x[1] is not None and y[1] is not None))
        score=(int(not valid),inter,max(0,max(gaps)-.02) if eng>=.90 else 0,max(0,-min(clear)) if eng>=.90 else 0)
        if best is None or score<best[0]:best=(score,x,y,inter,valid)
        if valid:break
    _,x,y,inter,valid=best
    for l,sol in zip(arms,(x[2],y[2])):restore(l,sol["matrices"])
    bpy.context.view_layer.update()
    return {"phase":"rib_shoulder_hug","engagement":eng,"flight":False,"lift":0,"geometry_pass":valid,
            "intersections":inter,"fixed_body_intersections":base,"hand_surface_gaps":[x[2]["gap"],y[2]["gap"]],
            "surface_clearances":[x[2]["surface_clearance"],y[2]["surface_clearance"]],
            "half_thicknesses":[x[2]["half_thickness"],y[2]["half_thickness"]],
            "surface_anchors":[list(q) for q,n in anchors],"parameters":[x[1],y[1]],
            "arm_indices":[ix,iy],"arm_matrices":[x[2]["matrices"],y[2]["matrices"]]}

def search_hug(a,b,aa,bb,N):
    # Peak layout search includes side/side and side/shoulder-top contacts.
    # Bounded candidate grid, rank clean contact before any full-cycle test.
    layouts=[(s,d,ang,lean,.04,k0,k1,h0,h1,dep,mode)
             for s,d,ang,lean in itertools.product((.64,.74,.84,.94),(.0,.14,-.14),(.15,.32),(.055,.11))
             for k0,k1,h0,h1,dep,mode in (("rib","rib",.65,.65,.35,0),("rib","rib",.48,.78,.65,0),("rib","shoulder",.72,.9,.42,0),("shoulder","rib",.9,.72,.58,0),("rib","rib",.65,.65,.35,1))]
    ranked=[];attempts=[];peak_clean=0
    for layout in layouts:
        row=hug_solve(a,b,aa,bb,.5,1.,layout)
        score=(int(not row["geometry_pass"]),row["intersections"],max(row["hand_surface_gaps"]))
        ranked.append((score,layout,row["parameters"]));peak_clean+=int(row["geometry_pass"])
        attempts.append({"layout":list(layout),"peak_intersections":row["intersections"],"peak_hand_gaps":row["hand_surface_gaps"],"peak_pass":row["geometry_pass"]})
    ranked.sort(key=lambda x:x[0])
    print("HUG_PEAK",json.dumps({"layouts":len(layouts),"peak_clean":peak_clean,"best":ranked[:3]}),flush=True)
    best=None
    for _,layout,prior in ranked[:12]:
        rows=[]
        for f in range(N):
            row=hug_solve(a,b,aa,bb,f/(N-1),f/30,layout,prior)
            prior=row["parameters"];rows.append(row)
        score=(sum(not x["geometry_pass"] for x in rows),max(x["intersections"] for x in rows),
               max(max(x["hand_surface_gaps"]) for x in rows if x["engagement"]>=.90))
        attempts.append({"layout":list(layout),"full_score":list(score)})
        if best is None or score<best[0]:best=(score,layout,rows)
        if score[0]==0:break
    return best[1],best[2],attempts
