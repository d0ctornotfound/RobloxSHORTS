"""Held-food EAT R8. Existing library food prop only; no edits to the library.
Actual food-tip contact, rigid surface-offset grip, geometry first."""
import argparse,sys,math,itertools,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from PIL import Image,ImageFilter,ImageChops,ImageStat
from library_props import build
from render_chapter1_round7 import setup
from chapter1_round2 import pose as old_pose
from chapter1_round4_solver import actual,world,data,nearest,overlap,ArmSolver,restore,matlist,proximal_data
from chapter1_round6_solver import prep,components
from chapter1_round5_solver import flat_contact
from chapter1_drink_path import sliced
from chapter1_articulation import face_grid,DOWN
from character_motion import ramp
from library_camera import metrics

N=60;FPS=30;SCALE=.5
def write(p,obj):p.write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")
class Food:
    def __init__(self):
        self.root=build("food",name="Held library burger",scale=SCALE)
        self.objects=[o for o in self.root.children_recursive if o.type=="MESH"]
        self.scale=self.root.matrix_world.copy();self.parts=[]
        for o in self.objects:
            ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            try:self.parts.append(([ev.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]))
            finally:ev.to_mesh_clear()
        self.vertices=[v for vs,fs in self.parts for v in vs]
        assert self.objects and self.vertices
        # Actual frontmost food vertex; choose one fixed tip, not an
        # artificial point on the mouth or nearest changing cheek point.
        ymin=min(v.y for v in self.vertices);lo=min(v.z for v in self.vertices);hi=max(v.z for v in self.vertices)
        self.tip=min(self.vertices,key=lambda v:(v.y-ymin)+.05*abs(v.x)+.02*abs(v.z-(lo+hi)/2))
    def geometries(self,m):return [world(d,m) for d in self.parts]
    def apply(self,m):
        self.root.matrix_world=m@self.scale;bpy.context.view_layer.update()
    def grip(self,fx,fy):
        # Actual underside ray, not a side support vertex or internal point.
        lo=Vector(tuple(min(v[i] for v in self.vertices) for i in range(3)))
        hi=Vector(tuple(max(v[i] for v in self.vertices) for i in range(3)))
        origin=Vector((lo.x+(hi.x-lo.x)*fx,lo.y+(hi.y-lo.y)*fy,lo.z-.25))
        hits=[]
        for geo in self.geometries(Matrix.Identity(4)):
            q,n,_,d=geo[1].ray_cast(origin,Vector((0,0,1)),1.)
            if q is not None:hits.append((d,q,n))
        if not hits:return None
        _,q,n=min(hits,key=lambda x:x[0])
        if n.z>0:n=-n
        if n.z>-.80:return None
        return q,n.normalized()

def face_counts(cam,a,nonexempt,hand,food,contact):
    c,dx,dz=face_grid(a);direction=(cam.matrix_world.to_3x3()@DOWN).normalized()
    blocked=0;exempt=0
    for x in (-.55,-.275,0,.275,.55):
        for z in (-.52,-.26,0,.26,.52):
            origin=c+dx*x+dz*z-direction*20
            other=any(g[1].ray_cast(origin,direction,19.999)[0] is not None for g in nonexempt)
            held=any(g[1].ray_cast(origin,direction,19.999)[0] is not None for g in [hand]+food)
            mouth=contact and abs(x)<=.30 and abs(z+.365)<=.16
            blocked+=int(other or (held and not mouth));exempt+=int(held and mouth and not other)
    return blocked,exempt

def base(scene,a,art,f,yaw):
    scene.frame_set(f+1);p,_=old_pose(a,art,"eat",f/59,f/30,yaw);a.pose("neutral");bpy.context.view_layer.update()
    return p

