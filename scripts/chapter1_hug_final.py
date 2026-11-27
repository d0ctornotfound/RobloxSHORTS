"""Final one-sided over-shoulder drape; bounded geometry search.
If no clean drape, separately test the authorized arms-down shoulder lean."""
import math,itertools,json,bpy
from mathutils import Vector,Matrix
from character_motion import D,ramp,mix,floor
from chapter1_round2 import basic,new_params as old_params
from chapter1_round4_solver import actual,world,data,nearest,overlap,cross,ArmSolver,arm_matrices,restore,matlist
from chapter1_round5_solver import pack
from chapter1_round3 import body_meshes,cross_intersections
from chapter1_aframe import torso
from r6_character import bounds
from chapter1_drink_path import sliced

def phase(u):
    raise_=ramp(u,0,.20)*(1-ramp(u,.80,1))
    approach=ramp(u,.20,.40)*(1-ramp(u,.64,.80))
    close=ramp(u,.40,.51)*(1-ramp(u,.59,.64))
    name="raise" if u<.20 else "step_in" if u<.40 else "drape" if u<.51 else "hold" if u<.59 else "lift_off" if u<.64 else "step_out" if u<.80 else "lower"
    return raise_,approach,close,name

def hug_base(a,b,aa,bb,u,t,layout):
    mode,spacing,offset,turn,lean,headyaw,xf,zf=layout
    op,ap,cl,ph=phase(u)
    if mode=="drape":
        # Friend stays at origin in precisely the same neutral pose.
        p=old_params("hug",0,0);p.update(pitch=0,legs=[D,D],arms=[D,D],torso=(0,0,0),head=(0,0,0))
        basic(b,p,(0,0,0),-math.pi/2);bb.rigid();bb.shift(Vector((0,0,-floor(b))));b.pose("neutral")
        p=old_params("hug",u,t)
        step=.20*math.sin(math.tau*2*ap) if 0<ap<1 else 0
        p.update(pitch=0,legs=[(0,step,-1),(0,-step,-1)],arms=[D,D],
            torso=(lean*ap,0,0),head=(0,0,headyaw*op))
        yaw=math.pi/2+turn*ap
        basic(a,p,(-1.9+(1.9-spacing)*ap,offset*ap,0),yaw);aa.rigid();aa.shift(Vector((0,0,-floor(a))));a.pose("happy")
    else:
        # Fallback is explicitly not a wrap: side-by-side, both arms down.
        for actor,art,sg in ((a,aa,-1),(b,bb,1)):
            p=old_params("hug",0,0);p.update(pitch=0,legs=[D,D],arms=[D,D],
                torso=(0,-sg*lean*ap,0),head=(0,-sg*.07*ap,0))
            basic(actor,p,(sg*spacing/2,0,0),0);art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
        yaw=0
    return cl,op,ap,ph,yaw

def anchors(b,layout):
    _,_,_,_,_,_,xf,zf=layout
    verts,tree,(lo,hi)=torso(b)
    # Friend faces -X, its back faces +X. Ray into the actual upper-back
    # torso surface on two sides of the spine.
    result=[]
    for frac in (xf,1-xf):
        q0=Vector((hi.x+.4,lo.y+(hi.y-lo.y)*frac,lo.z+(hi.z-lo.z)*zf))
        q,n,_,_=tree.ray_cast(q0,Vector((-1,0,0)),1.5)
        if q is None:q,n,_,_=tree.find_nearest(q0)
        if n.x<0:n=-n
        result.append((q,n.normalized()))
    return result
def head_parts(actor):
    return [actual(actor.head)]+[actual(o) for o in actor.accessories if o.type=="MESH" and o!=actor.face and "head" in o.name.lower()]
def friend_signature(b):
    return [list(v) for o in body_meshes(b) for v in actual(o)[0]]
def static_delta(b,reference):
    pts=friend_signature(b)
    if len(pts)!=len(reference):return 999.
    return max(((Vector(p)-Vector(q)).length for p,q in zip(pts,reference)),default=0.)
