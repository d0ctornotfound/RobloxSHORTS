"""Dedicated sleep review, no other motion clips or render-profile changes."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from PIL import Image,ImageChops,ImageFilter,ImageStat
from render_character_correction import studio
from render_demo import point_at
from library_character import character
from library_camera import metrics
from character_motion_correction import apply_corrected
from sleep_supine import sleep_diagnostics
FPS=30
N=120

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--smoke",action="store_true")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,lights=studio();actor=character("Sleep lead","lead")
    # Elevated side three-quarter camera makes the face-up orientation observable.
    cam.location=(6,-4.5,5.7);point_at(cam,Vector((0,.25,1.05)));cam.data.ortho_scale=4.8
    rows=[];maes=[];prev=None
    frames=[N-1] if args.smoke else range(N)
    for f in frames:
        scene.frame_set(f+1);u=f/(N-1);t=f/FPS
        pose=apply_corrected(actor,"sleep",u,t,(0,0,0),.25)
        actor.pose("neutral")
        bpy.context.view_layer.update()
        b=metrics(scene,cam,[actor]);assert all(x["body_safe"] for x in b),(f,b)
        row={"frame":f+1,"seconds":t,**pose,**sleep_diagnostics(actor),"bounds":b}
        rows.append(row)
        path=out/f"frame_{f+1:04d}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        assert path.is_file() and path.stat().st_size>0
        with Image.open(path) as im:
            gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
        if prev is not None:maes.append(ImageStat.Stat(ImageChops.difference(prev,gray)).mean[0])
        prev=gray
    if args.smoke:
        (out/"smoke.json").write_text(json.dumps({"frame":N,"fps":FPS,"samples":scene.cycles.samples,"denoising":scene.cycles.use_denoising,"pose":rows[0],"render_pass":True},indent=2))
        return
    supine=[x for x in rows if x["phase"]=="supine_breathing"]
    seated=[x for x in rows if x["phase"]=="ground_sit"]
    count=sum(x<.25 for x in maes)
    report={"action":"sleep","role":"lead","frames":N,"fps":FPS,"rows":rows,"near_static":{"threshold_mae":.25,"count":count,"transitions":len(maes),"fraction":count/len(maes),"maes":maes},
            "supine":{"face_up_dot_min":min(x["face_up_dot"] for x in supine),"max_abs_floor_error":max(abs(x["support_z"]["all"]) for x in rows),"max_torso_floor_gap":max(x["support_z"]["torso"] for x in supine),"max_head_with_hair_floor_gap":max(x["support_z"]["head_with_hair"] for x in supine),"chest_height_range":max(x["chest_max_z"] for x in supine)-min(x["chest_max_z"] for x in supine),"ground_sit_torso_gap":max(x["support_z"]["torso"] for x in seated)},
            "visual_review_pending":True}
    s=report["supine"]
    report["correction_gates"]={"performance_motion":count/len(maes)<=.40,"face_up":s["face_up_dot_min"]>=.95,"floor_contact":s["max_abs_floor_error"]<=.002,"ground_sit_support":s["ground_sit_torso_gap"]<=.06,"supine_torso_support":s["max_torso_floor_gap"]<=.06,"supine_head_support":s["max_head_with_hair_floor_gap"]<=.06,"breathing_geometry":s["chest_height_range"]>=.012}
    (out/"metrics.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
