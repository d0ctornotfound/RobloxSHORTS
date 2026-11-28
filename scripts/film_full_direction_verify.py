"""Independent full-film audit and before/after QC publication.
Run in a fresh checkout of the exact publication commit. No render artifacts
are accepted in lieu of committed footage. No artistic pass is inferred."""
import argparse,json,os,subprocess
from pathlib import Path
from film_direction_compare import verify,pixel_rows,summarize,read,sha
from film_timeline import run

def summarize_direction(q):
    if not q:return {"status":"unmeasured","scale_classes":[],"principal_motion_min":None,"all_actor_hold_max_s":None}
    parts=[x["direction"] for x in q.get("segments",[])] if "segments" in q else [q]
    rates=[];holds=[];classes=[]
    for p in parts:
        classes.append(p.get("beat_type","unmeasured"))
        actors=p.get("actors",{})
        if p.get("principal") in actors and actors[p["principal"]]:rates.append(actors[p["principal"]]["motion_coverage"])
        holds.extend(v["held_pose_max_s"] for v in actors.values() if v)
    return {"status":q.get("status","unmeasured"),"scale_classes":classes,"principal_motion_min":min(rates) if rates else None,"all_actor_hold_max_s":max(holds) if holds else None}

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--evidence",required=True);a=p.parse_args()
    c=read(a.config);out=Path(c["output_dir"]);plan=read(c["plan"]);n=round(plan["audio_duration"]*30)
    assert subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()==a.evidence
    val=read(out/"film_validation.json");qc=read(out/"qc.json");before=read(c["round5_qc"])["shots"]
    assert not qc["missing"] and qc["shot_count"]==len(plan["shots"])
    master=out/c["film_name"]
    base=Path(c.get("comparison_baseline","assets/saying_hi_review/round5/saying_hi.mp4"))
    base_info=verify(base,n,c.get("comparison_baseline_sha256"));info=verify(master,n,val["sha256"])
    old=pixel_rows(base,n);new=pixel_rows(master,n)
    dest=out/"independent";dest.mkdir(parents=True,exist_ok=True)
    report={"evidence_commit":a.evidence,"run_id":os.environ.get("GITHUB_RUN_ID"),"master":info,"baseline":base_info,"baseline_motion_scope":"unmeasured: Round 5 did not store evaluated pose samples for flow","shots":{},"visual_approval":"pending reviewer; exact frame counts and pixel statistics are not artistic approval"}
    lines=["","## Independent Round 6 committed master audit","",f"Verified exact publication commit {a.evidence}; {info['frames']} frames, {info['duration']:.2f}s, SHA-256 {info['sha256']}.","",
        "| Shot | Round 5 declared scale | Round 6 beat scale | Principal motion | Max hold | Saturation before → after | QC |","|---|---|---|---:|---:|---|---|"]
    for s in plan["shots"]:
        sid=s["id"];lo,hi=round(s["edit_in"]*30),round(s["edit_out"]*30);q=qc["shots"][sid];oldq=before[sid]
        d=summarize_direction(q.get("direction"));b=summarize(old[lo:hi]);v=summarize(new[lo:hi])
        frames=[]
        for label,k in (("first",lo),("middle",(lo+hi)//2),("last",hi-1)):
            target=dest/f"{sid}_{label}.png"
            run(["ffmpeg","-y","-v","error","-i",str(master),"-vf",f"select=eq(n\\,{k})","-frames:v","1",str(target)])
            frames.append(str(target))
        coverage=[x["min_vertical_coverage"] for x in oldq.get("chunks",[]) if "min_vertical_coverage" in x]
        report["shots"][sid]={"start":lo,"end":hi,"before":{"declared_scale":s["camera"]["size"],"min_body_coverage":min(coverage) if coverage else None,"motion_coverage":None,"held_pose_max_s":None,"grade_pixels":b,"flags":oldq.get("flags",[])},"after":{"direction":q.get("direction"),"summary":d,"grade_pixels":v,"flags":q.get("flags",[]),"review_frames":frames,"reused":any(x.get("type")=="approved_native_reuse" for x in q.get("chunks",[]))}}
        mot="unmeasured" if d["principal_motion_min"] is None else f"{100*d['principal_motion_min']:.1f}%"
        hold="unmeasured" if d["all_actor_hold_max_s"] is None else f"{d['all_actor_hold_max_s']:.3f}s"
        lines.append(f"| {sid} | {s['camera']['size']} (plan) | {', '.join(d['scale_classes'])} | {mot} | {hold} | {b['saturation']:.3f} → {v['saturation']:.3f} | {d['status']}; {len(q['flags'])} flags |")
    report["weak_shots"]=[{"id":sid,"start":r["start"]/30,"end":r["end"]/30,"flags":r["after"]["flags"]} for sid,r in report["shots"].items() if r["after"]["flags"] or r["after"]["summary"]["status"]!="numeric_pass"]
    lines.extend(["","Round 5 motion and held-pose metrics are unmeasured; no invented zero or before/after improvement percentage. Saturation is a descriptive downscaled RGB statistic, composition dependent. All legacy flags and exact direction measurements remain in the JSON. No claim of general story-independent artistic mastery."])
    (dest/"audit.json").write_text(json.dumps(report,indent=2)+"\n")
    with Path(c["review_path"]).open("a") as f:f.write("\n".join(lines)+"\n")
    paths=sorted(p for p in dest.iterdir() if p.is_file() and p.name!="SHA256SUMS")
    (dest/"SHA256SUMS").write_text("".join(sha(p)+"  "+str(p)+"\n" for p in paths))
    with Path(c["inventory_path"]).open("a") as f:f.write("\nIndependent Round 6 committed verification:\n"+"\n".join(str(p) for p in paths+[dest/"SHA256SUMS"])+"\n")
if __name__=="__main__":main()
