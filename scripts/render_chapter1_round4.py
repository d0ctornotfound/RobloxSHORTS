"""Round 4: geometry-only solve -> exact pose replay -> rendered validation.
A clean 60-frame plan is mandatory. No image is rendered in geometry mode,
and no image is rendered from a plan until its full evaluated replay passes."""
import argparse,json,sys,math,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from PIL import Image,ImageFilter,ImageChops,ImageStat
from render_character_correction import studio
from render_demo import point_at
from library_camera import metrics
from library_character import character
from r6_character import matte
from character_motion import floor,soles
from chapter1_articulation import Articulation,face_hits
from chapter1_round2 import pose as old_pose
from chapter1_round3 import cross_intersections,body_meshes
from chapter1_round4_solver import (point_pose,mouth_solve,mouth_anchor,hug_solve,search_hug,hug_base,
    actual,data,world,nearest,overlap,restore,rim_distance,ArmSolver,torso_surface)
N=60;FPS=30
NAMES=("point","eat","drink","hug")
def make_cup(scene):
    v=[];f=[];n=32
    for r,z in ((.075,-.10),(.085,.10),(.071,.10),(.061,-.083)):
        v.extend((r*math.cos(math.tau*i/n),r*math.sin(math.tau*i/n),z) for i in range(n))
    for j in range(3):
        for i in range(n):
            k=(i+1)%n;f.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    f.append(tuple(reversed(range(n))));f.append(tuple(range(3*n,4*n)))
    me=bpy.data.meshes.new("Round four open cup");me.from_pydata(v,[],f);me.update()
    ob=bpy.data.objects.new("Studio sip contact cup",me);scene.collection.objects.link(ob)
    ob.data.materials.append(matte("Cup muted teal",(.13,.34,.36)))
    return ob
def setup(name):
    scene,cam,lights=studio();actor=character("Round four lead","lead")
    partner=character("Round four friend","friend") if name=="hug" else None
    art=Articulation(actor,legs=name=="point",arms=name!="point")
    other=Articulation(partner,arms=True) if partner else None
    cup=make_cup(scene) if name=="drink" else None
    yaw=.95 if name=="point" else -.38 if name in ("eat","drink") else .20
    cam.location=(0,-10,2.7) if name in ("point","hug") else (7,-8,2.6)
    point_at(cam,Vector((0,0,1.35)));cam.data.ortho_scale=5.7 if partner else 4.5 if name=="point" else 4.2
    return scene,cam,actor,partner,art,other,cup,yaw
def base_pose(scene,actor,partner,art,other,name,f,yaw,layout):
    scene.frame_set(f+1);u=f/(N-1);t=f/FPS
    if name=="point":
        p=point_pose(actor,art,u,t,yaw);actor.pose("neutral")
    elif name=="hug":
        eng,w,yaws=hug_base(actor,partner,art,other,u,t,layout)
        p={"engagement":eng,"phase":"shoulder_hug"}
    else:
        p,_=old_pose(actor,art,name,u,t,yaw)
        actor.pose("neutral")
    bpy.context.view_layer.update()
    return p
def replay(scene,actor,partner,art,other,cup,name,f,yaw,layout,row):
    p=base_pose(scene,actor,partner,art,other,name,f,yaw,layout)
    if name in ("eat","drink"):
        restore(art.arms[0],row["arm_matrices"])
        if cup:cup.matrix_world=Matrix(row["cup_matrix"])
    elif name=="hug":
        for a,i,m in zip((art,other),row["arm_indices"],row["arm_matrices"]):restore(a.arms[i],m)
    bpy.context.view_layer.update()
    return p
