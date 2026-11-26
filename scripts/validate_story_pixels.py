"""Measure every decoded video frame, including captions; no image edits."""
import argparse,json,subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    m=json.loads(Path(a.manifest).read_text())
    w,h=m["resolution"];size=w*h*3
    proc=subprocess.Popen(["ffmpeg","-v","error","-i",a.video,"-map","0:v:0","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
    vals=[]
    while True:
        buf=proc.stdout.read(size)
        if not buf:break
        assert len(buf)==size
        n=sum(r<=24 and g<=24 and b<=24 for r,g,b in zip(buf[::3],buf[1::3],buf[2::3]))
        vals.append(n/(w*h))
    assert proc.wait()==0
    assert len(vals)==m["frame_count"]
    shots=[]
    for s in m["shots"]:
        chunk=vals[s["first"]-1:s["last"]]
        shots.append({"id":s["id"],"frames":len(chunk),"max_near_black_percent":100*max(chunk),"mean_near_black_percent":100*sum(chunk)/len(chunk),"worst_frame":s["first"]+chunk.index(max(chunk))})
    result={"definition":"decoded RGB max channel <=24/255, including captions","limit_percent":2,"shots":shots,"per_frame_percent":[100*v for v in vals]}
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n")
    print("NEAR_BLACK_VALIDATION",json.dumps(shots),flush=True)
    assert all(x["max_near_black_percent"]<=2 for x in shots),shots

if __name__=="__main__":main()
