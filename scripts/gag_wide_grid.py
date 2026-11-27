"""Test-only joint stage/camera grid. Proposals use cached support vertices,
never acceptance: all shortlisted candidates receive exact 21-frame gate checks.
Record failed gates on each frame, including original fixed-offset control."""
import json,math,itertools
from pathlib import Path
import numpy as np
import bpy
from mathutils import Vector
from library_camera import apply,points
from r6_character import mesh_points

def save(out,name,data):
    (out/name).write_text(json.dumps(data,indent=2)+"\n")
def support(verts):
    # Directional support points rank camera proposals only. Exact Blender
    # metrics and rays below decide acceptance, not this approximate proxy.
    a=np.array([tuple(v) for v in verts],dtype=float)
    directions=np.array(list(itertools.product(range(-2,3),repeat=3)),dtype=float)
    directions=directions[np.any(directions!=0,axis=1)]
    return a[np.unique(np.argmax(a@directions.T,axis=0))]
def proj(a,p,q,lens,aspect):
    forward=q-p;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right)
    up=np.cross(right,forward);v=a-p;z=v@forward
    if np.min(z)<=0:return (-9.,9.,-9.,9.,float(np.min(z)))
    x=.5+(v@right)/z*lens/36
    y=.5+(v@up)/z*lens/36*aspect
    return (float(x.min()),float(x.max()),float(y.min()),float(y.max()),float(z.min()))
def stats(bs):
    cov=[max(0,min(1,b[3])-max(0,b[2])) for b in bs]
    ratio=min(cov)/max(max(cov),1e-8)
    margin=min(min(b[0]-.035,.965-b[1],b[2]-.035,.965-b[3],b[4]) for b in bs)
    return ratio,sum(cov),margin
def exact_summary(row):
    b=row["bounds"];cov=[x["coverage"] for x in b]
    ratio=row["size_ratio"];total=sum(cov)
    sep=abs(b[0]["face_center"][0]-b[1]["face_center"][0])
    face=row["face"];lamps=row["lamp_overlap"]
    failures=[]
    if ratio<.70:failures.append("ratio")
    if total<.75:failures.append("combined_coverage")
    if any(not x["body_safe"] for x in b):failures.append("frame_bounds")
    if any(x["face_ray_fraction"]<.78 for x in face.values()):failures.append("face_visibility")
    if any(x["arm_overlap_upper_bound"]>.10 for x in face.values()):failures.append("arm_overlap")
    if any(x>.05 for x in lamps.values()):failures.append("lamp_overlap")
    # Face separation was a ranking preference in this gag, not a hard gate.
    # Record it without silently importing the generic fit_two_shot .20 cutoff.
    return {"frame":row["frame"],"ratio":ratio,"coverage":cov,"combined_coverage":total,
            "face_separation":sep,"face":face,"lamp_overlap":lamps,
            "bounds":[x["bounds"] for x in b],"failures":failures,
            "pass":row["body_pass"] and row["face_pass"] and row["lamp_pass"] and row["balance_pass"]}