def verify(scene,cam,actor,partner,art,other,cup,name,f,p,row,layout):
    b=metrics(scene,cam,[actor,partner] if partner else [actor])
    framing=all(x["body_safe"] and x["head_safe"] for x in b)
    lm=art.length_metrics()
    if other:
        for k,v in other.length_metrics().items():lm[k]=max(lm[k],v)
    row.update(lm,frame=f+1,seconds=f/FPS,bounds=b,framing_safe=framing,
               soles=[list(v) for v in (art.soles() if art.legs else soles(actor))])
    g={"full_body_framing":framing,"adapter_length_preserved":lm["max_segment_length_change"]<=.02,
       "joint_continuity":lm["max_joint_gap"]<=.002}
    if name in ("eat","drink"):
        decal,anchor,n,up,side,head=mouth_anchor(actor)
        limb=art.arms[0];hand=world(data(limb.lower,limb.b),limb.lower.matrix_world)
        handgap=nearest(hand,decal)[2]
        contact=p["mouth_action"]>=.90
        blockers=[actor.body]+[o for l in art.arms for o in l.objects]+([cup] if cup else [])
        headparts=[actual(actor.head)]+[actual(o) for o in actor.accessories if o!=actor.face and o.type=="MESH" and "head" in o.name.lower()]
        armgeoms=[actual(o) for l in art.arms for o in l.objects]
        headhits=sum(overlap(x,headparts) for x in armgeoms)
        if cup:headhits+=overlap(actual(cup),headparts)
        face=face_hits(cam,actor,blockers)
        clear=min((v-anchor).dot(n) for v in hand[0])
        row.update(hand_to_mouth=handgap,head_surface_intersections=headhits,face_body_blocked_samples=face,
                   contact=contact,hand_outward_clearance=clear)
        g.update(face_clear_geometry=face==0,head_no_intersections=headhits==0)
        if cup:
            cg=actual(cup);rim=rim_distance(cup,cup.matrix_world,decal)
            grip=nearest(hand,Vector(row["grip_anchor"]))[2]
            below=max(v.z-decal.z for j,v in enumerate(cg[0]) if not 32<=j<96)
            ci=overlap(cg,armgeoms)
            row.update(cup_rim_to_mouth=rim,grip_gap=grip,cup_body_above_mouth=below,cup_arm_intersections=ci)
            g.update(mouth_contact=not contact or rim<=.02,cup_below_mouth=not contact or below<=.002,
                     cup_grip_contact=grip<=.02,cup_arm_no_intersections=ci==0)
        else:
            g.update(mouth_contact=not contact or handgap<=.02,hand_outward_contact=not contact or clear>=-.001)
        g["solver_contact_pass"]=bool(row["geometry_pass"])
    elif name=="hug":
        ix,iy=row["arm_indices"];xf,zf=layout[4:]
        anchors=[torso_surface(partner,xf,zf),torso_surface(actor,1-xf,max(.25,zf-.32))]
        hand_geoms=[world(data(l.lower,l.b),l.lower.matrix_world) for l in (art.arms[ix],other.arms[iy])]
        gaps=[nearest(hand,anchor)[2] for hand,(anchor,n) in zip(hand_geoms,anchors)]
        clearance=[min((v-anchor).dot(n) for v in hand[0]) for hand,(anchor,n) in zip(hand_geoms,anchors)]
        inter=cross_intersections(actor,partner);eng=p["engagement"]
        row.update(intersections=inter,hand_surface_gaps=gaps,surface_clearances=clearance,engagement=eng)
        g.update(embrace_no_intersections=inter==0,back_surface_contact=eng<.90 or max(gaps)<=.02,
                 back_outward_contact=eng<.90 or min(clearance)>=-.001,solver_contact_pass=bool(row["geometry_pass"]))
    row["frame_gates"]=g;return row
def report(name,rows,attempts,layout):
    keys=sorted({k for r in rows for k in r["frame_gates"]})
    gates={k:all(r["frame_gates"].get(k,True) for r in rows) for k in keys}
    if name=="point":
        step=max(math.hypot(a["soles"][i][0]-b["soles"][i][0],a["soles"][i][1]-b["soles"][i][1]) for a,b in zip(rows,rows[1:]) for i in range(2))
        gates["planted_foot"]=step<.02
    else:step=None
    contacts=[r for r in rows if r.get("contact") or r.get("engagement",0)>=.90]
    if name!="point":gates["contact_frames_present"]=bool(contacts)
    q={"action":name,"frames":len(rows),"fps":FPS,"geometry_pass":len(rows)==N and all(gates.values()),
       "correction_gates":gates,"failed_frames":{k:[r["frame"] for r in rows if not r["frame_gates"].get(k,True)] for k,v in gates.items() if not v},
       "max_segment_length_change":max(r["max_segment_length_change"] for r in rows),
       "max_joint_gap":max(r["max_joint_gap"] for r in rows),"sole_displacement_per_frame":step,
       "contact_frames":[r["frame"] for r in contacts],"layout":layout,"search_attempts":attempts,"rows":rows}
    if name in ("eat","drink"):
        q.update(face_blocked_samples_max=max(r["face_body_blocked_samples"] for r in rows),
                 max_head_surface_intersections=max(r["head_surface_intersections"] for r in rows),
                 hand_max_gap=max((r["hand_to_mouth"] for r in contacts),default=None),
                 cup_rim_max_gap=max((r["cup_rim_to_mouth"] for r in contacts if r["cup_rim_to_mouth"] is not None),default=None),
                 search_evaluations=sum(r.get("search_evaluations",0) for r in rows))
        if name=="drink":q.update(max_grip_gap=max(r["grip_gap"] for r in rows),max_cup_arm_intersections=max(r["cup_arm_intersections"] for r in rows),
                                   max_cup_body_above_mouth=max((r["cup_body_above_mouth"] for r in contacts),default=None))
    if name=="hug":q.update(max_cross_body_surface_intersections=max(r["intersections"] for r in rows),
                             max_engaged_hand_gap=max((max(r["hand_surface_gaps"]) for r in contacts),default=None))
    return q
