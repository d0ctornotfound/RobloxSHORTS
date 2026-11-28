"""Reusable, declarative advisory QC for evaluated per-frame scene metrics.
Rules specify a selector, optional row filter, transform, reducer, and limit.
Missing data is an explicit unmeasured flag, never an automatic pass.
"""
import math
def select(row,path):
    current=[row]
    for part in path.split("."):
        nxt=[]
        for value in current:
            if part=="*":
                if isinstance(value,dict):nxt.extend(value.values())
                elif isinstance(value,list):nxt.extend(value)
            elif isinstance(value,dict) and part in value:nxt.append(value[part])
            elif isinstance(value,list) and part.isdigit() and int(part)<len(value):nxt.append(value[int(part)])
        current=nxt
    return [v for v in current if v is not None]
def transform(v,t):
    if t=="abs":return abs(v)
    if t=="vertical_span":return v[3]-v[2]
    if t=="horizontal_span":return v[1]-v[0]
    if t=="safe_bounds":return v[4]>0 and .035<=v[0]<=v[1]<=.965 and .035<=v[2]<=v[3]<=.965
    return v
def compare(value,op,limit):
    return {"max":lambda:value<=limit,"min":lambda:value>=limit,"eq":lambda:value==limit}[op]()
def evaluate(rows,rules):
    result=[]
    for rule in rules:
        vals=[];matched=0
        for row in rows:
            if "when" in rule:
                w=rule["when"];v=select(row,w["selector"])
                if not v or not all(x==w["equals"] for x in v):continue
            matched+=1
            for v in select(row,rule["selector"]):
                try:vals.append(transform(v,rule.get("transform")))
                except (TypeError,IndexError,ValueError):continue
        red=rule.get("reduce","max")
        v=None
        if vals:
            if red=="max":v=max(vals)
            elif red=="min":v=min(vals)
            elif red=="all":v=all(vals)
            elif red=="sum":v=sum(vals)
            elif red=="count_false":v=sum(not x for x in vals)
            elif red=="delta":v=abs(vals[-1]-vals[0])
            elif red=="rms":v=math.sqrt(sum(x*x for x in vals)/len(vals))
        result.append({"name":rule["name"],"selector":rule["selector"],"value":v,"limit":rule["limit"],"operator":rule["op"],"samples":len(vals),"matched_frames":matched,"status":"unmeasured" if v is None else "pass" if compare(v,rule["op"],rule["limit"]) else "flag"})
    return result
if __name__=="__main__":
    rows=[{"a":{"one":{"gap":.01},"two":{"gap":-.02}},"phase":"sit"},{"a":{"one":{"gap":.03}},"phase":"stand"}]
    rules=[{"name":"gap","selector":"a.*.gap","when":{"selector":"phase","equals":"sit"},"transform":"abs","reduce":"max","op":"max","limit":.015},{"name":"missing","selector":"a.*.not_here","op":"eq","limit":True}]
    report=evaluate(rows,rules)
    assert report[0]["value"]==.02 and report[0]["status"]=="flag" and report[0]["samples"]==2
    assert report[1]["status"]=="unmeasured"
    print("declarative QC self-test PASS")

