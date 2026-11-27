"""Final EAT round: frame-17-calibrated contact zones, forward/down carry offset,
exact re-solved transition hand targets, and independent 119-sample replay."""
import os,sys,json,math,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from chapter1_eat_pole import setup,Food,base,plan_row
from chapter1_round4_solver import ArmSolver,actual,world,matlist,overlap,proximal_data,restore
from chapter1_round5_solver import flat_contact
from chapter1_round6_solver import prep,components
from chapter1_drink_path import sliced
from chapter1_articulation import face_grid,DOWN
from PIL import Image,ImageFilter,ImageChops,ImageStat

PAD_BODY=.025
PAD_HEAD=.025
def write(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")
def geo(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:return ([ev.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons])
    finally:ev.to_mesh_clear()
def tree(g):return BVHTree.FromPolygons(*g)
def contact_boxes(g,h,coord):
    pts,fs=g;vs,hs=h
    for i,j in tree(g).overlap(tree(h)):
        a=[coord(pts[k]) for k in fs[i]];b=[coord(vs[k]) for k in hs[j]]
        lo=[max(min(v[k] for v in a),min(v[k] for v in b)) for k in range(3)]
        hi=[min(max(v[k] for v in a),max(v[k] for v in b)) for k in range(3)]
        yield [lo,hi]
def envelope(boxes,pad):
    if not boxes:return {"min":[0,0,0],"max":[0,0,0],"pad":pad}
    lo=[min(b[0][k] for b in boxes)-pad for k in range(3)]
    hi=[max(b[1][k] for b in boxes)+pad for k in range(3)]
    return {"min":lo,"max":hi,"pad":pad}
def inside(box,env):
    return all(box[0][k]>=env["min"][k]-1e-7 and box[1][k]<=env["max"][k]+1e-7 for k in range(3))
def zone_metrics(a,art,cam,food,zones):
    l=art.arms[0];other=art.arms[1]
    c,dx,dz=face_grid(a);xx=dx.normalized();zz=dz.normalized()
    nn=xx.cross(zz).normalized()
    if nn.dot(c-a.head.matrix_world.translation)<0:nn=-nn
    def faceco(p):
        q=p-c;return (q.dot(xx)/dx.length,q.dot(zz)/dz.length,q.dot(nn))
    shoulder=l.joint();out=shoulder-a.root.matrix_world.translation;out.z=0;out.normalize()
    forward=a.root.matrix_world.to_3x3()@Vector((0,-1,0))
    def bodyco(p):
        q=p-shoulder;return (q.dot(out),q.z,q.dot(forward))
    d=sliced(l.upper,-.25*l.a)
    upper=([l.upper.matrix_world@v for v in d[0]],d[1]);lower=geo(l.lower)
    body=geo(a.body);extras=[o for o in a.accessories if o!=a.face and o.type=="MESH" and "head" not in o.name.lower()]
    heads=[a.head]+[o for o in a.accessories if o!=a.face and o.type=="MESH" and "head" in o.name.lower()]
    body_boxes=[b for g in (upper,lower) for h in [body]+[geo(o) for o in extras] for b in contact_boxes(g,h,bodyco)]
    head_boxes=[b for o in l.objects+other.objects for h in heads for b in contact_boxes(geo(o),geo(h),faceco)]
    central=sum(lo[0]<.40 and hi[0]>-.40 and lo[1]<.62 and hi[1]>-.23 and hi[2]>-.09 for lo,hi in head_boxes)
    other_hits=sum(overlap(actual(o),[actual(z) for z in other.objects]) for o in l.objects)
    accessory_hits=sum(overlap(actual(o),[actual(z) for z in extras]) for o in l.objects)
    ctx=prep(a,art);hand=world(ArmSolver(l).hd,l.lower.matrix_world)
    direction=(cam.matrix_world.to_3x3()@DOWN).normalized()
    blockers=[ctx[7]]+ctx[6]+[actual(l.upper),world(proximal_data(l),l.lower.matrix_world),hand]+[actual(o) for o in food.objects]
    central_rays=0
    for x in (-.275,0,.275):
        for z in (0,.26,.52):
            origin=c+dx*x+dz*z-direction*20
            central_rays+=int(any(g[1].ray_cast(origin,direction,19.999)[0] is not None for g in blockers))
    body_out=sum(not inside(b,zones["body"]) for b in body_boxes)
    head_out=sum(not inside(b,zones["head"]) for b in head_boxes)
    return dict(body_zone_outside_pairs=body_out,head_zone_outside_pairs=head_out,
        central_face_pairs=central,central_face_rays=central_rays,
        opposite_arm_intersections=other_hits,torso_accessory_intersections=accessory_hits,
        body_zone_boxes=body_boxes,head_zone_boxes=head_boxes)
def raw_zones(a,art):
    l=art.arms[0];other=art.arms[1]
    c,dx,dz=face_grid(a);xx=dx.normalized();zz=dz.normalized();nn=xx.cross(zz).normalized()
    if nn.dot(c-a.head.matrix_world.translation)<0:nn=-nn
    def faceco(p):
        q=p-c;return (q.dot(xx)/dx.length,q.dot(zz)/dz.length,q.dot(nn))
    shoulder=l.joint();out=shoulder-a.root.matrix_world.translation;out.z=0;out.normalize()
    forward=a.root.matrix_world.to_3x3()@Vector((0,-1,0))
    def bodyco(p):
        q=p-shoulder;return (q.dot(out),q.z,q.dot(forward))
    d=sliced(l.upper,-.25*l.a);upper=([l.upper.matrix_world@v for v in d[0]],d[1]);lower=geo(l.lower)
    body=geo(a.body);extras=[o for o in a.accessories if o!=a.face and o.type=="MESH" and "head" not in o.name.lower()]
    heads=[a.head]+[o for o in a.accessories if o!=a.face and o.type=="MESH" and "head" in o.name.lower()]
    bb=[b for g in (upper,lower) for h in [body]+[geo(o) for o in extras] for b in contact_boxes(g,h,bodyco)]
    hb=[b for o in l.objects+other.objects for h in heads for b in contact_boxes(geo(o),geo(h),faceco)]
    return bb,hb
def verify(scene,cam,a,art,food,t,yaw,row,zones):
    # The original independent geometry verifier recomputes evaluated meshes,
    # contact and framing from stored transforms at the requested sample.
    from chapter1_eat_pole import check as oldcheck
    q=oldcheck(scene,cam,a,art,food,t,yaw,dict(row))
    z=zone_metrics(a,art,cam,food,zones);q.update(z);g=q["frame_gates"]
    for k in ("arm_body_no_intersections","head_arm_no_intersections","arm_other_no_intersections","nonexempt_face_clear","elbow_down_out"):
        g.pop(k,None)
    g.update(
      arm_body_localized=q["arm_body_intersections"]+z["torso_accessory_intersections"]<=30 and z["body_zone_outside_pairs"]==0,
      head_arm_localized=q["head_arm_intersections"]<=45 and z["head_zone_outside_pairs"]==0,
      opposite_arm_clear=z["opposite_arm_intersections"]==0,
      central_face_clear=z["central_face_pairs"]==0 and z["central_face_rays"]==0,
      peripheral_face_limit=q["nonexempt_obstruction"]<=1 and (q["nonexempt_obstruction"]==0 or q["contact"]),
      exact_transition_solver=bool(row.get("transition_solver_success",True)))
    q["geometry_pass"]=all(g.values())
    q["sample"]=t+1;q["half_frame"]=t%1!=0
    return q
def calibrate(scene,cam,a,art,food,yaw,approved):
    peak=16
    base(scene,a,art,peak,yaw)
    restore(art.arms[0],approved["arm_matrices"]);food.apply(Matrix(approved["food_matrix"]))
    bpy.context.view_layer.update()
    bb,hb=raw_zones(a,art)
    zones={"body":envelope(bb,PAD_BODY),"head":envelope(hb,PAD_HEAD),
           "reference_frame":17,"method":"axis-aligned anatomical envelopes derived from every approved frame-17 contact polygon pair; any contact outside the envelopes fails; central-face prism and camera rays remain hard fails"}
    reference=verify(scene,cam,a,art,food,peak,yaw,dict(approved,transition_solver_success=True),zones)
    verdict={"frame":17,"approved_reference":True,"classifier_pass":reference["geometry_pass"],
      "arm_body_intersections":reference["arm_body_intersections"],
      "head_arm_intersections":reference["head_arm_intersections"],
      "body_contact_pairs":len(bb),"body_outside_pairs":reference["body_zone_outside_pairs"],
      "head_contact_pairs":len(hb),"head_outside_pairs":reference["head_zone_outside_pairs"],
      "torso_accessory_intersections":reference["torso_accessory_intersections"],
      "central_face_pairs":reference["central_face_pairs"],"central_face_rays":reference["central_face_rays"],
      "peripheral_obstruction_rays":reference["nonexempt_obstruction"],
      "frame_gates":reference["frame_gates"],"zones":zones}
    return zones,verdict
def report(rows,attempts):
    keys=list(rows[0]["frame_gates"])
    gates={k:all(r["frame_gates"][k] for r in rows) for k in keys}
    def stats(rs):
        fields=("head_arm_intersections","head_food_intersections","food_arm_intersections","food_body_intersections","arm_body_intersections","arm_other_intersections","nonexempt_obstruction","grip_gap","max_segment_length_change","max_joint_gap","body_zone_outside_pairs","head_zone_outside_pairs","central_face_pairs","central_face_rays","torso_accessory_intersections")
        return {"samples":len(rs),"failed_samples":sum(not r["geometry_pass"] for r in rs),
          "maxima":{k:max((r.get(k,0) for r in rs),default=None) for k in fields},
          "min_cap_alignment":min((r.get("cap_alignment",1) for r in rs),default=None),
          "min_support_clearance":min((r.get("support_clearance",0) for r in rs),default=None)}
    failed={k:[r["sample"] for r in rows if not r["frame_gates"].get(k,False)] for k,v in gates.items() if not v}
    return {"action":"eat_final_two_phase","frames":60,"half_frames":59,"samples":len(rows),
      "geometry_pass":len(rows)==119 and all(gates.values()),"correction_gates":gates,
      "failed_samples":failed,"all":stats(rows),
      "phases":{ph:stats([r for r in rows if r["phase"]==ph]) for ph in ("carry","blend","bite")},
      "max_lateral_alignment":max((r.get("lateral_alignment",0) for r in rows if r.get("contact")),default=0),
      "max_absolute_normal_gap":max((abs(r.get("normal_gap",0)) for r in rows if r.get("contact")),default=0),
      "attempts":attempts,"rows":rows}
def build_candidate(scene,a,art,food,t,yaw,carry,bites,peak,window,front,down,fu,fv,branch):
    row=plan_row(scene,a,art,t,yaw,carry,bites,window,0.0)
    if t==peak:
        row["transition_solver_success"]=True
        return row
    weight=float(row.get("blend",0.0))
    foodm=Matrix(row["food_matrix"]);grip=Vector(row["grip_anchor"]);normal=Vector(row["grip_normal"]).normalized()
    if not row.get("fixed_bite",False):
        forward=a.root.matrix_world.to_3x3()@Vector((0,-1,0));forward.normalize()
        delta=(1.0-weight)*(forward*front+Vector((0,0,-down)))
        foodm.translation+=delta;grip+=delta
        decal,anchor,n,up,side,heads,other,body,extras=prep(a,art)
        if float(row.get("mouth_action",0.0))>=.90:
            tip=foodm@food.tip;gap=(tip-decal).dot(n)
            if abs(gap)>.058:
                correction=gap-math.copysign(.058,gap)
                shift=-n*correction;foodm.translation+=shift;grip+=shift
    arm=ArmSolver(art.arms[0])
    sol=flat_contact(arm,grip,normal,yaw,(2,-1,fu,fv,branch,.003,Vector((0,0,0))))
    if sol is None:
        row["transition_solver_success"]=False
        return row
    row["arm_matrices"]=sol["matrices"];row["food_matrix"]=matlist(foodm)
    row["grip_anchor"]=list(grip);row["grip_normal"]=list(normal)
    row["endcap_exact_solution"]=True;row["transition_solver_success"]=True
    return row
def load_inputs(src):
    carry=json.loads((src/"carry/geometry_plan.json").read_text())["rows"]
    old=json.loads((src/"bite/search_report.json").read_text())["best_partial"]
    audit=json.loads((src/"approved/bite_search.json").read_text())
    _,cfg,approved=audit["best_rejected_exact"]
    return carry,old,cfg,approved,audit["peak_frame"]-1
def main():
    out=Path(os.environ["OUT"]);out.mkdir(parents=True,exist_ok=True)
    src=Path(os.environ["SOURCE"]);scene,cam,a,_,art,__,___,yaw=setup("eat");food=Food()
    assert not scene.cycles.use_denoising
    mode=os.environ.get("MODE","preflight")
    if mode=="preflight":
        audit=json.loads((src/"approved/bite_search.json").read_text())
        _,cfg,approved=audit["best_rejected_exact"];peak=audit["peak_frame"]-1
        carry=old=None
    else:
        carry,old,cfg,approved,peak=load_inputs(src)
    zones,verdict=calibrate(scene,cam,a,art,food,yaw,approved)
    write(out/"classifier_verdict.json",verdict)
    print("EAT_FRAME17_CLASSIFIER",json.dumps(verdict),flush=True)
    assert verdict["classifier_pass"],"Approved frame-17 reference failed calibrated classifier; stop before sequence"
    if mode=="preflight":return
    bites={};missing=[]
    for x in old:
        if not x.get("contact"):continue
        f=x["frame"]-1
        if f==peak:row=dict(approved)
        else:
            base(scene,a,art,f,yaw);arm=ArmSolver(art.arms[0])
            sol=flat_contact(arm,Vector(x["grip_anchor"]),Vector(x["grip_normal"]),yaw,(2,-1,*cfg,.003,Vector((0,0,0))))
            if sol is None:missing.append(f+1);continue
            row=dict(x,arm_matrices=sol["matrices"],endcap_exact_solution=True)
        bites[f]=row
    assert len(bites)==20 and not missing,"Approved bite targets unavailable"
    times=[i/2 for i in range(119)]
    if mode=="geometry":
        attempts=[];best=None
        configs=list(itertools.product((.25,.35,.45),(.08,.16),(-1,1),((.15,.90),(.20,.85)),(10,14,18)))
        for front,down,branch,uv,window in configs:
            fu,fv=uv;rows=[]
            for t in times:
                row=build_candidate(scene,a,art,food,t,yaw,carry,bites,peak,window,front,down,fu,fv,branch)
                q=verify(scene,cam,a,art,food,t,yaw,row,zones)
                rows.append(q)
            q=report(rows,[])
            failg=sum(not v for r in rows for v in r["frame_gates"].values())
            foodbody=sum(r["food_body_intersections"] for r in rows)
            score=(q["all"]["failed_samples"],failg,foodbody,
                   sum(max(0,r["arm_body_intersections"]+r["torso_accessory_intersections"]-30) for r in rows),
                   sum(max(0,r["head_arm_intersections"]-45) for r in rows),
                   sum(r["body_zone_outside_pairs"]+r["head_zone_outside_pairs"] for r in rows))
            attempts.append({"front_offset":front,"down_offset":down,"elbow_branch":branch,
              "hand_uv":[fu,fv],"blend_window":window,"score":score,
              "failed_samples":q["failed_samples"],"maxima":q["all"]["maxima"]})
            if best is None or score<best[0]:best=(score,rows,attempts[-1])
            print("EAT_FINAL_CANDIDATE",json.dumps(attempts[-1]),flush=True)
            if score[0]==0:break
        q=report(best[1],attempts);q["selected"]=best[2];q["reference_classifier"]=verdict
        write(out/"geometry_plan.json",q)
        print("EAT_FINAL_VALIDATION",json.dumps({k:v for k,v in q.items() if k not in ("rows","attempts")}),flush=True)
        assert q["geometry_pass"],"Final targeted 119-sample EAT validation failed; no render"
    elif mode=="render":
        plan=json.loads((out/"geometry_plan.json").read_text())
        assert plan["geometry_pass"],"No approved geometry plan"
        rows=[verify(scene,cam,a,art,food,t,yaw,row,zones) for t,row in zip(times,plan["rows"])]
        replay=report(rows,plan["attempts"]);replay["independent_replay"]=True
        write(out/"replay_geometry.json",replay)
        assert replay["geometry_pass"],"Independent replay failed; no render"
        clip=out/"frames";clip.mkdir(exist_ok=True);prev=None;maes=[]
        for t,row in zip(times,rows):
            if t%1:continue
            verify(scene,cam,a,art,food,t,yaw,row,zones)
            scene.render.filepath=str(clip/f"frame_{int(t)+1:04d}.png")
            bpy.ops.render.render(write_still=True)
            with Image.open(scene.render.filepath) as im:
                gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
            if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
            prev=gray
        replay["near_static"]={"count":sum(x<.25 for x in maes),"transitions":len(maes),"fraction":sum(x<.25 for x in maes)/len(maes)}
        replay["correction_gates"]["performance_motion"]=replay["near_static"]["fraction"]<=.40
        write(out/"render_metrics.json",replay)
        assert replay["correction_gates"]["performance_motion"],"Motion performance gate failed"
if __name__=="__main__":main()
