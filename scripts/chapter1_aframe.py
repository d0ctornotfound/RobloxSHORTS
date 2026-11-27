"""A-frame hug candidate. Geometry only. Route arms outside torso corridor,
then approach evaluated shoulder top from above. No changes to approved assets."""
import math,itertools,json,bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from character_motion import D,ramp,mix,floor
from chapter1_round2 import new_params as old_params,basic
from chapter1_round4_solver import actual,data,world,nearest,overlap,cross,ArmSolver,arm_matrices,restore,matlist
from chapter1_round5_solver import pack
from chapter1_round3 import body_meshes
from r6_character import bounds,mesh_points,dominant_group

def phase(u):
    raise_=ramp(u,0,.20)*(1-ramp(u,.80,1))
    lean=ramp(u,.20,.40)*(1-ramp(u,.64,.80))
    contact=ramp(u,.40,.51)*(1-ramp(u,.59,.68))
    name="raise_outside" if u<.20 else "lean_in" if u<.40 else "land" if u<.51 else "hold" if u<.59 else "lift_off" if u<.68 else "lean_out" if u<.80 else "lower"
    return raise_,lean,contact,name

def torso(actor):
    ob=actor.body;pts=mesh_points(ob);name=actor.bones["torso"].name
    faces=[tuple(p.vertices) for p in ob.data.polygons if dominant_group(ob,ob.data.vertices[p.vertices[0]])==name]
    vertices=[pts[i] for f in faces for i in f]
    return vertices,BVHTree.FromPolygons(pts,faces),bounds(vertices)

def shoulder_top(actor,outer,xf,yf):
    # Use the actual evaluated torso, not rest-pose AABB or back-centre.
    # Pick outer shoulder along WORLD Y, away from the head/torso gap,
    # and search along the top surface with vertical rays.
    pts,tree,(lo,hi)=torso(actor)
    xx=lo.x+(hi.x-lo.x)*xf;yy=lo.y+(hi.y-lo.y)*(yf if outer>0 else 1-yf)
    start=Vector((xx,yy,hi.z+.25))
    q,n,_,_=tree.ray_cast(start,Vector((0,0,-1)),1.5)
    if q is None:
        # Nearest surface fallback may not be a shoulder top. Retain
        # for diagnostics but explicitly gate on upward facing normal.
        q,n,_,_=tree.find_nearest(start)
    if n.z<0:n=-n
    return q,n.normalized()

def hug_base(a,b,aa,bb,u,t,layout):
    spacing,leanangle,turn,depth,xf,yf,outer,spread=layout
    raise_,lean,cl,ph=phase(u)
    yaws=(turn,-turn)
    for actor,art,sign,yaw in ((a,aa,-1,yaws[0]),(b,bb,1,yaws[1])):
        p=old_params("hug",u,t)
        # Local forward is -Y. Rotate torso about local X toward partner;
        # hips remain fixed apart; no step/torso translation.
        p.update(pitch=0,legs=[D,D],torso=(leanangle*lean,0,0),head=(.035*lean,0,0),
                 arms=[mix(D,(-spread,.12,.30),raise_),mix(D,(spread,.12,.30),raise_)])
        basic(actor,p,(sign*spacing/2,sign*depth/2,0),yaw)
        art.rigid();art.shift(Vector((0,0,-floor(actor))));actor.pose("happy")
    return cl,raise_,lean,ph,yaws
def hug_anchors(a,b,layout):
    _,_,_,_,xf,yf,outer,_=layout
    # Contact on opposite outer sides; distinct routes avoid arm-arm crossing.
    return [shoulder_top(b,outer,xf,yf),shoulder_top(a,-outer,1-xf,yf)]

def corridor_count(geoms,t0,t1):
    # Conservative diagnostic: below shoulder-top band, count arm vertices
    # inside the shared front/back extent AND between torso centroids.
    # Shoulder-top landing band is excluded, not intersections.
    (al,ah),(bl,bh)=t0[2],t1[2]
    y0=max(al.y,bl.y);y1=min(ah.y,bh.y)
    x0=(al.x+ah.x)/2;x1=(bl.x+bh.x)/2
    z0=max(al.z,bl.z);z1=min(ah.z,bh.z)-.035
    if y1<=y0 or z1<=z0:return 0
    # Ignore vertices inside own torso's horizontal footprint? No:
    # route after leaving shoulder must clear common corridor. Native
    # shoulder attachment itself is excluded by checking distal segments
    # and upper beyond proximal quarter.
    return sum(x0+.03<v.x<x1-.03 and y0+.015<v.y<y1-.015 and z0<v.z<z1 for g in geoms for v in g[0])