def evaluate(scene,cam,a,art,food,f,yaw,config,baseline,prepared=None):
    if prepared is None:p=base(scene,a,art,f,yaw);prepared=(p,prep(a,art),ArmSolver(art.arms[0]))
    p,ctx,arm=prepared;decal,anchor,n,up,side,heads,other,body,extras=ctx
    fx,fy,fu,fv,branch,clear,front,drop,restside,restfront,restheight=config
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    old=baseline[f];oldm=Matrix(old["food_matrix"])
    rot=oldm.to_3x3()
    g=food.grip(fx,fy)
    if g is None:return None,{"frame":f+1,"geometry_pass":False,"reason":"no underside surface"}
    local_grip,local_normal=g;gn=(rot@local_normal).normalized()
    # Preserve the exact previous successful tip transform at every
    # designated bite frame. Widen the below-front approach for the prop.
    delta=old["parameters"]
    final=decal+n*delta[4]-up*delta[5]+side*delta[6]-rot@food.tip
    shoulder=arm.l.joint()
    outward=shoulder-a.root.matrix_world.translation;outward.z=0
    outward=outward.normalized()
    rest_grip=shoulder+outward*restside+n*restfront-up*restheight
    rest=rest_grip-rot@local_grip
    waypoint=final+n*front-up*drop
    if w<.55:pos=rest.lerp(waypoint,ramp(w,0,.55))
    else:pos=waypoint.lerp(final,ramp(w,.55,1))
    m=oldm if contact else Matrix.Translation(pos)@rot.to_4x4()
    grip=m@local_grip;tip=m@food.tip
    # Hard exact end-cap search, no general IK fallback.
    sol=flat_contact(arm,grip,gn,yaw,(2,-1,fu,fv,branch,clear,Vector((0,0,0))))
    la,ng=components(tip,decal,n)
    if sol is None:return None,{"frame":f+1,"geometry_pass":False,"reason":"no exact end-cap solution","lateral_alignment":la,"normal_gap":ng,"contact":contact}
    lm=Matrix(sol["matrices"][1]);cap=(lm.to_3x3()@Vector((0,0,-1))).normalized().dot(-gn)
    if cap<.90:return None,{"frame":f+1,"geometry_pass":False,"reason":"end-cap orientation","cap_alignment":cap,"contact":contact}
    geoms=[sol["upper"],sol["lower"]];fg=food.geometries(m)
    headarm=sum(overlap(g,heads) for g in geoms+other);headfood=sum(overlap(g,heads) for g in fg)
    foodarm=sum(overlap(g,geoms+other) for g in fg);foodbody=sum(overlap(g,[body]+extras) for g in fg)
    ab=overlap(world(sliced(arm.l.upper,-.25*arm.l.a),Matrix(sol["matrices"][0])),[body])+overlap(sol["lower"],[body])
    ao=sum(overlap(g,other+extras) for g in geoms)
    proximal=world(proximal_data(arm.l),lm)
    face,exempt=face_counts(cam,a,[body]+other+[sol["upper"],proximal],sol["hand"],fg,contact)
    gp=sol["gap"];support=sol["surface_clearance"]
    valid=headarm==headfood==foodarm==foodbody==ab==ao==face==0 and gp<=.02 and support>=-.001 and (not contact or (la<=.03 and abs(ng)<=.06))
    score=(int(not valid),headarm+headfood+foodarm+foodbody+ab+ao,face,max(0,gp-.02)+max(0,-support-.001),max(0,la-.03)+max(0,abs(ng)-.06) if contact else 0)
    return score,{"frame":f+1,"contact":contact,"mouth_action":raw,"geometry_pass":valid,
         "arm_matrices":sol["matrices"],"food_matrix":matlist(m),"food_tip":list(tip),"grip_anchor":list(grip),"grip_normal":list(gn),
         "lateral_alignment":la,"normal_gap":ng,"head_arm_intersections":headarm,"head_food_intersections":headfood,
         "food_arm_intersections":foodarm,"food_body_intersections":foodbody,"arm_body_intersections":ab,"arm_other_intersections":ao,
         "nonexempt_obstruction":face,"mouth_exempt_rays":exempt,"cap_alignment":cap,"endcap_exact_solution":True,
         "grip_gap":gp,"support_clearance":support,"measured_half_thickness":sol["half_thickness"],"parameters":list(config)}