def shoulder_gap(a,b):
    av,at,(al,ah)=torso(a);bv,bt,(bl,bh)=torso(b)
    # Actual upper torso surfaces; restrict both nearest points to upper band.
    vals=[]
    for pts,tree,lo,hi,olo,ohi in ((av,bt,al,ah,bl,bh),(bv,at,bl,bh,al,ah)):
        for v in pts:
            if v.z<lo.z+.72*(hi.z-lo.z):continue
            q,n,i,d=tree.find_nearest(v)
            if q is not None and q.z>=olo.z+.72*(ohi.z-olo.z):vals.append(d)
    return min(vals,default=999.)
def diagnostics(a,b,aa,bb,layout,cl,ph,ref):
    inter=cross_intersections(a,b);ha=head_parts(a);hb=head_parts(b)
    headhead=sum(cross(x,y) for x in ha for y in hb)
    leadarms=[actual(o) for l in aa.arms for o in l.objects]
    friendarms=[actual(o) for l in bb.arms for o in l.objects]
    headarm=sum(overlap(g,ha+hb) for g in leadarms+friendarms)
    own_arm_inter=sum(cross(actual(x),actual(y)) for x in aa.arms[0].objects for y in aa.arms[1].objects)
    gap=[];clear=[];elbow=[];drop=[];normals=[]
    if layout[0]=="drape":
        # Pair by actual world-Y shoulder order, and ensure elbows above
        # the upper-back contact with downward forearm direction.
        ids=sorted(range(2),key=lambda i:aa.arms[i].joint().y)
        qs=sorted(anchors(b,layout),key=lambda z:z[0].y)
        top=torso(b)[2][1].z
        for i,(q,n) in zip(ids,qs):
            l=aa.arms[i];hand=world(data(l.lower,l.b),l.lower.matrix_world)
            gap.append(nearest(hand,q)[2]);clear.append(min((v-q).dot(n) for v in hand[0]))
            e=l.lower.matrix_world.translation;end=l.lower.matrix_world@Vector((0,0,-l.b))
            elbow.append(e.z-top);drop.append(e.z-end.z);normals.append(n.x)
        # Measured lateral head-centre displacement (world Y), not yaw alone.
        ahc=sum(ha[0][0],Vector())/len(ha[0][0]);bhc=sum(hb[0][0],Vector())/len(hb[0][0])
        hoff=abs(ahc.y-bhc.y);fd=static_delta(b,ref)
        own_body=sum(overlap(world(sliced(l.upper,-.25*l.a),l.upper.matrix_world),[actual(a.body)])+overlap(actual(l.lower),[actual(a.body)]) for l in aa.arms)
        valid=inter==headhead==headarm==own_arm_inter==own_body==0 and fd<=1e-5 and (cl<.90 or (max(gap)<=.02 and min(clear)>=-.001 and min(elbow)>=-.06 and min(drop)>=.05 and min(normals)>=.60 and hoff>=.15))
        sg=None
    else:
        sg=shoulder_gap(a,b);fd=None;hoff=None;own_body=0
        valid=inter==headhead==headarm==own_arm_inter==0 and (cl<.90 or sg<=.02)
    return {"geometry_pass":valid,"phase":ph,"engagement":cl,"intersections":inter,
        "head_head_intersections":headhead,"head_arm_intersections":headarm,"lead_arm_arm_intersections":own_arm_inter,
        "lead_arm_body_intersections":own_body,"hand_surface_gaps":gap,"surface_clearances":clear,
        "elbow_height_over_shoulder":elbow,"forearm_vertical_drop":drop,"back_normal_x":normals,
        "head_lateral_offset":hoff,"friend_static_delta":fd,"shoulder_gap":sg}
