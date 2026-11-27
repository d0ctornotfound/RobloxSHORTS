"""Drink-only numerical path search. No rendering; no changes to frozen motions.
One fixed path and IK branch across the complete cycle. Check 60 frames plus
half-frame samples for a stronger (discrete, not continuous proof) path test."""
import sys,math,json,itertools,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from chapter1_round4_solver import (actual,data,world,nearest,overlap,cross,rays,
    mouth_anchor,ArmSolver,matlist,clip,restore,rim_distance)
from render_chapter1_round4 import setup
from chapter1_round2 import pose as old_pose
from character_motion import ramp
from library_camera import metrics

N=60;FPS=30
def sliced(ob,z):
    verts=[];faces=[]
    for p in ob.data.polygons:
        poly=[(ob.data.vertices[i].co.copy(),Vector((0,0))) for i in p.vertices]
        part=clip(poly,z,False)
        if len(part)<3:continue
        faces.append(tuple(range(len(verts),len(verts)+len(part))))
        verts.extend(v for v,t in part)
    return verts,faces

def prepare(scene,actor,art,cam,cup,yaw,f):
    scene.frame_set(int(f)+1);p,_=old_pose(actor,art,"drink",f/(N-1),f/FPS,yaw);actor.pose("neutral")
    bpy.context.view_layer.update()
    decal,anchor,n,up,side,head=mouth_anchor(actor)
    other=[actual(o) for o in art.arms[1].objects]
    headparts=[head]+[actual(o) for o in actor.accessories if o!=actor.face and o.type=="MESH" and "head" in o.name.lower()]
    body=actual(actor.body)
    accessories=[actual(o) for o in actor.accessories if o.type=="MESH" and o!=actor.face and "head" not in o.name.lower()]
    return p,decal,anchor,n,up,side,headparts,other,body,accessories