def verify(scene,cam,a,art,food,f,yaw,row):
    p=base(scene,a,art,f,yaw);l=art.arms[0];restore(l,row["arm_matrices"]);m=Matrix(row["food_matrix"]);food.apply(m)
    decal,anchor,n,up,side,heads,other,body,extras=prep(a,art)
    fg=[actual(o) for o in food.objects]
    arm=ArmSolver(l);hand=world(arm.hd,l.lower.matrix_world)
    # Recover actual food tip under the stored root transform and compute
    # fresh evaluated meshes and contact distances, not candidate scores.
    tip=(food.root.matrix_world@food.scale.inverted())@food.tip
    lat,normal=components(tip,decal,n);gq=Vector(row["grip_anchor"]);gn=Vector(row["grip_normal"])
    armg=[actual(o) for limb in art.arms for o in limb.objects]
    ha=sum(overlap(g,heads) for g in armg);hf=sum(overlap(g,heads) for g in fg)
    fa=sum(overlap(g,armg) for g in fg);fb=sum(overlap(g,[body]+extras) for g in fg)
    contact=p["mouth_action"]>=.90
    face,ex=face_counts(cam,a,[body]+other+[actual(l.upper),world(proximal_data(l),l.lower.matrix_world)],hand,fg,contact)
    gap=nearest(hand,gq)[2];support=min((v-gq).dot(gn) for v in hand[0])
    cap=(l.lower.matrix_world.to_3x3()@Vector((0,0,-1))).normalized().dot(-gn)
    ab=overlap(world(sliced(l.upper,-.25*l.a),l.upper.matrix_world),[body])+overlap(actual(l.lower),[body])
    ao=sum(overlap(g,other+extras) for g in (actual(l.upper),actual(l.lower)))
    lm=art.length_metrics();bounds=metrics(scene,cam,[a]);safe=all(v["body_safe"] and v["head_safe"] for v in bounds)
    gates={"head_arm_no_intersections":ha==0,"head_food_no_intersections":hf==0,"food_arm_no_intersections":fa==0,
        "food_body_no_intersections":fb==0,"arm_body_no_intersections":ab==0,"arm_other_no_intersections":ao==0,
        "exact_endcap_support":row["endcap_exact_solution"] and cap>=.90,"nonexempt_face_clear":face==0,"grip_contact":gap<=.02,"support_clearance":support>=-.001,
        "food_tip_alignment":not contact or lat<=.03,"food_tip_normal_gap":not contact or abs(normal)<=.06,
        "segment_length":lm["max_segment_length_change"]<=.02,"joint_continuity":lm["max_joint_gap"]<=.002,"framing":safe}
    row.update(lm,frame=f+1,contact=contact,food_tip=list(tip),lateral_alignment=lat,normal_gap=normal,head_arm_intersections=ha,
        head_food_intersections=hf,food_arm_intersections=fa,food_body_intersections=fb,nonexempt_obstruction=face,mouth_exempt_rays=ex,
        grip_gap=gap,support_clearance=support,cap_alignment=cap,arm_body_intersections=ab,arm_other_intersections=ao,frame_gates=gates,geometry_pass=all(gates.values()))
    return row

def search(scene,cam,a,art,food,yaw,baseline,out):
    f=15;p=base(scene,a,art,f,yaw);prepared=(p,prep(a,art),ArmSolver(art.arms[0]))
    ranked=[];tested=0;rejected=0;peak_clean=0
    for fx,fy,fu,fv,branch,clear in itertools.product((.3,.5,.7),(.3,.5,.7),(.08,.3,.7,.92),(.08,.3,.7,.92),(-1,1),(.003,.008)):
        cfg=(fx,fy,fu,fv,branch,clear,.28,.38,.20,.35,.32)
        sc,row=evaluate(scene,cam,a,art,food,f,yaw,cfg,baseline,prepared);tested+=1
        if sc is None:rejected+=1;continue
        peak_clean+=int(row["geometry_pass"]);ranked.append((sc,cfg))
    ranked.sort();attempts=[{"peak_tested":tested,"hard_constraint_rejections":rejected,"peak_solved":len(ranked),"peak_clean":peak_clean,"best_peak":ranked[:5]}]
    write(out/"search_report.json",{"geometry_pass":False,"attempts":attempts})
    print("FOOD9_PEAK",json.dumps(attempts[0]),flush=True)
    best=None;best_partial=None
    for _,cfg in ranked[:32]:
        for front,drop,rs,rf,rh in ((.28,.38,.20,.35,.32),(.36,.42,.28,.42,.30),(.25,.30,.15,.34,.38),(.40,.48,.28,.38,.25)):
            config=cfg[:6]+(front,drop,rs,rf,rh)
            rows=[evaluate(scene,cam,a,art,food,f,yaw,config,baseline)[1] for f in range(N)]
            missing=[r["frame"] for r in rows if "arm_matrices" not in r]
            bad=sum(not r["geometry_pass"] for r in rows)
            sc=(bad,len(missing),sum(r.get("head_arm_intersections",0)+r.get("head_food_intersections",0)+r.get("food_arm_intersections",0)+r.get("food_body_intersections",0)+r.get("arm_body_intersections",0) for r in rows))
            attempts.append({"parameters":config,"score":list(sc),"unreachable_frames":missing})
            if best_partial is None or sc<best_partial[0]:best_partial=(sc,rows)
            if not missing and (best is None or sc<best[0]):best=(sc,rows)
            if bad==0:break
        if best is not None and best[0][0]==0:break
    write(out/"search_report.json",{"geometry_pass":False,"attempts":attempts,"best_partial":best_partial[1] if best_partial else []})
    if best is None:
        raise RuntimeError("No all-frame exact end-cap solution; no render; see search_report.json")
    return best[1],attempts

