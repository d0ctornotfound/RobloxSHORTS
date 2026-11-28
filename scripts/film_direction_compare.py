"""Independent committed-video audit for director pilots and full films.

Run against a fresh checkout of the exact evidence commit, not render artifacts.
Pixel statistics are descriptive, not a substitute for visual review or a
skeletal motion measurement. The original narration timing is never modified.
"""
import argparse, hashlib, json, subprocess
from fractions import Fraction
from pathlib import Path

FPS=30
WIDTH,HEIGHT=540,960
SMALL_W,SMALL_H=54,96
STRIDE=SMALL_W*SMALL_H*3

def read(p): return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def capture(cmd): return subprocess.check_output(cmd)
def verify(path,frames,expected_hash=None):
    p=Path(path)
    digest=sha(p)
    if expected_hash is not None and digest!=expected_hash:
        raise ValueError("checksum mismatch: "+str(p))
    probe=json.loads(capture(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(p)]))
    v=next(x for x in probe["streams"] if x["codec_type"]=="video")
    assert (v["width"],v["height"])==(WIDTH,HEIGHT)
    assert Fraction(v["avg_frame_rate"])==FPS and Fraction(v["r_frame_rate"])==FPS
    assert int(v["nb_read_frames"])==frames
    audio=next(x for x in probe["streams"] if x["codec_type"]=="audio")
    assert abs(float(audio["duration"])-frames/FPS)<.08
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(p),"-f","null","-"],check=True)
    return {"path":str(p),"sha256":digest,"frames":frames,"duration":frames/FPS,"bytes":p.stat().st_size,"resolution":[WIDTH,HEIGHT],"fps":FPS,"audio_duration":float(audio["duration"]),"full_decode":"pass"}

def pixel_rows(path,frames):
    # Decode every frame once. Downscaled RGB statistics are deliberately
    # labeled as an approximate, composition-sensitive grade proxy.
    data=capture(["ffmpeg","-v","error","-i",str(path),"-map","0:v:0","-vf",f"scale={SMALL_W}:{SMALL_H}:flags=area,format=rgb24","-fps_mode","passthrough","-f","rawvideo","-pix_fmt","rgb24","-"])
    assert len(data)==STRIDE*frames
    hashes=capture(["ffmpeg","-v","error","-i",str(path),"-map","0:v:0","-f","framemd5","-"]).decode().splitlines()
    hashes=[l.rsplit(",",1)[-1].strip() for l in hashes if l and not l.startswith("#")]
    assert len(hashes)==frames
    rows=[]
    for i in range(frames):
        frame=memoryview(data)[i*STRIDE:(i+1)*STRIDE]
        sat=warm=luma=dark=0
        count=STRIDE//3
        for j in range(0,STRIDE,3):
            r,g,b=frame[j:j+3]
            hi=max(r,g,b);lo=min(r,g,b)
            sat+=(hi-lo)/hi if hi else 0
            warm+=(r-b)/255
            luma+=(.2126*r+.7152*g+.0722*b)/255
            dark+=hi<=24
        rows.append({"saturation":sat/count,"warm_red_minus_blue":warm/count,"luma":luma/count,"near_black_fraction":dark/count,"hash":hashes[i]})
    return rows

def summarize(rows):
    assert rows
    keys=("saturation","warm_red_minus_blue","luma","near_black_fraction")
    return {"frames":len(rows),**{k:sum(x[k] for x in rows)/len(rows) for k in keys},"consecutive_exact_duplicates":sum(a["hash"]==b["hash"] for a,b in zip(rows,rows[1:]))}

def shot_ranges(plan):
    for s in plan["shots"]:
        yield s["id"],round(s["edit_in"]*FPS),round(s["edit_out"]*FPS)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True);ap.add_argument("--baseline",required=True)
    ap.add_argument("--baseline-sha");ap.add_argument("--pilot-qc");ap.add_argument("--candidate");ap.add_argument("--candidate-sha")
    ap.add_argument("--out",required=True);a=ap.parse_args()
    plan=read(a.plan);n=round(plan["audio_duration"]*FPS)
    baseline=verify(a.baseline,n,a.baseline_sha)
    old=pixel_rows(a.baseline,n)
    report={"baseline":baseline,"scope":"fresh committed video files; pixel grade proxies depend on composition; no motion or visual acceptance inferred","shots":{}}
    ranges={sid:(start,end) for sid,start,end in shot_ranges(plan)}
    if a.pilot_qc:
        pilot=read(a.pilot_qc);report["clips"]={}
        for name,g in pilot["groups"].items():
            if not g.get("clip"):continue
            ids=list(g["shots"]);lo=ranges[ids[0]][0];hi=ranges[ids[-1]][1]
            path=g["clip"];report["clips"][name]=verify(path,hi-lo,g["sha256"])
            new=pixel_rows(path,hi-lo)
            for sid in ids:
                start,end=ranges[sid]
                report["shots"][sid]={"start_frame":start,"end_frame":end,"before":summarize(old[start:end]),"after":summarize(new[start-lo:end-lo]),"direction_after":g["shots"][sid]["direction"]}
    elif a.candidate:
        report["candidate"]=verify(a.candidate,n,a.candidate_sha)
        new=pixel_rows(a.candidate,n)
        for sid,(start,end) in ranges.items():report["shots"][sid]={"start_frame":start,"end_frame":end,"before":summarize(old[start:end]),"after":summarize(new[start:end])}
    else:raise ValueError("provide --pilot-qc or --candidate")
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
