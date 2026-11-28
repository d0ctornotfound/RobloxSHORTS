"""Encode a labeled, narration-timed held-still animatic. Missing actual stills are fatal."""
import argparse, json, subprocess, tempfile
from pathlib import Path
from validate_shot_plan import validate

def main():
    a=argparse.ArgumentParser();a.add_argument("plan");a.add_argument("--output",required=True);args=a.parse_args()
    root=Path(".");p=json.loads(Path(args.plan).read_text());validate(p,root)
    shots=p["shots"];missing=[s["still_path"] for s in shots if not Path(s["still_path"]).is_file()]
    if missing: a.exit(1,"ANIMATIC FAIL: missing shot stills:\n"+"\n".join(missing)+"\n")
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);fps=p["fps"]
    vf="scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,setsar=1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text=ANIMATIC:x=(w-tw)/2:y=36:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.8"
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);segments=[]
        for s in shots:
            frames=round(s["edit_out"]*fps)-round(s["edit_in"]*fps)
            if frames<=0: raise ValueError("Shot shorter than one encoded frame: "+s["id"])
            dst=temp/(s["id"]+".mp4")
            subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-loop","1","-framerate",str(fps),"-i",s["still_path"],"-vf",vf,"-frames:v",str(frames),"-c:v","libx264","-pix_fmt","yuv420p",str(dst)],check=True)
            segments.append("file '"+str(dst)+"'\n")
        listing=temp/"concat.txt";listing.write_text("".join(segments))
        subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-f","concat","-safe","0","-i",str(listing),"-i",p["narration_audio"],"-c:v","copy","-c:a","aac","-movflags","+faststart",str(output)],check=True)
    meta={"tier":"animatic","label":"ANIMATIC","held_stills":True,"distinct_rendered_samples_per_second":None,"encoded_fps":fps,"narration_source":p["narration_source"],"audio_duration":p["audio_duration"],"frames":round(p["audio_duration"]*fps),"note":"Stills and held poses; not motion proof or final film."}
    output.with_suffix(".json").write_text(json.dumps(meta,indent=2)+"\n")
if __name__=="__main__":main()