def report(rows,attempts):
    contacts=[r for r in rows if r["contact"]]
    gates={k:all(r["frame_gates"][k] for r in rows) for k in rows[0]["frame_gates"]};gates["contact_frames_present"]=bool(contacts)
    return {"action":"eat_held_food","prop":"library_props.food (burger)","prop_scale":SCALE,"frames":len(rows),"fps":FPS,
      "geometry_pass":len(rows)==N and all(gates.values()),"correction_gates":gates,
      "contact_frames":[r["frame"] for r in contacts],
      "failed_frames":{k:[r["frame"] for r in rows if not r["frame_gates"].get(k,True)] for k,v in gates.items() if not v},
      "max_lateral_alignment":max(r["lateral_alignment"] for r in contacts),
      "max_absolute_normal_gap":max(abs(r["normal_gap"]) for r in contacts),
      "maxima":{k:max(r[k] for r in rows) for k in ("head_arm_intersections","head_food_intersections","food_arm_intersections","food_body_intersections","nonexempt_obstruction","grip_gap","max_segment_length_change","max_joint_gap")},
      "min_support_clearance":min(r["support_clearance"] for r in rows),"min_cap_alignment":min(r["cap_alignment"] for r in rows),
      "max_arm_body_intersections":max(r["arm_body_intersections"] for r in rows),"max_arm_other_intersections":max(r["arm_other_intersections"] for r in rows),"rows":rows,"search_attempts":attempts}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True)
    group=ap.add_mutually_exclusive_group(required=True);group.add_argument("--geometry-only",action="store_true");group.add_argument("--plan");ap.add_argument("--baseline")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,___,yaw=setup("eat");food=Food()
    if args.geometry_only:
        assert args.baseline,"Round8 food placement required"
        baseline=json.loads(Path(args.baseline).read_text());assert baseline["action"]=="eat_held_food" and len(baseline["rows"])==N and baseline["correction_gates"]["food_tip_alignment"] and baseline["correction_gates"]["food_tip_normal_gap"] and baseline["correction_gates"]["head_food_no_intersections"]
        rows,attempts=search(scene,cam,a,art,food,yaw,baseline["rows"],out)
    else:
        p=json.loads(Path(args.plan).read_text());assert p["geometry_pass"] and p["action"]=="eat_held_food" and len(p["rows"])==N
        rows=p["rows"];attempts=p["search_attempts"]
    rows=[verify(scene,cam,a,art,food,f,yaw,row) for f,row in enumerate(rows)]
    q=report(rows,attempts);write(out/("geometry_plan.json" if args.geometry_only else "replay_geometry.json"),q)
    print("FOOD_GEOMETRY_SUMMARY",json.dumps({k:v for k,v in q.items() if k not in ("rows","search_attempts")}),flush=True)
    assert q["geometry_pass"],"GEOMETRY PRECHECK FAILED — NO RENDER"
    if args.geometry_only:return
    clip=out/"00_lead_eat_food";clip.mkdir(exist_ok=True);prev=None;maes=[]
    for f,row in enumerate(rows):
        verify(scene,cam,a,art,food,f,yaw,row)
        path=clip/f"frame_{f+1:04d}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);assert path.is_file()
        with Image.open(path) as im:gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
        if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
        prev=gray
    count=sum(x<.25 for x in maes);q["near_static"]={"count":count,"transitions":len(maes),"fraction":count/len(maes)}
    q["correction_gates"]["performance_motion"]=count/len(maes)<=.40;q["visual_review_pending"]=True
    write(clip/"metrics.json",q);print("FOOD_RENDER_SUMMARY",q["correction_gates"],flush=True)
if __name__=="__main__":main()
