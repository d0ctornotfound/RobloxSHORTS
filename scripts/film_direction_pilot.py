"""Select, assemble and permanently publish only the authorized director pilot.
The full-film lane is not invoked and cannot be released by this program.
"""
import argparse,json,os,subprocess,hashlib
from pathlib import Path
from shutil import copytree,copy2
from film_timeline import compile_tasks,read,write,check_video,sha,run
from film_qc import flow_report

def tasks(c):
    ids={s for g in c["pilot_groups"] for s in g["shots"]}
    result=[t for t in compile_tasks(c) if t["shot"] in ids]
    assert result and all("reuse" not in t for t in result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("command",choices=["matrix","assemble"]);p.add_argument("--chunks",default="/tmp/film-chunks");a=p.parse_args();c=read(a.config);ts=tasks(c)
    if a.command=="matrix":
        print(json.dumps({"include":[{"key":t["key"],"task":json.dumps(t,separators=(",",":"))} for t in ts]},separators=(",",":")));return
    out=Path(c["output_dir"]);out.mkdir(parents=True,exist_ok=True);chunks=Path(a.chunks)
    if chunks.exists():copytree(chunks,out/"chunks",dirs_exist_ok=True)
    plan=read(c["plan"]);baseline=Path(c["pilot_baseline"])
    report={"run_id":os.environ.get("GITHUB_RUN_ID"),"source_commit":os.environ.get("GITHUB_SHA"),"baseline":str(baseline),"groups":{},"visual_review_required":True,"full_render_authorized":False}
    for group in c["pilot_groups"]:
        name=group["name"];selected=[t for t in ts if t["shot"] in group["shots"]];rows={};clips=[];missing=[];quality={}
        for t in selected:
            d=chunks/t["key"]
            if not (d/"clip.mp4").exists() or not (d/"manifest.json").exists():missing.append(t["key"]);continue
            m=read(d/"manifest.json");n=t["end"]-t["start"];check_video(d/"clip.mp4",n)
            assert [x["frame"] for x in m["rendered"]]==list(range(t["start"],t["end"]))
            assert m["engine"]=="EEVEE" and m["denoising"] is False and m["render_sampling_hz"]==30
            rows.setdefault(t["shot"],[]).extend(m["rows"]);clips.append(d/"clip.mp4")
        g={"missing_chunks":missing,"shots":{}}
        for sid in group["shots"]:
            st=next(s for s in plan["shots"] if s["id"]==sid);start=round(st["edit_in"]*30);end=round(st["edit_out"]*30)
            rs=rows.get(sid,[]);flow=flow_report(rs,expected_frames=end-start)
            shot_tasks=[t for t in selected if t["shot"]==sid]
            manifests=[read(chunks/t["key"]/"manifest.json") for t in shot_tasks if (chunks/t["key"]/"manifest.json").is_file()]
            dark=max((r["near_black_percent"] for m in manifests for r in m["rendered"]),default=None)
            walks=[m["extra"]["walk"] for m in manifests if m.get("extra",{}).get("walk",{}).get("complete_unit")]
            gait_ok=all(w["metrics"]["pass"] and w["metrics"]["backward_frames"]==0 and w["metrics"]["stance_velocity_rms"]<=.03 and w["final_contact_error"]<=.05 and (w["final_plant"] if w.get("end_mode","stop")=="stop" else w.get("end_mode")=="moving_cut" and w.get("last_support") in (0,1) and w.get("last_forward_speed",0)>0) for w in walks) if walks else None
            face_blocks={cid:max(x["actor_qc"][cid]["face_external"]["blocked"] for x in rs if cid in x["actor_qc"]) for cid in sorted({cid for x in rs for cid in x["actor_qc"]})}
            g["shots"][sid]={"start":start,"end":end,"direction":flow,"external_face_ray_blocks_max":face_blocks,"native_near_black_max_percent":dark,"walk_evidence":walks,"gait_gate":gait_ok}
            if baseline.is_file():
                for label,k in (("first",start),("middle",(start+end)//2),("last",end-1)):
                    path=out/f"{sid}_round5_{label}.png"
                    run(["ffmpeg","-y","-v","error","-i",str(baseline),"-vf",f"select=eq(n\\,{k})","-frames:v","1",str(path)])
        if not missing:
            concat=out/(name+"_concat.txt");concat.write_text("".join("file '"+str(p.resolve())+"'\n" for p in clips))
            start=selected[0]["start"];end=selected[-1]["end"];film=out/(name+".mp4")
            run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(concat),"-ss",str(start/30),"-i",plan["narration_audio"],"-map","0:v:0","-map","1:a:0","-t",str((end-start)/30),"-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-c:a","aac",str(film)])
            check_video(film,end-start);g.update({"clip":str(film),"frames":end-start,"sha256":sha(film)})
            for sid,q in g["shots"].items():
                for label,k in (("first",q["start"]),("middle",(q["start"]+q["end"])//2),("last",q["end"]-1)):
                    run(["ffmpeg","-y","-v","error","-i",str(film),"-vf",f"select=eq(n\\,{k-start})","-frames:v","1",str(out/f"{sid}_round6_{label}.png")])
        report["groups"][name]=g
    report["numerical_pass"]=all(not g["missing_chunks"] and all(s["direction"]["status"]=="numeric_pass" and all(v==0 for v in s["external_face_ray_blocks_max"].values()) and s["native_near_black_max_percent"] is not None and s["native_near_black_max_percent"]<=2 and s["gait_gate"] is not False for s in g["shots"].values()) for g in report["groups"].values())
    write(out/"pilot_qc.json",report)
    with Path(c["review_path"]).open("a") as f:
        f.write("\n## Round 6 direction pilot run "+str(report["run_id"])+"\n")
        f.write("Pilot numerical pass: "+str(report["numerical_pass"])+". Actual visual/playback inspection still mandatory; full-film pass not authorized. Evidence: "+str(out/"pilot_qc.json")+"\n")
    paths=[p for p in sorted(out.rglob("*")) if p.is_file() and p.name!="SHA256SUMS"]
    (out/"SHA256SUMS").write_text("".join(sha(p)+"  "+str(p)+"\n" for p in paths))
    with Path(c["inventory_path"]).open("a") as f:f.write("\nRound 6 pilot evidence:\n"+"\n".join(str(p) for p in paths+[out/"SHA256SUMS"])+"\n")
if __name__=="__main__":main()
