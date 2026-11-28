"""Encode a labeled narration-timed animatic from held renders and optional actual proof clips.
Missing input, invalid segment coverage or incorrect video rate is fatal. No final-film mode.
"""
import argparse,json,subprocess,tempfile
from fractions import Fraction
from pathlib import Path
from validate_shot_plan import validate

def probe(path):
    p=subprocess.run(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(path)],check=True,capture_output=True,text=True)
    return json.loads(p.stdout)

def segments(plan):
    fps=plan["fps"];rows=[]
    for s in plan["shots"]:
        start=round(s["edit_in"]*fps);end=round(s["edit_out"]*fps);n=end-start
        segs=s.get("animatic_segments") or [{"fraction_start":0,"fraction_end":1,"still_path":s["still_path"]}]
        last=0
        for i,x in enumerate(segs):
            a=round(float(x["fraction_start"])*n);b=round(float(x["fraction_end"])*n)
            if a!=last or b<=a or b>n:raise ValueError(s["id"]+": invalid internal segment coverage")
            still=x.get("still_path");video=x.get("video_path")
            if bool(still)==bool(video):raise ValueError("Exactly one still or motion source required")
            rows.append(dict(shot=s["id"],segment=i,first=start+a,last=start+b,frames=b-a,still_path=still,video_path=video,video_start_frame=int(x.get("video_start_frame",0))))
            last=b
        if last!=n:raise ValueError(s["id"]+": segment gap")
    if rows[0]["first"]!=0 or any(a["last"]!=b["first"] for a,b in zip(rows,rows[1:])):raise ValueError("Edit frame gap")
    return rows

def main():
    a=argparse.ArgumentParser();a.add_argument("plan");a.add_argument("--output",required=True);args=a.parse_args()
    root=Path(".");p=json.loads(Path(args.plan).read_text());validate(p,root);rows=segments(p)
    missing=[x["still_path"] or x["video_path"] for x in rows if not Path(x["still_path"] or x["video_path"]).is_file()]
    if missing:a.exit(1,"ANIMATIC FAIL: missing actual inputs:\n"+"\n".join(sorted(set(missing)))+"\n")
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);fps=p["fps"]
    vf="scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,setsar=1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text=ANIMATIC:x=(w-tw)/2:y=36:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.8"
    cache={}
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);listing=[]
        for j,s in enumerate(rows):
            dst=temp/(f"{j:03d}.mp4");frames=s["frames"]
            if s["video_path"]:
                source=s["video_path"]
                if source not in cache:
                    cache[source]=next(x for x in probe(source)["streams"] if x["codec_type"]=="video")
                info=cache[source]
                if Fraction(info["avg_frame_rate"])!=fps:raise ValueError(source+": not native target rate")
                begin=s["video_start_frame"]
                if begin<0 or begin+frames>int(info["nb_read_frames"]):raise ValueError(source+": clip range unavailable")
                inputs=["-i",source];filters=f"trim=start_frame={begin}:end_frame={begin+frames},setpts=PTS-STARTPTS,"+vf
            else:
                inputs=["-loop","1","-framerate",str(fps),"-i",s["still_path"]];filters=vf
            subprocess.run(["ffmpeg","-nostdin","-v","error","-y",*inputs,"-an","-vf",filters,"-frames:v",str(frames),"-c:v","libx264","-pix_fmt","yuv420p","-r",str(fps),"-video_track_timescale","90000",str(dst)],check=True)
            actual=next(x for x in probe(dst)["streams"] if x["codec_type"]=="video")
            if int(actual["nb_read_frames"])!=frames:raise ValueError(f"segment {j}: wrong encoded frame count")
            listing.append("file '"+str(dst)+"'\n")
        concat=temp/"concat.txt";concat.write_text("".join(listing))
        subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-f","concat","-safe","0","-i",str(concat),"-i",p["narration_audio"],"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-movflags","+faststart",str(output)],check=True)
    actual=probe(output);v=next(x for x in actual["streams"] if x["codec_type"]=="video");audio=next(x for x in actual["streams"] if x["codec_type"]=="audio")
    expected=round(p["audio_duration"]*fps)
    if int(v["nb_read_frames"])!=expected or Fraction(v["avg_frame_rate"])!=fps or abs(float(audio["duration"])-p["audio_duration"])>1/fps:raise ValueError("Final animatic timeline mismatch")
    meta={"tier":"animatic","label":"ANIMATIC","held_stills":True,"held_segments":sum(bool(s["still_path"]) for s in rows),"motion_segments":sum(bool(s["video_path"]) for s in rows),"distinct_rendered_samples_per_second":"varies; held stills and native proof clips are explicitly separated","encoded_fps":fps,"narration_source":p["narration_source"],"audio_duration":p["audio_duration"],"frames":expected,"segments":rows,"ffprobe":actual,"note":"Stills and held poses with selected motion proofs; not a final film."}
    output.with_suffix(".json").write_text(json.dumps(meta,indent=2)+"\n")
if __name__=="__main__":main()
