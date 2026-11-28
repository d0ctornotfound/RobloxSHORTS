"""Director preflight: complete geometry sample sequence plus three native
smoke frames per shot. Never produces or certifies a complete pilot clip."""
import argparse,json,os
from pathlib import Path
from shutil import copytree,copy2
from film_direction_pilot import tasks
from film_timeline import read,write,sha
from film_qc import flow_report

def matrix(c):
    ts=tasks(c);out=[]
    for g in c["pilot_groups"]:
        for sid in g["shots"]:
            chunks=[t for t in ts if t["shot"]==sid]
            assert chunks and all(t["stage"]==chunks[0]["stage"] for t in chunks)
            assert all(a["end"]==b["start"] for a,b in zip(chunks,chunks[1:]))
            t={**chunks[0],"key":sid,"end":chunks[-1]["end"]}
            out.append({"key":sid,"task":json.dumps(t,separators=(",",":"))})
    return {"include":out}

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("command",choices=["matrix","publish"]);p.add_argument("--chunks");p.add_argument("--audit");a=p.parse_args();c=read(a.config)
    if a.command=="matrix":print(json.dumps(matrix(c),separators=(",",":")));return
    out=Path(c["preflight_output_dir"]);out.mkdir(parents=True,exist_ok=True)
    chunks=Path(a.chunks)
    report={"run_id":os.environ.get("GITHUB_RUN_ID"),"source_commit":os.environ.get("GITHUB_SHA"),"status":"preflight_only","shots":{},"native_pilot_authorized":False}
    for entry in matrix(c)["include"]:
        t=json.loads(entry["task"]);sid=t["shot"];src=chunks/sid
        if src.exists():copytree(src,out/sid,dirs_exist_ok=True)
        if not (src/"manifest.json").is_file():
            report["shots"][sid]={"status":"unmeasured","reason":"missing preflight manifest"};continue
        m=read(src/"manifest.json");rs=m["rows"];n=t["end"]-t["start"]
        assert m["preflight_only"] is True and m["engine"]=="EEVEE" and not m["denoising"]
        assert [x["frame"] for x in rs]==list(range(t["start"],t["end"]))
        assert [x["frame"] for x in m["rendered"]]==sorted(set((t["start"],(t["start"]+t["end"])//2,t["end"]-1)))
        f=flow_report(rs,expected_frames=n)
        blocks={cid:max(x["actor_qc"][cid]["face_external"]["blocked"] for x in rs if cid in x["actor_qc"]) for cid in sorted({cid for x in rs for cid in x["actor_qc"]})}
        report["shots"][sid]={"status":"pass" if f["status"]=="numeric_pass" and all(v==0 for v in blocks.values()) else "flag","direction":f,"external_face_ray_blocks_max":blocks,"smoke_frames":m["rendered"],"extra":m.get("extra",{})}
    report["numerical_pass"]=all(s["status"]=="pass" for s in report["shots"].values())
    if a.audit and Path(a.audit).is_file():copy2(a.audit,out/"first_pilot_independent_audit.json")
    write(out/"preflight_qc.json",report)
    with Path(c["review_path"]).open("a") as f:
        f.write("\n## Round 6 retry 1 direction preflight run "+str(report["run_id"])+"\n")
        f.write("Geometry/flow preflight numerical pass: "+str(report["numerical_pass"])+". Three native still samples per shot, not full clips; visual review and native pilot still mandatory. Evidence: "+str(out/"preflight_qc.json")+"\n")
    paths=[p for p in sorted(out.rglob("*")) if p.is_file() and p.name!="SHA256SUMS"]
    (out/"SHA256SUMS").write_text("".join(sha(p)+"  "+str(p)+"\n" for p in paths))
    with Path(c["inventory_path"]).open("a") as f:f.write("\nRound 6 retry 1 preflight evidence:\n"+"\n".join(str(p) for p in paths+[out/"SHA256SUMS"])+"\n")
if __name__=="__main__":main()
