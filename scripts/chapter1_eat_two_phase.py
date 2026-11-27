"""Two-phase held-food candidate; immutable R6 carry and R9 bite endpoints.
Validate all 119 integer/half-frame samples before rendering."""
import argparse,sys,math,json
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from PIL import Image,ImageFilter,ImageChops,ImageStat
import chapter1_eat_food_r9 as prior
from chapter1_eat_food_r9 import Food,setup,write,restore,matlist,N
from chapter1_round2 import pose as old_pose
from character_motion import ramp

def base(scene,a,art,f,yaw):
    i=int(f);scene.frame_set(i+1,subframe=f-i)
    p,_=old_pose(a,art,"eat",f/59,f/30,yaw);a.pose("neutral");bpy.context.view_layer.update()
    return p
# The same evaluated mesh verification as R9, with fractional time support.
prior.base=base

def blendrot(m,n,t):
    return m.to_quaternion().slerp(n.to_quaternion(),t).to_matrix().to_4x4()
def interp(m,n,t):
    out=blendrot(m,n,t);out.translation=m.translation.lerp(n.translation,t);return out

def arm_at(rows,t):
    i=int(t);j=min(i+1,len(rows)-1);w=t-i
    return [interp(Matrix(x),Matrix(y),w) for x,y in zip(rows[i]["arm_matrices"],rows[j]["arm_matrices"])]

def bite_at(bites,t):
    # Interpolate within bite clusters only. Otherwise use nearest exact
    # bite pose as blend endpoint. No unconstrained inverse kinematics.
    keys=sorted(bites);near=min(keys,key=lambda x:abs(t-x))
    i=int(t);j=i+1
    if i in bites and j in bites and t!=i:
        a,b=bites[i],bites[j];w=t-i
        mats=[interp(Matrix(x),Matrix(y),w) for x,y in zip(a["arm_matrices"],b["arm_matrices"])]
        fm=interp(Matrix(a["food_matrix"]),Matrix(b["food_matrix"]),w)
        gq=Vector(a["grip_anchor"]).lerp(Vector(b["grip_anchor"]),w)
        gn=Vector(a["grip_normal"]).lerp(Vector(b["grip_normal"]),w).normalized()
        return mats,fm,gq,gn,0.
    row=bites[near]
    return [Matrix(m) for m in row["arm_matrices"]],Matrix(row["food_matrix"]),Vector(row["grip_anchor"]),Vector(row["grip_normal"]),abs(t-near)

def plan_row(scene,a,art,t,yaw,carry,bites,window,twist):
    p=base(scene,a,art,t,yaw);limb=art.arms[0]
    cm=arm_at(carry,t);bm,fm,gq,gn,dist=bite_at(bites,t)
    # R9 contact positions are immutable, including their existing failures.
    if t in bites:
        row=dict(bites[t]);row.update(sample=t+1,phase="bite",blend=1.,fixed_bite=True)
        return row
    weight=1-ramp(dist,0,window)
    um=blendrot(cm[0],bm[0],weight);lm=blendrot(cm[1],bm[1],weight)
    # Reconstruct the exact rigid chain, rather than lerping independent
    # world positions, to preserve shoulder attachment and segment lengths.
    um.translation=limb.joint()
    lm.translation=um@Vector((0,0,-limb.a))
    # Food is rigidly attached at the bite's measured end-cap offset,
    # with an optional carry twist around the grip normal, fading to zero.
    rel=bm[1].inverted()@fm
    local_gq=bm[1].inverted()@gq
    local_gn=(bm[1].to_3x3().inverted()@gn).normalized()
    rr=Matrix.Rotation(twist*(1-weight),4,local_gn)
    rel=Matrix.Translation(local_gq)@rr@Matrix.Translation(-local_gq)@rel
    foodm=lm@rel
    grip=lm@local_gq;normal=(lm.to_3x3()@local_gn).normalized()
    return {"sample":t+1,"phase":"carry" if weight<1e-8 else "bite" if weight>=1-1e-8 else "blend",
            "blend":weight,"fixed_bite":False,"arm_matrices":[matlist(um),matlist(lm)],
            "food_matrix":matlist(foodm),"grip_anchor":list(grip),"grip_normal":list(normal),
            "endcap_exact_solution":True,"mouth_action":p["mouth_action"]}

def check(scene,cam,a,art,food,t,yaw,row):
    row=prior.verify(scene,cam,a,art,food,t,yaw,dict(row))
    row["sample"]=t+1;row["half_frame"]=t%1!=0
    return row

