"""Strict geometry-first proof runner. No render may start before the full
unit has passed all numeric checks. Diagnostic images are not native clips."""
import argparse,json,math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from PIL import Image
from render_saying_hi_shot import ROOT,UNITS,FPS,load,setup,create,StrideLock
from saying_hi_correction import CorrectedUnit,V

def evaluate_gate(unit,driver,rows):
    ms=[r["metrics"] for r in rows];checks={}
    def check(key,value,limit,ok):checks[key]={"value":value,"limit":limit,"pass":bool(ok)}
    if unit=="crossing":
        lock=driver.lock;report=lock.report();rs=lock.records
        end=V(rs[-1]["contact_world"]);err=(end-driver.end).length
        allback=sum(x["forward_speed"]<-.01 for x in rs)
        continuing=[x for x in rs if x["continuing"]]
        rms=math.sqrt(sum(x["velocity"]**2 for x in continuing)/len(continuing))
        drift=max((V(x["contact_world"])-end).length for x in rs[-driver.hold:])
        check("locked_stride_pass",report["pass"],True,report["pass"])
        check("planted_stop_error",err,.05,err<=.05)
        check("backward_frames_including_settle",allback,0,allback==0)
        check("stance_rms_including_settle",rms,.03,rms<=.03)
        check("settled_support_drift",drift,.005,drift<=.005)
        check("locked_stance_rms",report["stance_velocity_rms"],.03,report["stance_velocity_rms"]<=.03)
        check("camera_geography_fitted",driver.cross_camera["candidate_found"],True,driver.cross_camera["candidate_found"])
        carry=[x for x in ms if "actor_bounds" in x]
        cov=min(x["actor_bounds"][3]-x["actor_bounds"][2] for x in carry)
        check("narrator_vertical_coverage",cov,.14,cov>=.14)
        safe=all(.035<=x["actor_bounds"][0]<=x["actor_bounds"][1]<=.965 and .035<=x["actor_bounds"][2]<=x["actor_bounds"][3]<=.965 and x["actor_bounds"][4]>0 for x in carry)
        check("full_body_safe",safe,True,safe)
        blocked=sum(not x["foot_visible"] for x in carry)
        check("support_ray_blocked_frames",blocked,0,blocked==0)
        extra={"stride":{k:v for k,v in report.items() if k!="records"},"target_mark":list(driver.end),"actual_planted_contact":list(end),"root_stop":list(lock.pos),"root_stop_error":(lock.pos-driver.end).length,"walk_solution":driver.stride_candidate,"search_candidates":driver.stride_search,"camera":driver.cross_camera}
    elif unit=="otis_eyes":
        overlap=max(x["head_arm_overlap_pairs"] for m in ms for x in m["eyes"])
        covered=min(m["eye_samples_covered"] for m in ms if m["coverage_progress"]>.99)
        check("max_head_arm_intersections",overlap,0,overlap==0)
        check("covered_eye_samples_at_full_pose",covered,2,covered==2)
        extra={"eye_solution":driver.eye_solution,"search_candidates":getattr(driver,"eye_search",[]),"max_hand_target_gap":max(x["hand_target_gap"] for m in ms for x in m["eyes"])}
    elif unit in ("june_question","june_answer"):
        pairs=max(m["standing_seat_intersections"] for m in ms)
        check("standing_seat_intersections",pairs,0,pairs==0)
        b=max(m["speaker_visibility"]["blocked"] for m in ms);s=min(m["speaker_visibility"]["samples"] for m in ms)
        check("speaker_occlusion_samples",b,0,b==0 and s>0)
        safe=all(m["speaker_visibility"]["safe"] for m in ms)
        check("speaker_in_frame",safe,True,safe)
        if unit=="june_question":
            x=[m["pencil_external_visibility"] for m in ms];y=[m["pencil_visibility"] for m in ms]
            b=max(m["blocked"] for m in x);s=min(m["samples"] for m in x)
            check("external_pencil_occlusion_samples",b,0,b==0 and s>0)
            check("pencil_in_frame",all(m["safe"] for m in x),True,all(m["safe"] for m in x))
            v=min(m["visible_fraction"] for m in y)
            check("visible_pencil_fraction",v,.45,v>=.45)
        extra={"camera":driver.reverse_camera,"marks":{"june":list(driver.jp),"narrator":list(driver.np)}}
    elif unit in ("dog_name","seating","closing"):
        dog=[m["dog_visibility"] for m in ms if m["dog_visible"]]
        b=max((x["blocked"] for x in dog),default=-1);s=min((x["samples"] for x in dog),default=0)
        check("dog_occlusion_samples",b,0,b==0 and s>0)
        safe=bool(dog) and all(x["safe"] for x in dog)
        check("dog_fully_in_frame",safe,True,safe)
        ground=max((abs(m["waffle"]["evaluated_min_z"]) for m in ms if m["dog_visible"]),default=999)
        check("dog_floor_error",ground,.002,ground<=.002)
        june=[m["seat_contacts"]["june"] for m in ms]
        lateral=max(x["lateral_hip_drift"] for x in june if x["phase"]!="step")
        check("june_lateral_hip_drift_outside_step",lateral,.005,lateral<=.005)
        seated=[x for m in ms for x in m["seat_contacts"].values() if x["phase"] in ("seated","initial_seated")]
        gap=max((abs(x["signed_rear_hip_gap"]) for x in seated),default=999)
        check("settled_hip_plane_error",gap,.015,gap<=.015)
        feet=max(abs(z) for m in ms for x in m["seat_contacts"].values() for z,moving in zip(x["signed_foot_gaps"],x["moving_feet"]) if not moving)
        check("planted_floor_error",feet,.002,feet<=.002)
        # A stance starts after the prior swing; do not count a swing-to-plant
        # interval as a continuing stance. Still check floor on every plant.
        drift=0
        for a,b in zip(ms,ms[1:]):
            for cid in ("june","narrator"):
                p=a["seat_contacts"][cid];q=b["seat_contacts"][cid]
                if q["foot_step_drift"]:
                    for i,d in enumerate(q["foot_step_drift"]):
                        if not p["moving_feet"][i] and not q["moving_feet"][i]:drift=max(drift,d)
        check("continuing_planted_foot_drift",drift,.005,drift<=.005)
        if unit=="seating":
            displacement=abs(june[-1]["hip_world"][1]-june[0]["hip_world"][1])
            check("actual_move_over_displacement",displacement,.20,displacement>=.20)
        extra={"dog_visible_frames":len(dog),"minimum_dog_samples":s,"camera":list(driver.cam.location)}
    elif unit=="empty_wall":
        check("wall_tally_strokes",min(m["tally_count"] for m in ms),35,all(m["tally_count"]==35 for m in ms))
        check("boys_on_wall",max(m["boys_on_wall"] for m in ms),0,all(m["boys_on_wall"]==0 for m in ms))
        for k in ("wall_visibility","tally_visibility"):
            b=max(m[k]["blocked"] for m in ms);s=min(m[k]["samples"] for m in ms)
            check(k+"_occlusion_samples",b,0,b==0 and s>0)
            check(k+"_in_frame",all(m[k]["safe"] for m in ms),True,all(m[k]["safe"] for m in ms))
        extra={"camera":list(driver.cam.location)}
    else:raise ValueError(unit)
    return {"unit":unit,"samples":len(rows),"sampling_hz":30,"checks":checks,"pass":all(x["pass"] for x in checks.values()),**extra}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--unit",required=True);ap.add_argument("--mode",choices=["check","motion"],required=True);ap.add_argument("--map",required=True);ap.add_argument("--lineup",required=True);ap.add_argument("--output",required=True);ap.add_argument("--cache");a=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    c,stage=load();plan=json.loads((ROOT/"stories/saying_hi_plan.json").read_text());ids=UNITS[a.unit];shots=[plan["shots"][i-1] for i in ids]
    start=round(shots[0]["edit_in"]*FPS);end=round(shots[-1]["edit_out"]*FPS);count=end-start
    scene=setup(540,960);scene.frame_end=round(plan["audio_duration"]*FPS);cam=create(scene);driver=CorrectedUnit(scene,cam,c,stage,a.unit,ids,a.map,a.lineup)
    cache=json.loads(Path(a.cache).read_text()) if a.cache else {}
    if a.unit=="crossing":
        driver.cached_walk=cache.get("walk_solution");driver.prepare_stride(count)
    elif a.unit=="otis_eyes" and cache:driver.eye_solution=cache["eye_solution"]
    def sample(gf):
        shot=next(x for x in shots if round(x["edit_in"]*FPS)<=gf<round(x["edit_out"]*FPS))
        n=int(shot["sentence_ids"][0]);s0=round(shot["edit_in"]*FPS);s1=round(shot["edit_out"]*FPS)
        scene.frame_set(gf+1)
        return {"global_frame":gf,"sentence":n,"metrics":driver.update(n,(gf-s0)/max(1,s1-s0-1),(gf-start)/FPS,gf-start,gf/FPS>=shot["audio_out"])}
    rows=[]
    for gf in range(start,end):
        row=sample(gf);rows.append(row)
        if gf%10==0:print("GEOMETRY_FRAME",a.unit,gf,flush=True)
    gate=evaluate_gate(a.unit,driver,rows)
    (out/"geometry.json").write_text(json.dumps({"unit":a.unit,"frame_window":[start,end],"metrics":rows},indent=2)+"\n")
    (out/"gate.json").write_text(json.dumps(gate,indent=2)+"\n")
    print("GEOMETRY_GATE",json.dumps(gate,default=str),flush=True)
    if not gate["pass"]:raise RuntimeError("All-frame geometry gate FAILED; no render invoked")
    # Every geometry sample has passed. Reset only the story-local state
    # and replay same clock/parameters for real through-camera evidence.
    if a.unit=="crossing":
        ret=driver.lock.ret;driver.lock=StrideLock(ret,"walk_cycle",FPS,driver.stride_candidate["rate"],driver.start,driver.yaw)
    if a.unit in ("dog_name","seating","closing"):
        driver.prev_feet={};driver.prev_hip={};driver.prev_phase={}
    selected=set(range(start,end)) if a.mode=="motion" else {start,start+count//4,start+count//2,start+3*count//4,end-1}
    if a.mode=="check" and a.unit=="dog_name":selected={r["global_frame"] for r in rows if r["metrics"]["dog_visible"]}
    if a.mode=="check" and a.unit=="june_question":
        selected.update(r["global_frame"] for r in rows if abs(r["metrics"]["pencil_shake_phase"])>.99)
    rendered=[];replay=[]
    for gf in range(start,end):
        row=sample(gf);replay.append(row)
        if gf not in selected:continue
        path=out/f"frame_{gf:05d}.png";scene.render.filepath=str(path);clock=time.monotonic()
        print("RENDER_AFTER_GEOMETRY_PASS",a.unit,gf,flush=True);bpy.ops.render.render(write_still=True)
        pixels=np.asarray(Image.open(path).convert("RGB"));rendered.append({"frame":gf,"file":path.name,"render_seconds":time.monotonic()-clock,"near_black_percent":100*float(np.mean(np.max(pixels,axis=2)<=24))})
        (out/"partial.json").write_text(json.dumps({"rendered":rendered},indent=2)+"\n")
    assert len(rendered)==len(selected)
    second=evaluate_gate(a.unit,driver,replay);assert second["pass"],"replay geometry changed"
    assert max(x["near_black_percent"] for x in rendered)<=10,"darkness gate failed"
    m={"unit":a.unit,"mode":"motion" if a.mode=="motion" else "smoke","sentence_ids":ids,"engine":"EEVEE","denoising":False,"eevee_spatial_samples":32,"frame_window":[start,end],"actual_rendered_frames":len(rendered),"expected_rendered_frames":len(selected),"rendered_temporal_samples_per_second":30 if a.mode=="motion" else None,"encoded_fps_target":30 if a.mode=="motion" else None,"rendered":rendered,"metrics":rows,"geometry_gate":gate,"scenery":driver.scenery}
    (out/"manifest.json").write_text(json.dumps(m,indent=2)+"\n")
    if a.mode=="check":
        import shutil
        shutil.copyfile(out/rendered[-1]["file"],out/"held_pose.png")
if __name__=="__main__":main()