def flow_report(rows, fps=30, expected_frames=None):
    """Evaluate chronological pose differences across chunk boundaries.
    Missing/partial evidence is not a pass; camera motion never counts as actor motion.
    The first frame has no preceding transition and is excluded from the motion denominator.
    """
    rows=sorted(rows,key=lambda r:r["frame"])
    if not rows or any("direction" not in r for r in rows):
        return {"status":"unmeasured","reason":"missing direction samples"}
    if (expected_frames is not None and len(rows)!=expected_frames) or any(b["frame"]!=a["frame"]+1 for a,b in zip(rows,rows[1:])):
        return {"status":"unmeasured","reason":"noncontiguous or incomplete direction samples"}
    d=[r["direction"] for r in rows]; principal=d[0]["principal"]
    if any(x["principal"]!=principal or x["beat_type"]!=d[0]["beat_type"] for x in d):
        return {"status":"unmeasured","reason":"principal or beat type changes within shot"}
    # Absolute scene units: 1.5 mm if a scene unit is treated as one metre.
    # This is a pose-change proxy, not perceived performance or velocity.
    threshold=.0015
    calibrated=all(x.get("motion_schema")=="action_only_v1" for x in d)
    if any(x.get("motion_schema")=="action_only_v1" for x in d) and not calibrated:
        return {"status":"unmeasured","reason":"mixed motion schemas"}
    def measure(cid):
        if len(d)<2 or any(cid not in x["actors"] for x in d):return None
        data=[x["actors"][cid] for x in d]
        if calibrated:
            states=[x.get("action_state","unmeasured") for x in data]
            sig=[x.get("action_pose") for x in data]
            if "unmeasured" in states or any(not p for p in sig) or any(len(p)!=len(sig[0]) for p in sig):return None
            active=[a==b=="action" for a,b in zip(states,states[1:])]
            moved=[max(math.dist(x,y) for x,y in zip(a,b))>=threshold for a,b in zip(sig,sig[1:])]
            count=sum(active);moving=sum(a and b for a,b in zip(active,moved));run=longest=0
            for a,b in zip(active,moved):
                run=run+1 if a and not b else 0;longest=max(longest,run)
            applied={k:[max(abs(x.get("idle_applied_rad",{}).get(k,[0,0,0])[i]) for x in data) for i in range(3)] for k in ("head","torso")}
            return {"action_coverage":moving/count if count else None,"action_coverage_whole_shot":moving/len(active),"longest_action_freeze_s":(longest+1)/fps if count else None,"action_transitions":count,"total_transitions":len(active),"state_frames":{k:states.count(k) for k in set(states)},"idle_profile":data[0]["idle_profile"],"max_applied_idle_rad":applied,"motion_coverage":moving/count if count else None,"held_pose_max_s":(longest+1)/fps if count else None,"start_in_motion":bool(active[0] and moved[0]),"end_in_motion":bool(active[-1] and moved[-1])}
        sig=[x["pose"] for x in data]
        if not sig[0] or any(len(p)!=len(sig[0]) for p in sig):return None
        moving=[max(math.dist(x,y) for x,y in zip(a,b))>=threshold for a,b in zip(sig,sig[1:])]
        run=longest=0
        for m in moving:
            run=0 if m else run+1;longest=max(longest,run)
        return {"motion_coverage":sum(moving)/len(moving),"held_pose_max_s":(longest+1)/fps,"start_in_motion":moving[0],"end_in_motion":moving[-1],"transitions":len(moving)}
    actor_ids=sorted(set().union(*(x["actors"] for x in d)))
    metrics={cid:measure(cid) for cid in actor_ids}
    p=metrics.get(principal)
    kind=d[0]["beat_type"]
    if p is None:
        if not (principal is None and kind=="geography" and all(x.get("pure_establishing",False) for x in d) and len(rows)/fps<=2):return {"status":"unmeasured","reason":"principal motion unavailable"}
        p={"motion_coverage":1,"start_in_motion":True,"end_in_motion":True}
    faces={cid:{"min_height":min(x["actors"][cid]["face_height"] for x in d),"safe_all":all(x["actors"][cid]["face_safe"] for x in d)} for cid in [principal]+d[0]["listeners"] if all(cid in x["actors"] for x in d)}
    if calibrated:
        intentional=p.get("action_transitions",0)==0 and not p.get("state_frames",{}).get("action",0)
        checks={"principal_action_coverage":intentional or (p.get("action_coverage") is not None and p["action_coverage"]>=.8),"principal_action_freeze":intentional or (p.get("longest_action_freeze_s") is not None and p["longest_action_freeze_s"]<=.5),"grade_declared":all(x["grade"] and x["grade"]["preset"]=="warm_saturated_v1" for x in d)}
    else:
        checks={"principal_motion":p["motion_coverage"]>=.8,"principal_edges":p["start_in_motion"] and p["end_in_motion"],"all_actor_holds":all(m is not None and m["held_pose_max_s"]<=.5 for m in metrics.values()),"grade_declared":all(x["grade"] and x["grade"]["preset"]=="warm_saturated_v1" for x in d)}
    # Projection alone can pass for an edge-on or fully obstructed decal.
    # New native samples include facing dot and final-camera ray evidence.
    face_ids=[principal]+d[0]["listeners"] if kind=="interview" else [principal] if kind=="emotion" else []
    if face_ids:
        for cid in face_ids:
            values=[x["actors"].get(cid,{}) for x in d]
            rays=[r.get("actor_qc",{}).get(cid,{}) for r in rows]
            if cid in faces:
                faces[cid]["min_facing_dot"]=min((v.get("face_facing_dot",-1) for v in values),default=-1)
                faces[cid]["min_ray_visibility"]=min((v.get("face_all",{}).get("visible_fraction",0) for v in rays),default=0)
                faces[cid]["max_external_blocks"]=max((v.get("face_external",{}).get("blocked",999) for v in rays),default=999)
                faces[cid]["min_ray_samples"]=min((v.get("face_all",{}).get("samples",0) for v in rays),default=0)
        checks["readable_faces"]=all(cid in faces and faces[cid]["min_facing_dot"]>=.65 and faces[cid]["min_ray_visibility"]>=.85 and faces[cid]["max_external_blocks"]==0 and faces[cid]["min_ray_samples"]>=9 for cid in face_ids)
    if kind=="emotion":checks["face_scale"]=principal in faces and faces[principal]["min_height"]>=.40 and faces[principal]["safe_all"]
    elif kind=="interview":checks["two_face_bounds"]=len(faces)>=2 and all(v["safe_all"] and v["min_height"]>=.12 for v in faces.values())
    elif kind=="action":checks["action_body_scale"]=all(r.get("actor_qc",{}).get(principal,{}).get("vertical_coverage",0)>=.25 for r in rows)
    elif kind=="geography":
        checks["body_scale"]=all(r.get("actor_qc",{}).get(principal,{}).get("vertical_coverage",0)>=.25 for r in rows) or (len(rows)/fps<=2 and all(x.get("pure_establishing",False) for x in d))
    if kind=="information":
        diagrams=[r.get("geometry",{}).get("world_diagram") for r in rows]
        checks["actual_cast_diagram"]=all(x is not None and x["actor_count"]==x["expected_actor_count"] and x["link_count"]==x["expected_link_count"] and len(set(x["actual_cast_ids"]))==x["actor_count"] for x in diagrams)
        checks["diagram_framing"]=all(x and x.get("framing_bounds") and x["framing_bounds"][4]>0 and .025<=x["framing_bounds"][0]<=x["framing_bounds"][1]<=.975 and .025<=x["framing_bounds"][2]<=x["framing_bounds"][3]<=.975 for x in diagrams)
    if kind=="geography":checks["landmarks_declared"]=all(bool(x.get("landmarks")) for x in d)
    if any(x.get("landmarks") for x in d):
        required=set().union(*(x.get("landmarks",{}) for x in d))
        checks["landmarks_visible"]=all(all(x.get("landmarks",{}).get(k,{}).get("pass",False) for k in required) for x in d)
    return {"status":"numeric_pass" if all(checks.values()) else "flag","beat_type":kind,"principal":principal,"actors":metrics,"faces":faces,"checks":checks,"grade":d[0]["grade"],"threshold_scene_units":threshold,"motion_schema":"action_only_v1" if calibrated else "legacy_all_pose","idle_profile":d[0].get("idle_profile"),"visual_review_required":True}
