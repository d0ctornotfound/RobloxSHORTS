"""Supervisor-approved bite reference; full motion still unapproved."""
import sys,os,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from chapter1_eat_pole import setup,Food,base,plan_row,check as oldcheck,summary,write
from chapter1_round4_solver import ArmSolver,actual,world,matlist,overlap,proximal_data
from chapter1_round5_solver import flat_contact
from chapter1_round6_solver import prep
from chapter1_drink_path import sliced
from chapter1_articulation import face_grid,DOWN
from PIL import Image,ImageFilter,ImageChops,ImageStat

def geo(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:return ([ev.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons])
    finally:ev.to_mesh_clear()
def tree(g):return BVHTree.FromPolygons(*g)
def contact_boxes(g,h,coord):
    # Conservative intersection AABB of the actual overlapping polygon pairs,
    # expressed in anatomical coordinates (not camera screen coordinates).
    pts,fs=g;vs,hs=h
    for i,j in tree(g).overlap(tree(h)):
        a=[coord(pts[k]) for k in fs[i]];b=[coord(vs[k]) for k in hs[j]]
        lo=[max(min(v[k] for v in a),min(v[k] for v in b)) for k in range(3)]
        hi=[min(max(v[k] for v in a),max(v[k] for v in b)) for k in range(3)]
        yield lo,hi
def zone_metrics(a,art,cam,food,row):
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
    # An upper torso corner: within 0.42 scene units below shoulder,
    # no more than 0.30 inward and 0.34 fore/aft from shoulder joint.
    body_boxes=[b for g in (upper,lower) for h in [body]+[geo(o) for o in extras] for b in contact_boxes(g,h,bodyco)]
    body_bad=sum(lo[0]<-.30 or lo[1]<-.42 or lo[2]<-.34 or hi[2]>.34 for lo,hi in body_boxes)
    # Lower head/neck or peripheral lower face; never central front face.
    head_boxes=[b for o in l.objects+other.objects for h in heads for b in contact_boxes(geo(o),geo(h),faceco)]
    head_bad=sum(hi[1]>-.15 and lo[0]<.58 and hi[0]>-.58 for lo,hi in head_boxes)
    central=sum(lo[0]<.40 and hi[0]>-.40 and lo[1]<.62 and hi[1]>-.23 and hi[2]>-.09 for lo,hi in head_boxes)
    other_hits=sum(overlap(actual(o),[actual(z) for z in other.objects]) for o in l.objects)
    accessory_hits=sum(overlap(actual(o),[actual(z) for z in extras]) for o in l.objects)
    # Keep central face obstruction at zero; allow at most the one
    # peripheral ray visible in the explicitly approved reference.
    ctx=prep(a,art);hand=world(ArmSolver(l).hd,l.lower.matrix_world)
    d=(cam.matrix_world.to_3x3()@DOWN).normalized()
    blockers=[ctx[7]]+ctx[6]+[actual(l.upper),world(proximal_data(l),l.lower.matrix_world),hand]+[actual(o) for o in food.objects]
    central_rays=0
    for x in (-.275,0,.275):
        for z in (0,.26,.52):
            origin=c+dx*x+dz*z-d*20
            central_rays+=int(any(g[1].ray_cast(origin,d,19.999)[0] is not None for g in blockers))
    return dict(body_zone_outside_pairs=body_bad,head_zone_outside_pairs=head_bad,central_face_pairs=central,central_face_rays=central_rays,opposite_arm_intersections=other_hits,torso_accessory_intersections=accessory_hits,body_zone_boxes=body_boxes,head_zone_boxes=head_boxes)

def verify(scene,cam,a,art,food,t,yaw,row):
    q=oldcheck(scene,cam,a,art,food,t,yaw,row)
    z=zone_metrics(a,art,cam,food,q);q.update(z);g=q["frame_gates"]
    for k in ("arm_body_no_intersections","head_arm_no_intersections","arm_other_no_intersections","nonexempt_face_clear","elbow_down_out"):g.pop(k)
    g.update(arm_body_localized=q["arm_body_intersections"]+z["torso_accessory_intersections"]<=30 and z["body_zone_outside_pairs"]==0,
        head_arm_localized=q["head_arm_intersections"]<=45 and z["head_zone_outside_pairs"]==0,
        opposite_arm_clear=z["opposite_arm_intersections"]==0,
        central_face_clear=z["central_face_pairs"]==0 and z["central_face_rays"]==0,
        peripheral_face_limit=q["nonexempt_obstruction"]<=1 and (q["nonexempt_obstruction"]==0 or q["contact"]))
    q["geometry_pass"]=all(g.values());return q

def report(rows,attempts):
    q=summary(rows,attempts)
    for k in ("body_zone_outside_pairs","head_zone_outside_pairs","central_face_pairs","central_face_rays","opposite_arm_intersections","torso_accessory_intersections"):
        q["all"]["maxima"][k]=max(r[k] for r in rows)
    q["visual_review_pending"]=True
    return q
def main():
    out=Path(os.environ["OUT"]);out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,___,yaw=setup("eat");food=Food()
    assert not scene.cycles.use_denoising
    src=Path(os.environ["SOURCE"])
    mode=os.environ.get("MODE","geometry")
    times=[i/2 for i in range(119)]
    if mode=="geometry":
        carry=json.loads((src/"carry/geometry_plan.json").read_text())["rows"]
        old=json.loads((src/"bite/search_report.json").read_text())["best_partial"]
        audit=json.loads((src/"approved/bite_search.json").read_text())
        _,cfg,approved=audit["best_rejected_exact"];peak=audit["peak_frame"]-1
        reference=verify(scene,cam,a,art,food,peak,yaw,dict(approved))
        write(out/"approved_reference_check.json",reference)
        # Preserve accepted peak exactly. Same cap coordinates/branch for
        # all other bites; no substitution of a different grip standard.
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
        write(out/"bite_replay.json",{"config":cfg,"missing":missing,"rows":{str(f):verify(scene,cam,a,art,food,f,yaw,dict(row)) for f,row in bites.items()}})
        assert len(bites)==20 and not missing,"Accepted config unreachable at other bite frames"
        attempts=[];best=None
        for twist in (0.,math.pi/2,-math.pi/2,math.pi):
            for window in (10,14,18):
                rows=[verify(scene,cam,a,art,food,t,yaw,plan_row(scene,a,art,t,yaw,carry,bites,window,twist)) for t in times]
                q=report(rows,[])
                score=(q["all"]["failed"],sum(not v for row in rows for v in row["frame_gates"].values()))
                attempts.append(dict(window=window,twist=twist,score=score,failed_samples=q["failed_samples"],maxima=q["all"]["maxima"]))
                if best is None or score<best[0]:best=score,rows
                if not score[0]:break
            if not best[0][0]:break
        q=report(best[1],attempts);write(out/"geometry_plan.json",q)
        print("EAT_STANDARD_VALIDATION",json.dumps({k:v for k,v in q.items() if k not in ("rows","attempts")}),flush=True)
        assert q["geometry_pass"],"Recalibrated 119-sample gates failed; no render"
    else:
        plan=json.loads((out/"geometry_plan.json").read_text());assert plan["geometry_pass"]
        rows=[verify(scene,cam,a,art,food,t,yaw,row) for t,row in zip(times,plan["rows"])]
        q=report(rows,plan["attempts"]);write(out/"replay_geometry.json",q);assert q["geometry_pass"]
        clip=out/"frames";clip.mkdir(exist_ok=True);prev=None;maes=[]
        for t,row in zip(times,rows):
            if t%1:continue
            verify(scene,cam,a,art,food,t,yaw,row);scene.render.filepath=str(clip/f"frame_{int(t)+1:04d}.png");bpy.ops.render.render(write_still=True)
            with Image.open(scene.render.filepath) as im:gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
            if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
            prev=gray
        q["near_static"]={"count":sum(x<.25 for x in maes),"transitions":len(maes),"fraction":sum(x<.25 for x in maes)/len(maes)}
        q["correction_gates"]["performance_motion"]=q["near_static"]["fraction"]<=.40
        write(out/"render_metrics.json",q)
if __name__=="__main__":main()
