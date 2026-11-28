#!/usr/bin/env python3
"""Assemble only verified complete shot outputs. No synthetic voice or invented frames."""
import argparse,json,hashlib,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from library_story_plan import validate
def main():
    p=argparse.ArgumentParser();p.add_argument("--chunks",required=True);p.add_argument("--output",required=True);p.add_argument("--preflight",action="store_true");p.add_argument("--narration")
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    story=json.loads(Path("stories/the_bench_plan.json").read_text());print(validate(story))
    files={};records={}
    for f in Path(a.chunks).rglob("manifest.json"):
        m=json.loads(f.read_text());i=int(m["shot"]["id"]);records[i]=m
        for x in f.parent.glob("frame_*.png"):
            n=int(x.stem.split("_")[-1]);assert n not in files;files[n]=x
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",20)
    for act in range(1,7):
        shots=[s for s in story["shots"] if s["act"]==act and int(s["id"]) in records]
        if not shots:continue
        w,h=180,320;board=Image.new("RGB",(w*4,(h+32)*((len(shots)+3)//4)+40),(30,34,38));d=ImageDraw.Draw(board)
        d.text((12,9),"THE BENCH / ACT %d / ACTUAL RENDERS"%act,font=font,fill="white")
        for j,s in enumerate(shots):
            m=records[int(s["id"])];f=m["records"][len(m["records"])//2]["global_frame"]
            x=j%4*w;y=j//4*(h+32)+40
            with Image.open(files[f]) as im:board.paste(im.convert("RGB").resize((w,h),Image.Resampling.LANCZOS),(x,y))
            d.text((x+6,y+h+3),"%s | %05.1fs"%(s["id"],s["start"]),font=font,fill="white")
        board.save(out/("act_%d_contact.png"%act))
    if a.preflight:return
    expected=round(story["duration"]*story["fps"]);assert sorted(files)==list(range(1,expected+1))
    assert len(records)==48 and all(m["mode"]=="render" for m in records.values())
    frames=out/"caption_frames";frames.mkdir(exist_ok=True)
    capfont=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",44)
    for s in story["shots"]:
        first=round(s["start"]*24)+1;last=round(s["end"]*24);words=s["narration_beat"].split()
        for f in range(first,last+1):
            word=words[min(len(words)-1,(f-first)*len(words)//(last-first+1))]
            with Image.open(files[f]) as src:
                im=src.convert("RGB");d=ImageDraw.Draw(im);d.text((270,766),word,font=capfont,anchor="mm",fill="white",stroke_width=3,stroke_fill="#404040");im.save(frames/("frame_%04d.png"%f))
    video=out/"the_bench.mp4"
    cmd=["ffmpeg","-y","-framerate","24","-i",str(frames/"frame_%04d.png")]
    if a.narration:cmd+=["-i",a.narration,"-map","0:v:0","-map","1:a:0","-af","apad","-c:a","aac","-b:a","160k"]
    cmd+=["-t","120","-c:v","libx264","-crf","16","-pix_fmt","yuv420p","-movflags","+faststart",str(video)]
    subprocess.run(cmd,check=True)
    manifest={"resolution":[540,960],"frame_count":expected,"fps":24,"duration":120,"voice":"user-provided" if a.narration else "none; estimated caption timing","sha256":hashlib.sha256(video.read_bytes()).hexdigest(),"shots":[{"id":s["id"],"first":round(s["start"]*24)+1,"last":round(s["end"]*24)} for s in story["shots"]]}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(video)],check=True,stdout=(out/"ffprobe.json").open("w"))
    subprocess.run(["python3","scripts/validate_story_pixels.py","--video",str(video),"--manifest",str(out/"manifest.json"),"--output",str(out/"encoded_darkness.json")],check=True)
if __name__=="__main__":main()
