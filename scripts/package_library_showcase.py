"""Verify and package actual showcase renders; preserve raw proof and hashes."""
from pathlib import Path
import json,shutil,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
from library_story_plan import validate
ROOT=Path("chunks");OUT=Path("showcase");OUT.mkdir(exist_ok=True)
for job in ROOT.glob("library-*"):
    for f in job.iterdir():
        if f.is_file():
            assert not (OUT/f.name).exists(),f
            shutil.copy2(f,OUT/f.name)
def read(n):return json.loads((OUT/(n+".json")).read_text())
def sheet(names,output,columns=2):
    ims=[Image.open(OUT/(x+".png")).convert("RGB") for x in names]
    w=max(i.width for i in ims);h=max(i.height for i in ims)
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",25)
    rows=(len(ims)+columns-1)//columns;canvas=Image.new("RGB",(columns*w,rows*(h+42)),(22,29,39));d=ImageDraw.Draw(canvas)
    for k,(im,name) in enumerate(zip(ims,names)):
        x=(k%columns)*w;y=(k//columns)*(h+42)
        canvas.paste(im,(x+(w-im.width)//2,y));d.text((x+12,y+h+6),name.replace("_"," ").upper(),font=font,fill="white")
    canvas.save(OUT/output)
actions=[a for i in range(3) for a in read("poses"+str(i))["actions"]]
props=[a for i in range(3) for a in read("props"+str(i))["props"]]
assert len(actions)==18 and len(set(a["action"] for a in actions))==18
assert len(props)==21 and len(set(p["kind"] for p in props))==21
assert all(p["mesh_count"]>0 for p in props)
clips=[read("clip"+str(i)) for i in range(6)]
assert all(c["action"]=="walk_cycle" and c["source_sha256"]=="a05aa15bd6cc28b739c53208c69037bc547bbb731e78d200393468a26029d2d4" for c in clips)
frames=[f for c in clips for f in c["frames"]]
assert all(f["torso_z_bounds"][0]-.035<=f["star_height"]<=f["torso_z_bounds"][1]+.035 for f in frames)
for action in ("walk_cycle","run_cycle"):
    proof=read(action);assert proof["roundtrip"]["body_poses"]==510 and (OUT/(action+"_strip.png")).exists()
assert [f["frame"] for f in frames]==list(range(1,145))
assert all(abs(f["foot_min_z"])<.001 for f in frames)
assert frames[0]["night"]==0 and frames[-1]["night"]==1
assert abs(frames[-1]["x"]-frames[0]["x"]-20)<1e-6
assert all((OUT/("frame_%04d.png"%i)).exists() for i in range(1,145))
subprocess.run(["ffmpeg","-y","-v","error","-framerate","12","-i",str(OUT/"frame_%04d.png"),"-vf","hqdn3d=2.5:2:3:2.5","-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(OUT/"library_showcase.mp4")],check=True)
probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(OUT/"library_showcase.mp4")]))
v=probe["streams"][0];assert int(v["nb_frames"])==144 and abs(float(probe["format"]["duration"])-12)<.01
assert (v["width"],v["height"])==(360,640)
raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(OUT/"library_showcase.mp4"),"-f","rawvideo","-pix_fmt","rgb24","-"])
import numpy as np
pixels=np.frombuffer(raw,dtype=np.uint8).reshape(144,640,360,3)
black=(pixels.max(axis=-1)<=24).mean(axis=(1,2))*100
# This is an atmosphere proof, not a story edit; do not silently hide failures.
dark={"maximum_percent":float(black.max()),"worst_frame":int(black.argmax()+1),"pass":bool(black.max()<=2),"per_frame":black.tolist()}
for f in (1,37,73,109,144):
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(OUT/"library_showcase.mp4"),"-vf",f"select=eq(n\\,{f-1})","-frames:v","1",str(OUT/f"clip_grab_{f:02d}.png")],check=True)
sheet(["sky_"+x for x in ("morning","midday","golden_hour","dusk","night","overcast","rain")],"atmosphere_sheet.png",4)
sheet(["fx_"+x for x in ("rain","snow","sparkles","confetti","dust","shake")],"effects_sheet.png",3)
sheet(["room_cafe","room_classroom"],"rooms_sheet.png",2)
sheet([f"clip_grab_{f:02d}" for f in (1,37,73,109,144)],"clip_sheet.png",5)
example=Path("examples/library_story_plan.json");plan=validate(json.loads(example.read_text()));shutil.copy2(example,OUT/"story_plan.json")
rec={"actions":actions,"props":props,"atmospheres":[read("sky_"+x) for x in ("morning","midday","golden_hour","dusk","night","overcast","rain")],"effects":read("effects"),"character":read("characters"),"story_plan":plan,"video":{"resolution":[360,640],"fps":12,"frames":144,"duration":12,"samples":16,"action":"walk_cycle","source_sha256":clips[0]["source_sha256"],"speed":clips[0]["speed"],"playback_rate":clips[0]["playback_rate"],"calibration":clips[0]["calibration"],"minimum_hero_vertical_coverage":min(f["actor_bounds"][3]-f["actor_bounds"][2] for f in frames),"maximum_ground_error":max(abs(f["foot_min_z"]) for f in frames),"audio":False,"near_black":dark,"sha256":hashlib.sha256((OUT/"library_showcase.mp4").read_bytes()).hexdigest()},"files":{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.glob("*.png") if not f.name.startswith("frame_")}}
(OUT/"showcase_manifest.json").write_text(json.dumps(rec,indent=2)+"\n")
print("LIBRARY_SHOWCASE_VALIDATED",json.dumps({"actions":len(actions),"props":len(props),"plan":plan,"video":{k:v for k,v in rec["video"].items() if k!="near_black"},"near_black":{k:v for k,v in dark.items() if k!="per_frame"}}))
