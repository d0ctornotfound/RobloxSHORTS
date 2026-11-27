from pathlib import Path
import json,shutil,subprocess,hashlib
import numpy as np
from rbxm_animation import parse
OUT=Path("imported");OUT.mkdir(exist_ok=True)
for job in Path("chunks").glob("imported-*"):
    for f in job.iterdir():
        if f.is_file():
            assert not (OUT/f.name).exists(),f
            shutil.copy2(f,OUT/f.name)
def read(n):return json.loads((OUT/(n+".json")).read_text())
source=parse(Path("assets/animations/run_walk_roblox.bin").read_bytes())
(OUT/"source_extraction.json").write_text(json.dumps(source,indent=2)+"\n")
walk,run=read("walk_cycle"),read("run_cycle")
assert walk["roundtrip"]["body_poses"]==run["roundtrip"]["body_poses"]==510
assert (OUT/"imported_cycles.blend").stat().st_size>1000
rows=[f for j in range(3) for f in read("clip"+str(j))["frames"]]
assert [f["frame"] for f in rows]==list(range(1,49))
assert all(abs(f["floor_z"])<.001 for f in rows)
assert all(b["root_x"]>a["root_x"] for a,b in zip(rows,rows[1:]))
subprocess.run(["ffmpeg","-y","-v","error","-framerate","12","-i",str(OUT/"frame_%04d.png"),"-vf","hqdn3d=2.5:2:3:2.5","-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(OUT/"imported_walk.mp4")],check=True)
v=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(OUT/"imported_walk.mp4")]))
assert int(v["streams"][0]["nb_frames"])==48 and abs(float(v["format"]["duration"])-4)<.01
pixels=np.frombuffer(subprocess.check_output(["ffmpeg","-v","error","-i",str(OUT/"imported_walk.mp4"),"-f","rawvideo","-pix_fmt","rgb24","-"]),dtype=np.uint8).reshape(48,640,360,3)
dark=(pixels.max(axis=-1)<=24).mean(axis=(1,2))*100
for f in (1,12,24,36,48):
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(OUT/"imported_walk.mp4"),"-vf",f"select=eq(n\\,{f-1})","-frames:v","1",str(OUT/f"walk_grab_{f:02d}.png")],check=True)
rec={"walk":walk,"run":run,"video":{"frames":48,"fps":12,"duration":4,"resolution":[360,640],"samples":16,"root_distance":rows[-1]["root_x"]-rows[0]["root_x"],"speed":read("clip0")["speed"],"playback_rate":read("clip0")["playback_rate"],"near_black_max_percent":float(dark.max()),"near_black_pass":bool(dark.max()<=2),"sha256":hashlib.sha256((OUT/"imported_walk.mp4").read_bytes()).hexdigest()}}
(OUT/"imported_manifest.json").write_text(json.dumps(rec,indent=2)+"\n")
print("IMPORTED_CYCLES_VALIDATED",json.dumps(rec))