def evaluate(scene,cam,actor,art,cup,yaw,f,params,prepared=None,details=False):
    p,decal,anchor,n,up,side,heads,other,body,accessories=prepared or prepare(scene,actor,art,cam,cup,yaw,f)
    az,tilt,ri,clear,grip,gripz,poleang,poledepth,roll,front,drop,lateral,gripclear=params
    raw=p["mouth_action"];w=min(1.,raw/.90);contact=raw>=.90
    z=Vector((0,0,1));hn=n-z*n.dot(z);hn.normalize();hs=z.cross(hn)
    tang=hn*math.cos(az)+hs*math.sin(az);axis=z*math.cos(tilt)+tang*math.sin(tilt)
    q=z.rotation_difference(axis);rot=q.to_matrix()
    # Select a real rim edge, not a nominal cylinder center. Choose near-top
    # candidates by rank, and keep all non-rim vertices below mouth at sip.
    ring=[rot@cup.data.vertices[32+i].co for i in range(32)]
    # A physically plausible lip edge is selected by its height and inward
    # projection; search the top edge and neighbouring ring vertices.
    order=sorted(range(32),key=lambda i:(-ring[i].z,ring[i].dot(n),i))
    rv=ring[order[int(ri)]]
    final=anchor+n*clear-rv
    limb=art.arms[0];arm=ArmSolver(limb)
    rest=limb.transform()@limb.end+hn*.18+Vector((0,0,.08))
    waypoint=final+hn*front-z*drop+hs*lateral
    if w<.55:
        b=ramp(w,0,.55);pos=rest.lerp(waypoint,b);fraction=.55*b
    else:
        b=ramp(w,.55,1.);pos=waypoint.lerp(final,b);fraction=.55+.45*b
    cm=Matrix.Translation(pos)@z.rotation_difference(z).slerp(q,fraction).to_matrix().to_4x4()
    cg=world(data(cup),cm);rim=rim_distance(cup,cm,decal)
    below=max(v.z-decal.z for i,v in enumerate(cg[0]) if not 32<=i<96)
    cuphead=overlap(cg,heads);cupbody=overlap(cg,[body]+accessories)
    cupface=rays(cam,actor,[cg])
    # Prune impossible contact cup poses before expensive arm solving.
    if not details and (cuphead or cupbody or cupface or (contact and (rim>.02 or below>.002))):
        return (1,cuphead+cupbody+cupface,max(0,rim-.02) if contact else 0,max(0,below-.002) if contact else 0),None
    radial=Vector((math.cos(grip),math.sin(grip),0));gn=(cm.to_3x3()@radial).normalized()
    origin=cm@Vector((0,0,gripz));gq,_,_,_=cg[1].ray_cast(origin+gn*.3,-gn,.5)
    if gq is None:gq,_,_=nearest(cg,origin+gn*.08)
    pole=hs*math.cos(poleang)+z*math.sin(poleang)+hn*poledepth
    sol=arm.solve(gq,gn,pole,yaw,roll,1.,gripclear)
    um,lm=[Matrix(m) for m in sol["matrices"]]
    upper,lower=sol["upper"],sol["lower"]
    # The native shoulder attachment itself is intentionally adjacent to
    # torso. Check the upper arm beyond the proximal quarter against torso;
    # ALL of both arm segments against the head, cup, other arm/accessories.
    upper_distal=world(sliced(limb.upper,-.25*limb.a),um)
    upperhead=overlap(upper,heads);lowerhead=overlap(lower,heads)
    headhits=upperhead+lowerhead+cuphead+sum(overlap(g,heads) for g in other)
    cup_arm=overlap(cg,[upper,lower]+other)
    arm_body=overlap(upper_distal,[body])+overlap(lower,[body])
    arm_other=overlap(upper,other+accessories)+overlap(lower,other+accessories)
    face=rays(cam,actor,[body]+other+[upper,lower,cg])
    gripgap=sol["gap"]
    valid=(headhits==0 and cup_arm==0 and cupbody==0 and arm_body==0 and arm_other==0 and face==0
           and gripgap<=.02 and (not contact or (rim<=.02 and below<=.002)))
    score=(int(not valid),headhits+cup_arm+cupbody+arm_body+arm_other+face,
           max(0,rim-.02) if contact else 0,max(0,gripgap-.02)+max(0,below-.002) if contact else max(0,gripgap-.02))
    row={"frame":f+1,"contact":contact,"mouth_action":raw,"rim_gap":rim,"grip_gap":gripgap,
         "head_intersections":headhits,"upper_head":upperhead,"lower_head":lowerhead,"cup_head":cuphead,
         "cup_arm_intersections":cup_arm,"cup_body_intersections":cupbody,"arm_body_intersections":arm_body,
         "arm_other_intersections":arm_other,"face_obstruction":face,"cup_face":cupface,"cup_body_above_mouth":below,
         "geometry_pass":valid,"arm_matrices":sol["matrices"],"cup_matrix":matlist(cm),"grip_anchor":list(gq)}
    if details:
        restore(limb,sol["matrices"]);cup.matrix_world=cm;bpy.context.view_layer.update()
        # Independently measure evaluated objects (not just optimization proxies).
        ag=[actual(o) for l in art.arms for o in l.objects];cg=actual(cup)
        eh=sum(overlap(g,heads) for g in ag)+overlap(cg,heads)
        ec=overlap(cg,ag);ef=rays(cam,actor,[body]+ag+[cg])
        lmet=art.length_metrics();fr=all(v["body_safe"] and v["head_safe"] for v in metrics(scene,cam,[actor]))
        row.update(lmet,framing_safe=fr,evaluated_head_intersections=eh,evaluated_cup_arm_intersections=ec,evaluated_face_obstruction=ef)
        row["geometry_pass"]=valid and eh==ec==ef==0 and fr and lmet["max_segment_length_change"]<=.02 and lmet["max_joint_gap"]<=.002
    return score,row
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True);args=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,cup,yaw=setup("drink")
    # Existing shot remains fixed. Search actual sip geometry first, then
    # the trajectory; a clean endpoint is necessary but not sufficient.
    prep=prepare(scene,a,art,cam,cup,yaw,29)
    base=[];tested=0;cup_clean=0;peak_clean=0;best_failed=None
    # First rank cups independent of arm branch. This avoids repeating
    # thousands of doomed arm configurations for a penetrating cup.
    p,decal,anchor,n,up,side,heads,other,body,accessories=prep
    z=Vector((0,0,1));hn=n-z*n.dot(z);hn.normalize();hs=z.cross(hn)
    cup_options=[]
    for az,tilt,ri,clear in itertools.product([i*math.tau/12 for i in range(12)],map(math.radians,(25,30,35)),(0,1,3,5),(.003,.008,.014)):
        axis=z*math.cos(tilt)+(hn*math.cos(az)+hs*math.sin(az))*math.sin(tilt)
        rot=z.rotation_difference(axis).to_matrix();ring=[rot@cup.data.vertices[32+i].co for i in range(32)]
        order=sorted(range(32),key=lambda i:(-ring[i].z,ring[i].dot(n),i))
        cm=Matrix.Translation(anchor+n*clear-ring[order[ri]])@rot.to_4x4();cg=world(data(cup),cm)
        h=overlap(cg,heads);b=overlap(cg,[body]+accessories);face=rays(cam,a,[cg])
        rim=rim_distance(cup,cm,decal);below=max(v.z-decal.z for i,v in enumerate(cg[0]) if not 32<=i<96)
        score=(h+b+face,max(0,rim-.02),max(0,below-.002),rim)
        cup_options.append((score,(az,tilt,ri,clear)))
    cup_options.sort()
    clean=[x for x in cup_options if x[0][:3]==(0,0,0)];cup_clean=len(clean)
    # If no cup pose passes, still diagnose the best few; never mark valid.
    selected=(clean[:24] if clean else cup_options[:8])
    for _,cp in selected:
        for grip,gz,pa,pd,roll,gc in itertools.product([i*math.tau/8 for i in range(8)],(-.065,-.025,.015),[i*math.tau/8 for i in range(8)],(.25,.85),(0,math.pi/2,-math.pi/2),(.004,.010)):
            params=cp+(grip,gz,pa,pd,roll,.24,.36,0,gc)
            score,row=evaluate(scene,cam,a,art,cup,yaw,29,params,prep)
            tested+=1
            if row is None:continue
            if best_failed is None or score<best_failed[0]:best_failed=(score,params)
            if row["geometry_pass"]:
                peak_clean+=1;base.append(params)
                # Retain multiple complete-contact branches for path search.
                if len(base)>=32:break
        if len(base)>=32:break
    print("DRINK_PEAK",json.dumps({"cup_candidates":len(cup_options),"cup_clean":cup_clean,"arm_candidates":tested,"peak_clean":peak_clean,"best_cup":cup_options[0]}),flush=True)
    attempts=[];best=None;passed=None;coarse_best=None
    for params in base:
        for front,drop,lat in itertools.product((.16,.26,.36),(.27,.40),(-.10,0,.10)):
            p=params[:9]+(front,drop,lat,params[-1])
            checks=[evaluate(scene,cam,a,art,cup,yaw,f,p,details=True)[1] for f in (0,8,12,16,22,29,38,44,49,55,59)]
            bad=sum(not x["geometry_pass"] for x in checks)
            coarse_score=(bad,sum(x["head_intersections"]+x["cup_arm_intersections"]+x["cup_body_intersections"]+x["arm_body_intersections"]+x["arm_other_intersections"]+x["face_obstruction"] for x in checks))
            attempts.append({"parameters":list(p),"coarse_failed_frames":bad,"coarse_score":list(coarse_score)})
            if coarse_best is None or coarse_score<coarse_best[0]:coarse_best=(coarse_score,p)
            if bad:continue
            rows=[evaluate(scene,cam,a,art,cup,yaw,f,p,details=True)[1] for f in range(N)]
            failed=[x["frame"] for x in rows if not x["geometry_pass"]]
            attempts[-1]["failed_frames"]=failed
            if failed:continue
            half=[evaluate(scene,cam,a,art,cup,yaw,f+.5,p,details=True)[1] for f in range(N-1)]
            attempts[-1]["failed_half_frames"]=[x["frame"] for x in half if not x["geometry_pass"]]
            if not attempts[-1]["failed_half_frames"]:
                passed=(p,rows,half);break
        if passed:break
    if passed:p,rows,half=passed
    else:
        p=coarse_best[1] if coarse_best else best_failed[1] if best_failed else cup_options[0][1]+(0,-.025,0,.25,0,.24,.36,0,.004)
        rows=[evaluate(scene,cam,a,art,cup,yaw,f,p,details=True)[1] for f in range(N)];half=[]
    contact=[x for x in rows if x["contact"]]
    keys=("head_intersections","upper_head","lower_head","cup_head","cup_arm_intersections","cup_body_intersections","arm_body_intersections","arm_other_intersections","face_obstruction","evaluated_head_intersections","evaluated_cup_arm_intersections","evaluated_face_obstruction","max_segment_length_change","max_joint_gap","grip_gap")
    summary={"geometry_pass":bool(passed),"frames":len(rows),"half_frames":len(half),"cup_candidates":len(cup_options),"cup_clean":cup_clean,"arm_candidates":tested,"peak_clean":peak_clean,"path_attempts":len(attempts),"parameters":list(p),"failed_frames":[x["frame"] for x in rows if not x["geometry_pass"]],"maxima":{k:max(x[k] for x in rows) for k in keys},"max_contact_rim_gap":max(x["rim_gap"] for x in contact),"max_contact_cup_body_above_mouth":max(x["cup_body_above_mouth"] for x in contact)}
    (out/"drink_path_report.json").write_text(json.dumps(dict(summary,rows=rows,half_rows=half,attempts=attempts),indent=2)+"\n")
    print("DRINK_PATH_SUMMARY",json.dumps(summary),flush=True)
    assert passed,"No collision-free sampled path found; no rendering"
if __name__=="__main__":main()
