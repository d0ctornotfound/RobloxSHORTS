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
    def grip(self,g):
        normal=Vector((0,math.cos(g),-math.sin(g))).normalized()
        v=max(self.vertices,key=lambda x:x.dot(normal))
        return v,normal

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

def evaluate(scene,cam,a,art,food,f,yaw,config,prepared=None):
    if prepared is None:p=base(scene,a,art,f,yaw);prepared=(p,prep(a,art),ArmSolver(art.arms[0]))
    p,ctx,arm=prepared;decal,anchor,n,up,side,heads,other,body,extras=ctx
    g,angle,depth,roll,clear,lower,lat,way,drop=config
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    x=n.cross(up).normalized();y=n;z=x.cross(y).normalized()
    rot=Matrix((x,y,z)).transposed()
    local_grip,local_normal=food.grip(g);gn=(rot@local_normal).normalized()
    final=decal+n*clear-up*lower+side*lat-rot@food.tip
    # Retain established below-front route, two bite dips, and reverse
    # withdrawal. Start with prop supported by the actual relaxed hand.
    lm=arm.l.lower.matrix_world;center=lm@arm.local_center
    thickness=max((center-lm@v).dot(gn) for v in arm.hd[0])
    rest=center-gn*(thickness+.006)-rot@local_grip
    waypoint=final+n*way-up*drop
    if w<.55:pos=rest.lerp(waypoint,ramp(w,0,.55))
    else:pos=waypoint.lerp(final,ramp(w,.55,1))
    m=Matrix.Translation(pos)@rot.to_4x4()
    grip=m@local_grip;tip=m@food.tip
    pole=side*math.cos(angle)+up*math.sin(angle)+n*depth
    sol=arm.solve(grip,gn,pole,yaw,roll,1.,.006)
    geoms=[sol["upper"],sol["lower"]];fg=food.geometries(m)
    la,ng=components(tip,decal,n)
    headarm=sum(overlap(g,heads) for g in geoms+other)
    headfood=sum(overlap(g,heads) for g in fg)
    foodarm=sum(overlap(g,geoms+other) for g in fg)
    foodbody=sum(overlap(g,[body]+extras) for g in fg)
    proximal=world(proximal_data(arm.l),Matrix(sol["matrices"][1]))
    face,exempt=face_counts(cam,a,[body]+other+[sol["upper"],proximal],sol["hand"],fg,contact)
    gp=sol["gap"];support=sol["surface_clearance"]
    valid=headarm==headfood==foodarm==foodbody==face==0 and gp<=.02 and support>=-.001 and (not contact or (la<=.03 and abs(ng)<=.06))
    score=(int(not valid),headarm+headfood+foodarm+foodbody,face,max(0,gp-.02)+max(0,-support-.001),max(0,la-.03)+max(0,abs(ng)-.06) if contact else 0)
    return score,{"frame":f+1,"contact":contact,"mouth_action":raw,"geometry_pass":valid,
         "arm_matrices":sol["matrices"],"food_matrix":matlist(m),"food_tip":list(tip),"grip_anchor":list(grip),"grip_normal":list(gn),
         "lateral_alignment":la,"normal_gap":ng,"head_arm_intersections":headarm,"head_food_intersections":headfood,
         "food_arm_intersections":foodarm,"food_body_intersections":foodbody,"nonexempt_obstruction":face,"mouth_exempt_rays":exempt,
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
    lm=art.length_metrics();bounds=metrics(scene,cam,[a]);safe=all(v["body_safe"] and v["head_safe"] for v in bounds)
    gates={"head_arm_no_intersections":ha==0,"head_food_no_intersections":hf==0,"food_arm_no_intersections":fa==0,
        "food_body_no_intersections":fb==0,"nonexempt_face_clear":face==0,"grip_contact":gap<=.02,"support_clearance":support>=-.001,
        "food_tip_alignment":not contact or lat<=.03,"food_tip_normal_gap":not contact or abs(normal)<=.06,
        "segment_length":lm["max_segment_length_change"]<=.02,"joint_continuity":lm["max_joint_gap"]<=.002,"framing":safe}
    row.update(lm,frame=f+1,contact=contact,food_tip=list(tip),lateral_alignment=lat,normal_gap=normal,head_arm_intersections=ha,
        head_food_intersections=hf,food_arm_intersections=fa,food_body_intersections=fb,nonexempt_obstruction=face,mouth_exempt_rays=ex,
        grip_gap=gap,support_clearance=support,frame_gates=gates,geometry_pass=all(gates.values()))
    return row

def search(scene,cam,a,art,food,yaw):
    f=15;p=base(scene,a,art,f,yaw);prepared=(p,prep(a,art),ArmSolver(art.arms[0]))
    ranked=[];tested=0;peak_clean=0
    for g,angle,depth,roll,clear,lower,lat in itertools.product(map(math.radians,(20,50,80)),[i*math.tau/12 for i in range(12)],(.2,.8),(0,math.pi/2,-math.pi/2),(.015,.035,.055),(0,.015),(-.015,0,.015)):
        cfg=(g,angle,depth,roll,clear,lower,lat,.20,.30)
        sc,row=evaluate(scene,cam,a,art,food,f,yaw,cfg,prepared);tested+=1;peak_clean+=int(row["geometry_pass"])
        ranked.append((sc,cfg))
    ranked.sort();attempts=[{"peak_tested":tested,"peak_clean":peak_clean,"best_peak":ranked[:5]}]
    print("FOOD_PEAK",json.dumps(attempts[0]),flush=True)
    best=None
    for _,cfg in ranked[:24]:
        for way,drop in ((.20,.30),(.30,.38),(.13,.25)):
            config=cfg[:7]+(way,drop)
            rows=[evaluate(scene,cam,a,art,food,f,yaw,config)[1] for f in range(N)]
            contacts=[r for r in rows if r["contact"]]
            sc=(sum(not r["geometry_pass"] for r in rows),max(r["head_arm_intersections"]+r["head_food_intersections"]+r["food_arm_intersections"]+r["food_body_intersections"] for r in rows),
                max(r["nonexempt_obstruction"] for r in rows),max(r["grip_gap"] for r in rows))
            attempts.append({"parameters":config,"score":list(sc)})
            if best is None or sc<best[0]:best=(sc,rows)
            if sc[0]==0:break
        if best[0][0]==0:break
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
      "min_support_clearance":min(r["support_clearance"] for r in rows),"rows":rows,"search_attempts":attempts}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True)
    group=ap.add_mutually_exclusive_group(required=True);group.add_argument("--geometry-only",action="store_true");group.add_argument("--plan")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,___,yaw=setup("eat");food=Food()
    if args.geometry_only:rows,attempts=search(scene,cam,a,art,food,yaw)
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
