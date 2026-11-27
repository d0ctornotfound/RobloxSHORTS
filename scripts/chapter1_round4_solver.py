"""Round 4 surface-contact solver. No bpy render calls. All contact/clearance
tests operate on the evaluated source meshes or rigidly transformed copies.
Search is bounded and deterministic; a failed solution is evidence, not a pass."""
import math,itertools,bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from character_motion import D,ramp,pulse,mix,floor
from chapter1_round2 import new_params as old_params,basic
from chapter1_articulation import face_grid,tree_for_object,clip,DOWN
from r6_character import bounds,mesh_points,dominant_group
from chapter1_round3 import body_meshes

EPS=.003
def data(ob,distal=None):
    if distal is None:
        return [v.co.copy() for v in ob.data.vertices],[tuple(p.vertices) for p in ob.data.polygons]
    verts=[];faces=[]
    for p in ob.data.polygons:
        poly=[(ob.data.vertices[i].co.copy(),Vector((0,0))) for i in p.vertices]
        cut=clip(poly,-.75*distal,False)
        if len(cut)<3:continue
        faces.append(tuple(range(len(verts),len(verts)+len(cut))))
        verts.extend(v for v,_ in cut)
    return verts,faces

def world(d,m):
    pts=[m@v for v in d[0]]
    return pts,BVHTree.FromPolygons(pts,d[1]),bounds(pts)