def candidate(a,b,aa,bb,u,t,layout,params):
    cl,raise_,lean,ph,yaws=hug_base(a,b,aa,bb,u,t,layout)
    outer=layout[6];arms=[];indices=[]
    for art,sg in ((aa,outer),(bb,-outer)):
        i=max(range(2),key=lambda i:sg*art.arms[i].joint().y)
        indices.append(i);arms.append(art.arms[i])
    anchors=hug_anchors(a,b,layout);ts=(torso(a),torso(b))
    fixed=[[actual(o) for o in body_meshes(actor) if o not in l.objects] for actor,l in zip((a,b),arms)]
    fixed_inter=sum(cross(x,y) for x in fixed[0] for y in fixed[1])
    sols=[];corr=0
    from chapter1_drink_path import sliced
    for i,l in enumerate(arms):
        arm=ArmSolver(l);anchor,n=anchors[i];sg=outer if i==0 else -outer
        extra,poleup,roll,clear=params[i]
        # Shoulder joint outside selected silhouette, elbow pole remains
        # outward. First raise to an outward/upward waypoint, then only
        # once leaned in approach shoulder top from above/outside.
        outward=Vector((0,sg,0));up=Vector((0,0,1))
        rest=l.transform()@l.end
        # Solve actual contact with hand surface offset, not wrist target.
        final=arm.solve(anchor,n,outward+up*poleup,yaws[i],roll,1.,clear)
        target=Vector(final["endpoint"])
        waypoint=l.joint()+outward*(.47+extra)+up*.33
        # Shoulder and head motion changes the waypoint with the body.
        # During closure keep approach on above/outside route.
        target=waypoint.lerp(target,cl)
        goal=rest.lerp(target,raise_)
        if cl>=.999:
            sol=final
        else:
            um,lm,end=arm_matrices(l,goal,outward+up*poleup,yaws[i],roll*raise_)
            sol=pack(arm,um,lm,anchor,n)
        sols.append(sol)
        um=Matrix(sol["matrices"][0]);upper=world(sliced(l.upper,-.25*l.a),um)
        corr+=corridor_count([upper,sol["lower"]],*ts)
    inter=fixed_inter
    for i,sol in enumerate(sols):inter+=overlap(sol["upper"],fixed[1-i])+overlap(sol["lower"],fixed[1-i])
    inter+=sum(cross(x,y) for x in (sols[0]["upper"],sols[0]["lower"]) for y in (sols[1]["upper"],sols[1]["lower"]))
    gaps=[s["gap"] for s in sols];clearances=[s["surface_clearance"] for s in sols]
    tops=[n.z for q,n in anchors]
    valid=inter==0 and corr==0 and (cl<.90 or (max(gaps)<=.02 and min(clearances)>=-.001 and min(tops)>=.60))
    for l,sol in zip(arms,sols):restore(l,sol["matrices"])
    bpy.context.view_layer.update()
    return {"geometry_pass":valid,"phase":ph,"engagement":cl,"opening":raise_,"lean":lean,
        "intersections":inter,"fixed_body_intersections":fixed_inter,"corridor_vertices":corr,
        "hand_surface_gaps":gaps,"surface_clearances":clearances,"shoulder_top_normal_z":tops,
        "surface_anchors":[list(q) for q,n in anchors],"parameters":[list(p) for p in params],
        "arm_indices":indices,"arm_matrices":[s["matrices"] for s in sols],
        "all_arm_matrices":[[[matlist(l.upper.matrix_world),matlist(l.lower.matrix_world)] for l in art.arms] for art in (aa,bb)]}

def score(row):
    c=row["engagement"]>=.90
    return (int(not row["geometry_pass"]),row["intersections"],row["corridor_vertices"],
        max(0,max(row["hand_surface_gaps"])-.02) if c else 0,
        max(0,-min(row["surface_clearances"])-.001) if c else 0,
        max(0,.60-min(row["shoulder_top_normal_z"])) if c else 0)

def search_hug(a,b,aa,bb,N):
    # Requested hips ~1.2 apart; lean in the requested 15–20° range.
    layouts=list(itertools.product((1.10,1.20,1.30),map(math.radians,(15,17.5,20)),
        map(math.radians,(75,90)),(-.07,.07),(.30,.50,.70),(.73,.87),(-1,1),(.95,)))
    # Bounded numerical peak search with diverse arm poles and roll.
    # Keep parameters fixed throughout each candidate path.
    ranked=[];attempts=[];peak_clean=0;tests=0
    bank=[(.12,p,roll,cl) for p,roll,cl in itertools.product((.25,.8,1.4),(0,math.pi/2,-math.pi/2),(.004,.010))]
    # Broad layout scan with three representative arm configurations,
    # followed by full branch search on the top layouts.
    for layout in layouts:
        local=[]
        for j in (0,8,16):
            params=(bank[j],bank[j]);row=candidate(a,b,aa,bb,.55,1.1,layout,params);tests+=1
            local.append((score(row),layout,params,row))
        local.sort(key=lambda x:x[0]);ranked.append(local[0])
    ranked.sort(key=lambda x:x[0]);refined=[]
    for _,layout,_,_ in ranked[:24]:
        best=None
        for p,q in itertools.product(bank,bank):
            row=candidate(a,b,aa,bb,.55,1.1,layout,(p,q));tests+=1
            sc=score(row)
            if best is None or sc<best[0]:best=(sc,layout,(p,q),row)
            if row["geometry_pass"]:break
        refined.append(best)
    ranked=sorted(ranked+refined,key=lambda x:x[0])
    peak_clean=sum(x[3]["geometry_pass"] for x in ranked)
    attempts.append({"layout_count":len(layouts),"peak_evaluations":tests,"peak_clean":peak_clean,
        "best_peak":[{"layout":list(l),"params":p,"score":list(sc),"gaps":row["hand_surface_gaps"]} for sc,l,p,row in ranked[:10]]})
    print("AFRAME_PEAK",json.dumps(attempts[0]),flush=True)
    best=None
    for _,layout,params,_ in ranked[:20]:
        for extra in (.06,.18,.28):
            config=tuple((extra,)+tuple(p[1:]) for p in params)
            rows=[candidate(a,b,aa,bb,f/(N-1),f/30,layout,config) for f in range(N)]
            contacts=[x for x in rows if x["engagement"]>=.90]
            sc=(sum(not x["geometry_pass"] for x in rows),max(x["intersections"] for x in rows),
                max(x["corridor_vertices"] for x in rows),max(max(x["hand_surface_gaps"]) for x in contacts))
            attempts.append({"layout":list(layout),"parameters":config,"full_score":list(sc)})
            if best is None or sc<best[0]:best=(sc,layout,rows)
            if sc[0]==0:break
        if best[0][0]==0:break
    return best[1],best[2],attempts