def summary(rows,attempts):
    gates={k:all(r["frame_gates"][k] for r in rows) for k in rows[0]["frame_gates"]}
    contact=[r for r in rows if r["contact"]]
    fixed=[r for r in rows if r["fixed_bite"]]
    fields=("head_arm_intersections","head_food_intersections","food_arm_intersections","food_body_intersections","arm_body_intersections","arm_other_intersections","nonexempt_obstruction","grip_gap","max_segment_length_change","max_joint_gap")
    def stats(rs):
        return {"samples":len(rs),"failed":sum(not r["geometry_pass"] for r in rs),
                "maxima":{k:max((r[k] for r in rs),default=None) for k in fields},
                "min_cap_alignment":min((r["cap_alignment"] for r in rs),default=None),
                "min_support_clearance":min((r["support_clearance"] for r in rs),default=None)}
    return {"action":"eat_two_phase","frames":60,"half_frames":59,"samples":len(rows),"geometry_pass":len(rows)==119 and all(gates.values()),
      "correction_gates":gates,"failed_samples":{k:[r["sample"] for r in rows if not r["frame_gates"][k]] for k in gates if not gates[k]},
      "all":stats(rows),"fixed_bite":stats(fixed),"phases":{ph:stats([r for r in rows if r["phase"]==ph]) for ph in ("carry","blend","bite")},
      "max_lateral_alignment":max(r["lateral_alignment"] for r in contact),"max_absolute_normal_gap":max(abs(r["normal_gap"]) for r in contact),
      "attempts":attempts,"rows":rows}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True)
    g=ap.add_mutually_exclusive_group(required=True);g.add_argument("--geometry-only",action="store_true");g.add_argument("--plan")
    ap.add_argument("--carry");ap.add_argument("--bite")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,___,yaw=setup("eat");food=Food()
    times=[i/2 for i in range(119)]
    if args.geometry_only:
        c=json.loads(Path(args.carry).read_text());b=json.loads(Path(args.bite).read_text())
        carry=c["rows"];assert len(carry)==60 and c["max_head_surface_intersections"]==0 and c["face_blocked_samples_max"]==0
        bites={r["frame"]-1:r for r in b["best_partial"] if r.get("contact") and "arm_matrices" in r}
        assert len(bites)==20 and all(r["cap_alignment"]>=.90 for r in bites.values())
        attempts=[];best=None
        # Lengthen the window BEFORE changing carry twist.
        for twist in (0.,math.pi/2,-math.pi/2,math.pi):
            for window in (10,14,18):
                rows=[check(scene,cam,a,art,food,t,yaw,plan_row(scene,a,art,t,yaw,carry,bites,window,twist)) for t in times]
                q=summary(rows,[])
                score=(q["all"]["failed"],sum(r["head_arm_intersections"]+r["arm_body_intersections"]+r["head_food_intersections"]+r["food_arm_intersections"]+r["food_body_intersections"]+r["arm_other_intersections"] for r in rows))
                attempts.append({"window_frames":window,"carry_twist_degrees":math.degrees(twist),"score":score,"fixed_bite":q["fixed_bite"],"phases":q["phases"]})
                print("EAT_TWO_PHASE_ATTEMPT",json.dumps(attempts[-1]),flush=True)
                if best is None or score<best[0]:best=(score,rows)
                if q["geometry_pass"]:break
            if best[0][0]==0:break
        rows=best[1]
    else:
        plan=json.loads(Path(args.plan).read_text());assert plan["action"]=="eat_two_phase" and plan["geometry_pass"] and len(plan["rows"])==119
        attempts=plan["attempts"];rows=[check(scene,cam,a,art,food,t,yaw,row) for t,row in zip(times,plan["rows"])]
    q=summary(rows,attempts);write(out/("geometry_plan.json" if args.geometry_only else "replay_geometry.json"),q)
    print("EAT_TWO_PHASE_SUMMARY",json.dumps({k:v for k,v in q.items() if k not in ("rows","attempts")}),flush=True)
    assert q["geometry_pass"],"119-sample geometry precheck failed — no render"
    if args.geometry_only:return
    clip=out/"00_lead_eat_food";clip.mkdir(exist_ok=True);prev=None;maes=[]
    for t,row in zip(times,rows):
        if t%1:continue
        check(scene,cam,a,art,food,t,yaw,row);path=clip/f"frame_{int(t)+1:04d}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        with Image.open(path) as im:gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
        if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
        prev=gray
    q["near_static"]={"count":sum(v<.25 for v in maes),"transitions":len(maes),"fraction":sum(v<.25 for v in maes)/len(maes)}
    q["correction_gates"]["performance_motion"]=q["near_static"]["fraction"]<=.40
    q["visual_review_pending"]=True;write(clip/"metrics.json",q)
if __name__=="__main__":main()
