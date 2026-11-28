#!/usr/bin/env python3
"""Final release gate: combine only explicit, verified 60-frame production artifacts."""
import argparse, hashlib, json, subprocess
from pathlib import Path

def verify(root, entries, complete=True):
    shots=[e["shot"] for e in entries]
    assert len(shots)==len(set(shots)), "Duplicate shot entries"
    assert all(type(n) is int and 1<=n<=48 for n in shots)
    if complete: assert sorted(shots)==list(range(1,49)), "Missing release shots"
    evidence=[]
    for e in sorted(entries,key=lambda x:x["shot"]):
        n=e["shot"]; p=root/f"shot_{n:02d}"
        q=json.loads((p/"chunk_validation.json").read_text())
        m=json.loads((p/"manifest.json").read_text())
        g=json.loads((p/"geometry_all_frames.json").read_text())
        first=(n-1)*60+1; last=n*60
        assert q["shot"]==n and q["source_commit"]==e["source_commit"] and q["preflight_run"]==e["preflight_run"]
        assert q["passed"] is True and q["frames"]==60 and q["duration"]==2.5
        assert q["encoded_max_near_black_percent"]<=2
        assert hashlib.sha256((p/"preview.mp4").read_bytes()).hexdigest()==q["sha256"]
        assert m["mode"]=="render" and int(m["shot"]["id"])==n and m["frames"]==60
        assert m["resolution"]==[540,960] and m["fps"]==24 and m["engine"]=="EEVEE" and m["denoising"] is False
        assert m["geometry_pass"] and len(g)==60
        assert [x["frame"] for x in g]==list(range(first,last+1)) and all(x["pass"] for x in g)
        assert [x["global_frame"] for x in m["records"]]==list(range(first,last+1))
        assert max(x["near_black_percent"] for x in m["records"])<=2
        fs=sorted(p.glob("frame_*.png"))
        assert [int(x.stem.split("_")[-1]) for x in fs]==list(range(first,last+1))
        info=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-count_frames","-show_entries","stream=width,height,r_frame_rate,nb_read_frames","-of","json",str(p/"preview.mp4")]))
        v=info["streams"][0]
        assert (v["width"],v["height"],v["r_frame_rate"],int(v["nb_read_frames"]))==(540,960,"24/1",60)
        evidence.append({**e,"frames":60,"first":first,"last":last,"chunk_sha256":q["sha256"],"encoded_max_near_black_percent":q["encoded_max_near_black_percent"]})
        print("VERIFIED_PRODUCTION_CHUNK",n,flush=True)
    return evidence

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--chunks",required=True);a.add_argument("--release",required=True);a.add_argument("--output",required=True);a.add_argument("--narration")
    o=a.parse_args(); root=Path(o.chunks);out=Path(o.output);out.mkdir(parents=True,exist_ok=True)
    release=json.loads(Path(o.release).read_text())
    assert release["status"]=="ready_for_assembly"
    evidence=verify(root,release["shots"])
    (out/"release_evidence.json").write_text(json.dumps({"shots":evidence,"frames":2880,"fps":24,"duration":120},indent=2)+"\n")
    cmd=["python3","scripts/edit_bench.py","--chunks",str(root),"--output",str(out)]
    if o.narration:cmd.extend(["--narration",o.narration])
    subprocess.run(cmd,check=True)
    m=json.loads((out/"manifest.json").read_text())
    assert m["frame_count"]==2880 and m["duration"]==120 and m["fps"]==24
    assert hashlib.sha256((out/"the_bench.mp4").read_bytes()).hexdigest()==m["sha256"]
    print("COMPLETE_VISUAL_MASTER_VALIDATED",m["sha256"],flush=True)

if __name__=="__main__":main()
