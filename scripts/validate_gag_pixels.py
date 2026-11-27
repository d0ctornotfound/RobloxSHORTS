"""Validate decoded final pixels, including payoff motion; no threshold relaxation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    m=json.loads(a.manifest.read_text());w,h=m["resolution"];fps=m["fps"];count=m["frame_count"]
    raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(a.video),"-f","rawvideo","-pix_fmt","rgb24","-"])
    assert len(raw)==count*w*h*3
    rgb=np.frombuffer(raw,dtype=np.uint8).reshape(count,h,w,3)
    dark=(rgb.max(axis=3)<=24).mean(axis=(1,2))*100
    rows=m["rows"];assert len(rows)==count
    by_shot={}
    for shot in dict.fromkeys(r["shot"] for r in rows):
        indices=[i for i,r in enumerate(rows) if r["shot"]==shot]
        worst=max(indices,key=lambda i:dark[i])
        by_shot[shot]={"frames":len(indices),"maximum_percent":float(dark[worst]),"worst_frame":worst+1,"fail_count":int(sum(dark[i]>2 for i in indices))}
    # Evaluate consecutive frames within the actual performance beat only.
    # Crop to union of projected hero bounds so background alone cannot pass.
    indices=[i for i,r in enumerate(rows) if r["shot"]=="laugh_single"]
    assert len(indices)>=48 and indices==list(range(indices[0],indices[-1]+1))
    b=[rows[i]["bounds"][0]["bounds"] for i in indices]
    x0=max(0,int(min(v[0] for v in b)*w));x1=min(w,int(np.ceil(max(v[1] for v in b)*w)))
    y0=max(0,int((1-max(v[3] for v in b))*h));y1=min(h,int(np.ceil((1-min(v[2] for v in b))*h)))
    assert x1>x0 and y1>y0
    crop=rgb[indices,y0:y1,x0:x1,:].astype(np.int16)
    d=np.abs(np.diff(crop,axis=0));whole=np.abs(np.diff(rgb[indices].astype(np.int16),axis=0))
    mae=d.mean(axis=(1,2,3));changed=(d.max(axis=3)>=8).mean(axis=(1,2))*100
    exact=np.all(whole==0,axis=(1,2,3))
    # Pose metadata is a separate guard against render noise passing the hold
    # test: sustained bone angles/arm directions must vary as well as pixels.
    def pose_vector(row):
        b=row["friend_beat"]
        assert b["beat"]=="sustained_laugh"
        return b["head_euler"]+b["torso_euler"]+sum(b["arm_directions"],[])
    poses=np.asarray([pose_vector(rows[i]) for i in indices])
    pose_step=np.max(np.abs(np.diff(poses,axis=0)),axis=1)
    static=(mae<.10)|(changed<.10)|(pose_step<1e-5)
    longest=run=0
    for x in static:
        run=run+1 if x else 0;longest=max(longest,run)
    motion={"first_frame":indices[0]+1,"last_frame":indices[-1]+1,"frames":len(indices),"pairs":len(mae),
       "roi_xyxy":[x0,y0,x1,y1],"identical_full_frame_pairs":int(exact.sum()),"near_static_pairs":int(static.sum()),
       "max_near_static_run_pairs":longest,"max_near_static_hold_seconds":longest/fps,
       "roi_mean_absolute_difference_8bit":{"min":float(mae.min()),"mean":float(mae.mean()),"max":float(mae.max())},
       "roi_pixels_changed_ge8_percent":{"min":float(changed.min()),"mean":float(changed.mean()),"max":float(changed.max())},
       "minimum_pose_step":float(pose_step.min()),"pass":longest/fps<=.5,
       "per_pair":[{"from_frame":i+1,"to_frame":i+2,"roi_mae":float(mae[j]),"changed_percent":float(changed[j]),"pose_step":float(pose_step[j]),"near_static":bool(static[j])} for j,i in enumerate(indices[:-1])]}
    reused=[r["frame"] for r in rows if r.get("reused_from_run")==45936954946]
    assert reused==list(range(126,147)),reused
    result={"frames":count,"max_near_black_percent":float(dark.max()),"worst_frame":int(dark.argmax())+1,"fail_count":int((dark>2).sum()),"per_frame_percent":dark.tolist(),"per_shot":by_shot,"darkness_pass":bool(dark.max()<=2),"laugh_motion":motion,"reused_insert_frames":reused,"pass":bool(dark.max()<=2 and motion["pass"]),"sha256":hashlib.sha256(a.video.read_bytes()).hexdigest()}
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print("GAG_FINAL_VALIDATION",json.dumps({k:v for k,v in result.items() if k!="per_frame_percent" and k!="laugh_motion"}),flush=True)
    print("LAUGH_MOTION",json.dumps({k:v for k,v in motion.items() if k!="per_pair"}),flush=True)
    assert result["pass"],(result["max_near_black_percent"],motion["pass"])
if __name__=="__main__":main()