def actual(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:
        pts=[ev.matrix_world@v.co for v in me.vertices]
        return pts,BVHTree.FromPolygons(pts,[tuple(p.vertices) for p in me.polygons]),bounds(pts)
    finally:ev.to_mesh_clear()
def cross(a,b):
    al,ah=a[2];bl,bh=b[2]
    if any(ah[i]<bl[i]-1e-6 or bh[i]<al[i]-1e-6 for i in range(3)):return 0
    return len(a[1].overlap(b[1]))
def overlap(a,bs):return sum(cross(a,b) for b in bs)
def nearest(tree,p):
    q,n,i,d=tree[1].find_nearest(p)
    return (q,n,float(d)) if q is not None else (p,Vector((0,0,1)),999.)
def rays(cam,actor,blockers):
    c,dx,dz=face_grid(actor);direction=(cam.matrix_world.to_3x3()@DOWN).normalized()
    return sum(any(g[1].ray_cast(c+dx*x+dz*z-direction*20,direction,19.999)[0] is not None for g in blockers)
               for x in (-.55,-.275,0,.275,.55) for z in (-.52,-.26,0,.26,.52))
def proximal_data(limb):
    verts=[];faces=[]
    ob=limb.lower
    for p in ob.data.polygons:
        poly=[(ob.data.vertices[i].co.copy(),Vector((0,0))) for i in p.vertices]
        part=clip(poly,-.75*limb.b,True)
        if len(part)<3:continue
        faces.append(tuple(range(len(verts),len(verts)+len(part))))
        verts.extend(v for v,_ in part)
    return verts,faces

def eat_face_rays(cam,actor,nonhand,hand,contact):
    # Original 25 rays retained. Mask only distal-hand hits within the
    # neutral mouth decal footprint plus half a sampling cell, during
    # designated contact. No exemption for the forearm or other geometry.
    c,dx,dz=face_grid(actor);direction=(cam.matrix_world.to_3x3()@DOWN).normalized()
    blocked=0;exempt=0
    for x in (-.55,-.275,0,.275,.55):
        for z in (-.52,-.26,0,.26,.52):
            origin=c+dx*x+dz*z-direction*20
            other=any(g[1].ray_cast(origin,direction,19.999)[0] is not None for g in nonhand)
            hit=hand[1].ray_cast(origin,direction,19.999)[0] is not None
            mouth=contact and abs(x)<=.30 and abs(z+.365)<=.16
            blocked+=int(other or (hit and not mouth))
            exempt+=int(hit and mouth and not other)
    return blocked,exempt

def matlist(m):return [list(row) for row in m]
def restore(limb,mats):
    limb.upper.matrix_world=Matrix(mats[0]);limb.lower.matrix_world=Matrix(mats[1])
    limb.update_fabric()
def arm_matrices(limb,target,pole,yaw,roll):
    # Exact two-link IK, with free twist about the distal centreline.
    # No scale, no independent translation of a disconnected end.
    rot=Matrix.Rotation(yaw,3,"Z");s=limb.joint();dv=target-s;dist=dv.length
    axis=dv.normalized() if dist>1e-8 else rot@DOWN
    d=max(abs(limb.a-limb.b)+.0005,min(limb.a+limb.b-.0005,dist))
    x=(limb.a**2-limb.b**2+d*d)/(2*d)
    v=pole-axis*pole.dot(axis)
    if v.length<1e-7:v=axis.cross(Vector((0,0,1)))
    if v.length<1e-7:v=axis.cross(Vector((1,0,0)))
    elbow=s+axis*x+v.normalized()*math.sqrt(max(0,limb.a**2-x*x));end=s+axis*d
    def segment(a,b,twist):
        direction=(b-a).normalized()
        r=(rot@DOWN).rotation_difference(direction).to_matrix()@rot
        if twist:r=Matrix.Rotation(twist,3,direction)@r
        return Matrix.Translation(a)@r.to_4x4()
    return segment(s,elbow,0),segment(elbow,end,roll),end

class ArmSolver:
    def __init__(self,l):
        self.l=l;self.ud=data(l.upper);self.ld=data(l.lower);self.hd=data(l.lower,l.b)
        lo,hi=bounds(self.hd[0]);self.local_center=(lo+hi)/2
        self.half=(hi-lo)/2
    def solve(self,anchor,normal,pole,yaw,roll,weight,clearance=.004):
        # Find centerline endpoint using the actual oriented distal support
        # distance (half-thickness), then Newton-like surface residual updates.
        # Project a candidate hand center OUTWARD, never into the anchor plane.
        l=self.l;rest=l.transform()@l.end
        target=anchor+normal*(max(self.half.x,self.half.y)+clearance)
        desired=anchor+normal*clearance
        for _ in range(5):
            um,lm,end=arm_matrices(l,target,pole,yaw,roll)
            center=lm@self.local_center
            support=max((center-lm@v).dot(normal) for v in self.hd[0])
            wanted=anchor+normal*(support+clearance)
            # Align projected centre with the anchor and compensate for the
            # distal centre being above the actual arm endpoint.
            correction=wanted-center
            if correction.length<.0006:break
            target+=correction*.80
        # For the approach, blend from the actual rest endpoint to the
        # solved endpoint; never keyframe elbow angles. Contact holds at 1.
        goal=rest.lerp(target,weight)
        um,lm,end=arm_matrices(l,goal,pole,yaw,roll*weight)
        hand=world(self.hd,lm)
        if weight>=.999:
            # Residual refinement against the real distal surface.
            for _ in range(4):
                q,_,gap=nearest(hand,desired)
                error=desired-q
                if gap<.002:break
                trial=goal+error*.75
                uu,ll,ee=arm_matrices(l,trial,pole,yaw,roll)
                hh=world(self.hd,ll);_,_,ng=nearest(hh,desired)
                if ng>=gap-1e-6:break
                goal=trial;um,lm,end,hand=uu,ll,ee,hh
        upper=world(self.ud,um);lower=world(self.ld,lm)
        q,_,gap=nearest(hand,anchor)
        support=min((v-anchor).dot(normal) for v in hand[0])
        return {"matrices":[matlist(um),matlist(lm)],"upper":upper,"lower":lower,"hand":hand,"gap":gap,
                "surface_clearance":support,"half_thickness":float(max((lm@self.local_center-v).dot(normal) for v in hand[0])),
                "endpoint":list(end),"hand_surface_point":list(q)}
def eat_path(arm,anchor,n,up,side,pole,yaw,roll,w,cl,depth,drop,lat):
    # Solve the contact endpoint at the OUTWARD half-thickness plane.
    # Travel via a below-front waypoint, then approach vertically from
    # below while staying in front. Reverse this on withdrawal.
    l=arm.l;rest=l.transform()@l.end
    if w<=1e-7:
        um=l.upper.matrix_world.copy();lm=l.lower.matrix_world.copy()
    else:
        contact=arm.solve(anchor,n,pole,yaw,roll,1.,cl)
        final=Vector(contact["endpoint"])
        # The contact pose itself must not cross the head plane. If the
        # residual refinement penetrated, enforce support-plane projection.
        for _ in range(5):
            um,lm,end=arm_matrices(l,final,pole,yaw,roll)
            support=min((lm@v-anchor).dot(n) for v in arm.hd[0])
            if support>=cl-.0005:break
            final+=n*(cl-support+.001)
        waypoint=final+n*depth-up*drop+side*lat
        if w<.55:
            blend=ramp(w,0,.55);goal=rest.lerp(waypoint,blend)
        else:
            blend=ramp(w,.55,1.);goal=waypoint.lerp(final,blend)
        um,lm,end=arm_matrices(l,goal,pole,yaw,roll*min(1.,w/.55))
    hand=world(arm.hd,lm);upper=world(arm.ud,um);lower=world(arm.ld,lm)
    q,_,gap=nearest(hand,anchor)
    return {"matrices":[matlist(um),matlist(lm)],"upper":upper,"lower":lower,"hand":hand,
            "proximal":world(proximal_data(l),lm),"gap":gap,
            "surface_clearance":min((v-anchor).dot(n) for v in hand[0]),
            "half_thickness":float(max((lm@arm.local_center-v).dot(n) for v in hand[0])),
            "endpoint":list(lm@Vector((0,0,-l.b))),"hand_surface_point":list(q)}

def point_pose(actor,art,u,t,yaw):
    p=old_params("point",u,t);lead=pulse(u,0,.15,.70,1);hit=pulse(u,.15,.34,.59,.88)
    # No root crouch or moving feet. Neutral first and last frames; sustained
    # head/torso micro-motion and a brief emphasis during the point.
    wave=math.sin(math.tau*2.7*t)*hit
    emphasis=pulse(u,.35,.43,.47,.59)
    p.update(pitch=0,legs=[D,D],head=(.15*wave+.12*emphasis,0,.30*lead),
             torso=(.08*hit+.08*wave,0,.12*hit+.06*wave),
             arms=[mix(D,(0,-1,.055*wave),hit),mix(D,(.18,.18,-.94),hit)])
    basic(actor,p,(0,0,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))))
    return p