def write(p,obj):
    p.write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")
def main():
    p=argparse.ArgumentParser();p.add_argument("--motion",choices=NAMES,required=True);p.add_argument("--output",required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument("--geometry-only",action="store_true");mode.add_argument("--plan")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);name=args.motion;out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,actor,partner,art,other,cup,yaw=setup(name)
    if args.geometry_only:
        rows=[];attempts=[];layout=None;prior=None
        if name=="hug":
            layout,planned,attempts=search_hug(actor,partner,art,other,N)
            write(out/"hug_search.json",{"layout":layout,"attempts":attempts})
        for f in range(N):
            if name=="hug":
                row=planned[f];params=replay(scene,actor,partner,art,other,cup,name,f,yaw,layout,row)
            else:
                params=base_pose(scene,actor,partner,art,other,name,f,yaw,layout)
                row=mouth_solve(actor,art,cam,cup,yaw,params,prior) if name in ("eat","drink") else {}
                if name in ("eat","drink"):prior=row["parameters"]
            row=verify(scene,cam,actor,partner,art,other,cup,name,f,params,row,layout);rows.append(row)
            print("GEOMETRY",name,f+1,row["frame_gates"],flush=True)
            write(out/"partial_geometry.json",{"action":name,"layout":layout,"rows":rows})
        q=report(name,rows,attempts,layout);write(out/"geometry_plan.json",q)
        print("GEOMETRY_SUMMARY",json.dumps({k:v for k,v in q.items() if k not in ("rows","search_attempts")}),flush=True)
        assert q["geometry_pass"],"GEOMETRY PRECHECK FAILED — NO RENDER"
        return
    planpath=Path(args.plan);plan=json.loads(planpath.read_text())
    assert plan["action"]==name and plan["geometry_pass"] and len(plan["rows"])==N
    layout=plan["layout"]
    # Full independent replay check BEFORE first call to bpy.ops.render.
    rows=[]
    for f,row in enumerate(plan["rows"]):
        row=dict(row);params=replay(scene,actor,partner,art,other,cup,name,f,yaw,layout,row)
        rows.append(verify(scene,cam,actor,partner,art,other,cup,name,f,params,row,layout))
    q=report(name,rows,plan.get("search_attempts",[]),layout)
    write(out/"replay_geometry.json",q);assert q["geometry_pass"],"REPLAY GEOMETRY FAILED — NO RENDER"
    clip=out/f"{NAMES.index(name):02d}_lead_{name}";clip.mkdir(exist_ok=True)
    maes=[];prev=None
    for f,row in enumerate(rows):
        replay(scene,actor,partner,art,other,cup,name,f,yaw,layout,row)
        path=clip/f"frame_{f+1:04d}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        assert path.is_file() and path.stat().st_size>0
        with Image.open(path) as im:gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
        if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
        prev=gray
    count=sum(v<.25 for v in maes);fraction=count/len(maes)
    q["near_static"]={"count":count,"transitions":len(maes),"fraction":fraction,"maes":maes,"threshold_mae":.25}
    q["correction_gates"]["performance_motion"]=fraction<=.40
    if name=="point":q["correction_gates"]["point_performance_target"]=fraction<=.30
    q["plan_sha256"]=hashlib.sha256(planpath.read_bytes()).hexdigest();q["visual_review_pending"]=True
    write(clip/"metrics.json",q)
    print("RENDER_SUMMARY",name,q["correction_gates"],flush=True)
if __name__=="__main__":main()
