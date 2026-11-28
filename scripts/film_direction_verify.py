"""Independent native pilot verification on fresh exact publication commit.
No approval is inferred from pixel statistics or sample sheets."""
import argparse,json,os,subprocess
from pathlib import Path
from film_direction_compare import verify,pixel_rows,summarize,read,sha
from film_timeline import run

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--evidence",required=True);a=p.parse_args()
    c=read(a.config);out=Path(c["output_dir"]);qc=read(out/"pilot_qc.json");plan=read(c["plan"]);n=round(plan["audio_duration"]*30)
    assert subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()==a.evidence
    dest=out/"independent";dest.mkdir(parents=True,exist_ok=True)
    baseline=verify(c["pilot_baseline"],n,c.get("pilot_baseline_sha256"));old=pixel_rows(c["pilot_baseline"],n)
    report={"evidence_commit":a.evidence,"qc_sha256":sha(out/"pilot_qc.json"),"baseline":baseline,"run_id":os.environ.get("GITHUB_RUN_ID"),"clips":{},"shots":{},"visual_review_required":True}
    for name,g in qc["groups"].items():
        if g.get("missing_chunks") or not g.get("clip"):raise ValueError("native pilot incomplete "+name)
        clip=Path(g["clip"]);info=verify(clip,g["frames"],g["sha256"]);new=pixel_rows(clip,g["frames"])
        start=min(s["start"] for s in g["shots"].values());report["clips"][name]=info
        for sid,s in g["shots"].items():
            lo,hi=s["start"],s["end"];indices=sorted(set(lo+round((hi-lo-1)*i/5) for i in range(6)))
            frames=[]
            for k in indices:
                path=dest/f"{sid}_{k:05d}.png"
                run(["ffmpeg","-y","-v","error","-i",str(clip),"-vf",f"select=eq(n\\,{k-start})","-frames:v","1",str(path)])
                frames.append(str(path))
            report["shots"][sid]={"before":summarize(old[lo:hi]),"after":summarize(new[lo-start:hi-start]),"direction":s["direction"],"review_frames":frames}
    (dest/"audit.json").write_text(json.dumps(report,indent=2)+"\n")
    paths=sorted(p for p in dest.iterdir() if p.is_file() and p.name!="SHA256SUMS")
    (dest/"SHA256SUMS").write_text("".join(sha(p)+"  "+str(p)+"\n" for p in paths))
if __name__=="__main__":main()