def mouth_anchor(actor):
    c,dx,dz=face_grid(actor);up=dz.normalized();side=dx.normalized()
    n=dx.cross(dz).normalized();head=actual(actor.head)
    hc=sum(head[0],Vector())/len(head[0])
    if n.dot(c-hc)<0:n=-n
    # Exact neutral young-face curve centre y=.6825 (variant texture source).
    decal=c-(2*.6825-1)*dz
    # Project through the decal to the actual head surface.
    q,_,_,_=head[1].ray_cast(decal+n*.1,-n,.25)
    if q is None:q,_,_=nearest(head,decal)
    return decal,q,n,up,side,head
def pole_set(n,up,side):
    return [side*math.cos(a)+up*math.sin(a)+n*d for a in [i*math.tau/12 for i in range(12)] for d in (.15,.8)]
def cup_pose_data(cup,anchor,n,up,side,az,tilt,clearance,weight,rest):
    # Highest rim edge touches the mouth. Remaining ring and cup body lie
    # below the mouth line. Tilt around a tangent-plane azimuth, about 30deg.
    z=Vector((0,0,1));horizontal=n-z*n.dot(z)
    if horizontal.length<1e-6:horizontal=side
    horizontal.normalize();lateral=z.cross(horizontal)
    tang=horizontal*math.cos(az)+lateral*math.sin(az)
    axis=(z*math.cos(tilt)+tang*math.sin(tilt)).normalized()
    rot=z.rotation_difference(axis).to_matrix()
    ring=[rot@cup.data.vertices[32+i].co for i in range(32)]
    # Choose the genuinely highest rim vertex; clearance is measured from
    # the head surface normal. Contact anchor remains within .02.
    top=max(ring,key=lambda v:v.z)
    pos=anchor+n*clearance-top
    # Rest cup is upright, beside the relaxed arm; interpolation moves the
    # cup and the grip target together.
    q0=z.rotation_difference(z);q1=z.rotation_difference(axis)
    rot=q0.slerp(q1,weight).to_matrix()
    pos=rest.lerp(pos,weight)
    return Matrix.Translation(pos)@rot.to_4x4()
def rim_distance(cup,m,anchor):
    pts=[m@cup.data.vertices[32+i].co for i in range(32)]
    ds=[]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        d=b-a;v=max(0,min(1,(anchor-a).dot(d)/d.length_squared));ds.append((anchor-a-d*v).length)
    return min(ds)