def search(scene,cam,heroes,out,set_stage,new_lock,pose,check,render):
    zero=(0.,0.,0.);set_stage(zero,zero);pose(new_lock(),0)
    roots=[np.array(tuple(a.root.location)) for a in heroes]
    meshes=[support(points(a)) for a in heroes]
    faces=[support(mesh_points(a.face)) for a in heroes]
    aspect=scene.render.resolution_x/scene.render.resolution_y
    # Along-street x shifts alter depth for the existing oblique cameras;
    # cross-street y offsets separate silhouettes. Constant translations.
    stages=list(itertools.product((.0,.75,1.5,2.25),(-.0,-.65,-1.3,-1.95),(-.45,0,.45),(-.35,0,.35)))
    stages.append((1.9,-1.6,0.,0.)) # exact failed control
    proposals=[];count=0
    for lx,fx,ly,fy in stages:
        shifts=[np.array((lx,ly,0)),np.array((fx,fy,0))]
        q=(roots[0]+shifts[0]+roots[1]+shifts[1])/2;q[2]=1.30
        stage_best=[]
        for angle,dist,height,lens in itertools.product((0,25,45,55,65,75,80,-25,-45),(5.5,7.5,10.,13.),(1.55,1.85,2.2),(35,50,66,85)):
            a=math.radians(angle);p=q+np.array((dist*math.sin(a),-dist*math.cos(a),height-q[2]))
            bs=[proj(m+s,p,q,lens,aspect) for m,s in zip(meshes,shifts)]
            ratio,total,margin=stats(bs)
            fs=[proj(m+s,p,q,lens,aspect) for m,s in zip(faces,shifts)]
            sep=abs((fs[0][0]+fs[0][1]-fs[1][0]-fs[1][1])/2)
            # Favor useful separation, balance and tightness; do not hard-reject.
            penalty=8*max(0,.70-ratio)+6*max(0,.75-total)+12*max(0,-margin)
            score=total+1.5*ratio+.9*sep-.09*(height-1.55)-.012*(dist-5)-penalty
            stage_best.append((score,tuple(p),tuple(q),lens,tuple(shifts[0]),tuple(shifts[1]),ratio,total,margin,sep))
            count+=1
        stage_best.sort(reverse=True);proposals.extend(stage_best[:2])
    proposals.sort(reverse=True)
    control=[p for p in proposals if p[4]==(1.9,0.,0.) and p[5]==(-1.6,0.,0.)]
    # Diversify by staging: first pass top candidate from each of 24 different stages,
    # then alternatives. Bounded exact search, not claim of exhaustive camera grid.
    chosen=[];seen=set()
    for p in proposals:
        key=(p[4],p[5])
        if key in seen:continue
        chosen.append(p);seen.add(key)
        if len(chosen)>=24:break
    for p in control+proposals[:24]:
        if p not in chosen:chosen.append(p)
    audit={"proposals_ranked":count,"staging_grid_count":len(stages),"shortlist_count":len(chosen),"thresholds":{"ratio":.70,"combined_coverage":.75,"frame_margin":.035,"face_ray_fraction":.78,"arm_overlap":.10,"lamp_overlap":.05,"face_separation":"ranking preference, no hard threshold"},"attempts":[]}
    winner=None
    for i,p in enumerate(chosen):
        score,pos,q,lens,ls,fs,_,_,_,_=p
        set_stage(ls,fs);lock=new_lock();rows=[]
        for f in range(21):
            pose(lock,f);apply(cam,"static",0,pos,q,lens);rows.append(exact_summary(check(f)))
        fails={}
        for row in rows:
            for gate in row["failures"]:fails.setdefault(gate,[]).append(row["frame"])
        attempt={"rank":i+1,"score":score,"lead_shift":ls,"friend_shift":fs,"position":pos,"target":q,"lens":lens,
                 "minimum_ratio":min(r["ratio"] for r in rows),"minimum_combined_coverage":min(r["combined_coverage"] for r in rows),
                 "minimum_face_separation":min(r["face_separation"] for r in rows),"failed_frames_by_gate":fails,
                 "passed_frames":sum(r["pass"] for r in rows),"frames":rows}
        audit["attempts"].append(attempt);save(out,"wide_search_audit.json",audit)
        print("WIDE_GRID_ATTEMPT",json.dumps({k:v for k,v in attempt.items() if k!="frames"}),flush=True)
        if attempt["passed_frames"]==21 and winner is None:winner=attempt
        # Continue across best candidates for diagnostic comparison, including control.
        if winner is not None and i>=7 and (not control or any(a["lead_shift"]==control[0][4] and a["friend_shift"]==control[0][5] for a in audit["attempts"])):break
    audit["winner"]=winner;save(out,"wide_search_audit.json",audit)
    print("WIDE_GRID_SUMMARY",json.dumps({"proposals":count,"stages":len(stages),"exact_attempts":len(audit["attempts"]),"winner":None if winner is None else {k:v for k,v in winner.items() if k!="frames"}}),flush=True)
    if winner is None:raise RuntimeError("No shortlisted candidate passes all 21 frames; see per-frame diagnostic audit")
    set_stage(winner["lead_shift"],winner["friend_shift"]);lock=new_lock();rows=[];failures=[]
    for f in range(21):
        pose(lock,f);apply(cam,"static",0,winner["position"],winner["target"],winner["lens"]);row=check(f)
        if not exact_summary(row)["pass"]:failures.append(row)
        if f in (0,10,20):
            render(f,row)
            if any(not x["pass"] for x in row.get("visibility",{}).values()):failures.append(row)
        rows.append(row)
    save(out,"geometry_preflight.json",{"rows":rows,"failures":failures})
    assert not failures,"Wide proof or actual object-ID visibility failed"