def candidate(a,b,aa,bb,u,t,layout,params,ref):
    cl,op,ap,ph,yaw=hug_base(a,b,aa,bb,u,t,layout)
    if layout[0]=="drape":
        ids=sorted(range(2),key=lambda i:aa.arms[i].joint().y)
        qs=sorted(anchors(b,layout),key=lambda z:z[0].y)
        for idx,(q,n),sg in zip(ids,qs,(-1,1)):
            l=aa.arms[idx];arm=ArmSolver(l);up=Vector((0,0,1));out=Vector((0,sg,0))
            poleup,poleout,roll,clear=params
            pole=up*poleup+out*poleout+Vector((-.1,0,0))
            rest=l.transform()@l.end
            sol=arm.solve(q,n,pole,yaw,roll,1.,clear)
            waypoint=l.joint()+out*.34+up*.40+Vector((.12,0,0))
            goal=rest.lerp(waypoint.lerp(Vector(sol["endpoint"]),cl),op)
            if cl<.999:
                um,lm,end=arm_matrices(l,goal,pole,yaw,roll*op);sol=pack(arm,um,lm,q,n)
            restore(l,sol["matrices"])
    bpy.context.view_layer.update()
    row=diagnostics(a,b,aa,bb,layout,cl,ph,ref)
    row["all_arm_matrices"]=[[[matlist(l.upper.matrix_world),matlist(l.lower.matrix_world)] for l in art.arms] for art in (aa,bb)]
    return row
def score(row):
    contact=row["engagement"]>=.90
    return (int(not row["geometry_pass"]),row["intersections"]+row["head_arm_intersections"]+row["lead_arm_arm_intersections"]+row["lead_arm_body_intersections"],
            max(0,max(row["hand_surface_gaps"],default=0)-.02) if contact else 0,
            max(0,(row["shoulder_gap"] or 0)-.02) if contact else 0)
def search_hug(a,b,aa,bb,N):
    layouts=[("drape",s,off,turn,lean,hy,xf,zf) for s,off,turn,lean,hy,xf,zf in itertools.product(
        (.85,1.0,1.15,1.30),(-.32,.32),(-.10,.10),(.05,.12),(-.30,.30),(.18,.30),(.78,.90))]
    bank=list(itertools.product((1.0,2.0),(.25,.85),(0,math.pi/2,-math.pi/2),(.004,.009)))
    hug_base(a,b,aa,bb,0,0,layouts[0]);ref=friend_signature(b)
    ranked=[];attempts=[];tested=0
    for layout in layouts:
        local=[]
        for p in (bank[0],bank[8],bank[16]):
            row=candidate(a,b,aa,bb,.55,1.1,layout,p,ref);tested+=1;local.append((score(row),layout,p))
        ranked.append(min(local))
    ranked.sort()
    refined=[]
    for _,layout,_ in ranked[:24]:
        for p in bank:
            row=candidate(a,b,aa,bb,.55,1.1,layout,p,ref);tested+=1
            refined.append((score(row),layout,p))
    ranked=sorted(ranked+refined)
    attempts.append({"drape_layouts":len(layouts),"peak_evaluations":tested,"peak_clean":sum(x[0][0]==0 for x in ranked),"best_peak":ranked[:5]})
    print("DRAPE_PEAK",json.dumps(attempts[0]),flush=True)
    best=None
    for _,layout,p in ranked[:36]:
        rows=[candidate(a,b,aa,bb,f/(N-1),f/30,layout,p,ref) for f in range(N)]
        sc=(sum(not x["geometry_pass"] for x in rows),sum(score(x)[1] for x in rows),max(max(x["hand_surface_gaps"],default=0) for x in rows if x["engagement"]>=.90))
        attempts.append({"layout":layout,"parameters":p,"full_score":sc})
        if best is None or sc<best[0]:best=(sc,layout,rows)
        if sc[0]==0:return layout,rows,attempts,ref,None
    drape={"layout":best[1],"rows":best[2],"score":best[0]}
    # Only after final drape failure, test the separately authorized fallback.
    fallback=None
    for sp,le in itertools.product((.90,1.0,1.1,1.2,1.3,1.4,1.5),map(math.radians,(5,10,15,20))):
        layout=("shoulder_lean",sp,0,0,le,0,.25,.85)
        rows=[candidate(a,b,aa,bb,f/(N-1),f/30,layout,bank[0],ref) for f in range(N)]
        sc=(sum(not x["geometry_pass"] for x in rows),sum(score(x)[1] for x in rows),max(x["shoulder_gap"] for x in rows if x["engagement"]>=.90))
        attempts.append({"fallback_layout":layout,"full_score":sc})
        if fallback is None or sc<fallback[0]:fallback=(sc,layout,rows)
        if sc[0]==0:break
    return fallback[1],fallback[2],attempts,ref,drape