def mouth_solve(actor,art,cam,cup,yaw,p,prior=None):
    raw=p["mouth_action"];w=min(1,raw/.90);contact=raw>=.90
    decal,anchor,n,up,side,head=mouth_anchor(actor)
    # Measure collision against the actual head and its accessories.
    fixed=[actual(o) for o in body_meshes(actor) if o not in [x for l in art.arms for x in l.objects] and o!=actor.head]
    other=[actual(o) for o in art.arms[1].objects]
    actorbody=actual(actor.body)
    arm=ArmSolver(art.arms[0]);limb=arm.l
    headparts=[head]+[actual(o) for o in actor.accessories if o!=actor.face and o.type=="MESH" and "head" in o.name.lower()]
    # Pole and roll variables define rigid IK solutions, not hand-keyframed
    # angles. Search both approach clearance and support contact.
    poles=pole_set(n,up,side);rolls=(0,math.pi/4,-math.pi/4,math.pi/2,-math.pi/2,math.pi)
    rest=limb.transform()@limb.end+Vector((0,0,.08))
    cup_d=data(cup) if cup else None
    def evaluate(params):
        pi,roll,cl,az,tilt,grip=params
        pole=poles[int(pi)]
        if cup:
            cm=cup_pose_data(cup,anchor,n,up,side,az,tilt,cl,w,rest)
            cg=world(cup_d,cm);rim=rim_distance(cup,cm,decal)
            # Actual cup side surface, radial outward from cup axis.
            radial=Vector((math.cos(grip),math.sin(grip),0));gn=(cm.to_3x3()@radial).normalized()
            # Height -.025 is on outer tapered wall; ray finds exact mesh surface.
            origin=cm@Vector((0,0,-.025))
            gq,_,_,_=cg[1].ray_cast(origin+gn*.3,-gn,.5)
            if gq is None:gq,_,_=nearest(cg,origin+gn*.08)
            sol=arm.solve(gq,gn,pole,yaw,roll,1.,clearance=.003)
            cgap=sol["gap"]
            cup_arm=overlap(cg,[sol["upper"],sol["lower"]]+other)
            cuphead=overlap(cg,headparts)
            # Non-rim cup vertices must remain below the mouth line at sip.
            below=max(v.z-decal.z for j,v in enumerate(cg[0]) if not 32<=j<96)
            cupmat=matlist(cm)
        else:
            sol=eat_path(arm,anchor,n,up,side,pole,yaw,roll,w,cl,az,tilt,grip)
            cg=None;rim=None;cuphead=0;below=0;cgap=0;cupmat=None;cup_arm=0;gq=None
        geoms=[sol["upper"],sol["lower"]]
        headhits=sum(overlap(g,headparts) for g in geoms)+cuphead
        if cup:
            face=rays(cam,actor,[actorbody]+other+geoms+[cg]);exempt=0
        else:
            face,exempt=eat_face_rays(cam,actor,[actorbody]+other+[sol["upper"],sol["proximal"]],sol["hand"],contact)
        handgap=nearest(sol["hand"],decal)[2]
        gap=rim if cup else handgap
        # Never score a contact through the head. Require the hand to stay
        # on the outward side of the head plane when actually touching.
        clear=sol["surface_clearance"]
        support_pen=max(0,-clear-.001) if contact and not cup else 0
        grip_pen=max(0,cgap-.02) if cup else 0
        valid=headhits==0 and face==0 and (not contact or gap<=.02) and support_pen<=1e-6 and (not cup or (cgap<=.02 and cup_arm==0 and (not contact or below<=.002)))
        score=(int(not valid),headhits+face+cup_arm, max(0,gap-.02) if contact else 0,grip_pen+support_pen+max(0,below-.002) if contact or cup else 0,gap if contact else 0)
        row={"face_body_blocked_samples":face,"head_surface_intersections":headhits,"hand_to_mouth":handgap,
             "cup_rim_to_mouth":rim,"mouth_action":raw,"contact":contact,"grip_gap":cgap,"cup_body_above_mouth":below,
             "cup_arm_intersections":cup_arm,"grip_anchor":list(gq) if gq is not None else None,
             "hand_outward_clearance":clear,"measured_half_thickness":sol["half_thickness"],
             "mouth_decal_anchor":list(decal),"head_surface_anchor":list(anchor),"hand_surface_point":sol["hand_surface_point"],
             "parameters":list(params),"arm_matrices":sol["matrices"],"cup_matrix":cupmat,"geometry_pass":valid,
             "mouth_only_exempt_rays":exempt}
        return score,row
    # Deterministic coarse-to-fine search with previous-frame continuation.
    # Limit the search per frame and publish explicit exhausted failures.
    if cup:
        defaults=[(pi,ro,cl,az,tilt,gr) for pi in (2,5,8,11,14,17,20,23) for ro in (0,math.pi/2,-math.pi/2) for cl in (.004,.010) for az in (0,math.pi/2,-math.pi/2,math.pi) for tilt in (math.pi/6,) for gr in (0,math.pi/2,math.pi,-math.pi/2)]
    else:
        # Below-front waypoint parameters (depth, drop, lateral shift).
        # At contact they do not alter the target; at approach they steer
        # the elbow/hand around the head, not through it.
        paths=[(.20,.30,0),(.30,.38,.08),(.30,.38,-.08),(.13,.25,0)]
        defaults=[(pi,ro,cl,depth,drop,lat) for depth,drop,lat in paths for pi in range(len(poles)) for ro in rolls for cl in (.003,.006,.010)]
    candidates=([tuple(prior)] if prior is not None else [])+defaults
    best=None;tries=0
    for params in candidates:
        score,row=evaluate(params);tries+=1
        if best is None or score<best[0]:best=(score,row)
        if row["geometry_pass"]:break
    # Local numerical perturbations around best parameters.
    if not best[1]["geometry_pass"]:
        for scale in (1,.5,.25):
            center=best[1]["parameters"]
            for j,delta in ((1,.25*scale),(2,.002*scale),(3,.24*scale),(4,.035*scale),(5,.25*scale)):
                if not cup and j>2:
                    if contact:continue
                    delta=.025*scale
                for sign in (-1,1):
                    v=list(center);v[j]+=sign*delta
                    if v[2]<.001 or v[2]>.018:continue
                    if cup and not math.radians(25)<=v[4]<=math.radians(35):continue
                    if not cup and (v[3]<.08 or v[4]<.12):continue
                    score,row=evaluate(v);tries+=1
                    if score<best[0]:best=(score,row)
            if best[1]["geometry_pass"]:break
    row=best[1];row["search_evaluations"]=tries
    restore(limb,row["arm_matrices"])
    if cup:cup.matrix_world=Matrix(row["cup_matrix"])
    bpy.context.view_layer.update()
    return row

def torso_surface(actor,xf,zf):
    ob=actor.body;pts=mesh_points(ob);name=actor.bones["torso"].name
    faces=[tuple(p.vertices) for p in ob.data.polygons if dominant_group(ob,ob.data.vertices[p.vertices[0]])==name]
    tree=BVHTree.FromPolygons(pts,faces)
    local=actor.root.matrix_world.inverted();tp=[local@pts[i] for f in faces for i in f]
    lo,hi=bounds(tp)
    back=(actor.root.matrix_world.to_3x3()@Vector((0,1,0))).normalized()
    target=actor.root.matrix_world@Vector((lo.x+(hi.x-lo.x)*xf,hi.y+.5,lo.z+(hi.z-lo.z)*zf))
    q,n,_,_=tree.ray_cast(target,-back,1.5)
    if q is None:q,n,_,_=tree.find_nearest(target)
    if n.dot(back)<0:n=-n
    return q,n
def hug_base(a,b,aa,bb,u,t,layout):
    close,depth,angle,lean,xf,zf=layout
    eng=pulse(u,.05,.38,.69,.99);w=min(1,eng/.90)
    spacing=1.16+(close-1.16)*eng
    # Side-by-side shoulder lean, bodies angled toward each other. Native
    # torso lean pivots above planted legs. Head counter-tilts for clearance.
    yaws=(angle,-angle)
    for actor,art,sign,yaw in ((a,aa,-1,yaws[0]),(b,bb,1,yaws[1])):
        p=old_params("hug",u,t);p.update(pitch=0,legs=[D,D],arms=[D,D],torso=(.02*eng,sign*lean*eng,0),head=(0,-sign*.07*eng,0))
        basic(actor,p,(sign*spacing,sign*depth*eng,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
    return eng,w,yaws
def hug_solve(a,b,aa,bb,u,t,layout,prior=None):
    eng,w,yaws=hug_base(a,b,aa,bb,u,t,layout)
    ix=max(range(2),key=lambda i:aa.arms[i].joint().x)
    iy=min(range(2),key=lambda i:bb.arms[i].joint().x)
    arms=(aa.arms[ix],bb.arms[iy]);actors=(a,b);arts=(aa,bb)
    solvers=[ArmSolver(l) for l in arms]
    fixed=[]
    for actor,arm in zip(actors,arms):
        fixed.append([actual(o) for o in body_meshes(actor) if o not in arm.objects])
    base=sum(cross(x,y) for x in fixed[0] for y in fixed[1])
    xf,zf=layout[4:]
    anchors=[torso_surface(b,xf,zf),torso_surface(a,1-xf,max(.25,zf-.32))]
    candidates=[]
    for i in range(2):
        anchor,n=anchors[i];side=Vector((1 if i==0 else -1,0,0));up=Vector((0,0,1))
        poles=[n*math.cos(ang)+up*math.sin(ang)+side*d for ang in [j*math.tau/12 for j in range(12)] for d in (.15,.65)]
        opts=[];params=[(j,ro,cl) for j in range(len(poles)) for ro in (0,math.pi/2,-math.pi/2,math.pi) for cl in (.004,.009)]
        if prior:params=[tuple(prior[i])]+params
        for j,ro,cl in params:
            s=solvers[i].solve(anchor,n,poles[int(j)],yaws[i],ro,w,cl)
            c=overlap(s["upper"],fixed[1-i])+overlap(s["lower"],fixed[1-i])
            gp=s["gap"] if eng>=.90 else 0
            score=(c,max(0,gp-.02),gp)
            opts.append((score,(j,ro,cl),s))
            if c==0 and (eng<.90 or gp<=.02) and len([x for x in opts if x[0][0]==0 and x[0][1]==0])>=6:break
        opts.sort(key=lambda x:x[0]);candidates.append(opts[:10])
    best=None;tests=0
    for x,y in itertools.product(*candidates):
        s0,s1=x[2],y[2];tests+=1
        inter=base+x[0][0]+y[0][0]+sum(cross(p,q) for p in (s0["upper"],s0["lower"]) for q in (s1["upper"],s1["lower"]))
        gap=max(s0["gap"],s1["gap"])
        valid=inter==0 and (eng<.90 or gap<=.02) and (eng<.90 or min(s0["surface_clearance"],s1["surface_clearance"])>=-.001)
        score=(int(not valid),inter,max(0,gap-.02) if eng>=.90 else 0,gap if eng>=.90 else 0)
        if best is None or score<best[0]:best=(score,x,y,inter,valid)
        if valid:break
    _,x,y,inter,valid=best
    for l,s in zip(arms,(x[2],y[2])):restore(l,s["matrices"])
    bpy.context.view_layer.update()
    return {"phase":"shoulder_hug","engagement":eng,"flight":False,"lift":0,"geometry_pass":valid,
            "intersections":inter,"fixed_body_intersections":base,"hand_surface_gaps":[x[2]["gap"],y[2]["gap"]],
            "surface_clearances":[x[2]["surface_clearance"],y[2]["surface_clearance"]],"half_thicknesses":[x[2]["half_thickness"],y[2]["half_thickness"]],
            "back_anchors":[list(z[0]) for z in anchors],"parameters":[list(x[1]),list(y[1])],
            "arm_indices":[ix,iy],"arm_matrices":[x[2]["matrices"],y[2]["matrices"]],"search_evaluations":tests}
def search_hug(a,b,aa,bb,N):
    # Geometry-only search: test peak first, then coarse frames, then all 60.
    # No image rendering before the full-sequence pass. Save best failed
    # attempt as well, but never authorize it for rendering.
    layouts=[(s,d,ang,lean,xf,zf) for s in (.61,.71,.81,.91) for d in (.04,.16,-.12) for ang in (.12,.28) for lean in (.05,.11) for xf,zf in ((.22,.78),(.36,.70))]
    results=[];ranked=[]
    for layout in layouts:
        row=hug_solve(a,b,aa,bb,.5,1.,layout)
        score=(row["intersections"],max(row["hand_surface_gaps"]))
        ranked.append((score,layout));results.append({"layout":list(layout),"peak_intersections":score[0],"peak_gap":score[1],"peak_pass":row["geometry_pass"]})
        if row["geometry_pass"]:
            # Early full-cycle test only when peak is already clean.
            prior=None;rows=[]
            for f in range(N):
                q=hug_solve(a,b,aa,bb,f/(N-1),f/30,layout,prior);prior=q["parameters"];rows.append(q)
            good=all(q["geometry_pass"] for q in rows)
            results[-1].update(full_cycle_pass=good,max_intersections=max(q["intersections"] for q in rows),failed_frames=[f+1 for f,q in enumerate(rows) if not q["geometry_pass"]])
            if good:return layout,rows,results
    # Report the best failed layout across all frames, not just peak.
    _,layout=min(ranked)
    rows=[];prior=None
    for f in range(N):
        q=hug_solve(a,b,aa,bb,f/(N-1),f/30,layout,prior);prior=q["parameters"];rows.append(q)
    return layout,rows,results
