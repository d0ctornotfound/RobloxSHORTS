#!/usr/bin/env python3
"""Replay locked motions; sample all 60 poses and render two angles at key phases."""
import argparse,json,sys,os,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from PIL import Image,ImageDraw
from render_clothing_character import studio,build_actor,render_view,font,cube,mat
from clothing_articulation import ArticulatedClothes,clearance_metrics
from r6_imported_cycles import Retarget
from library_locomotion import StrideLock
from character_motion_correction import apply_corrected
from chapter1_articulation import Articulation
from chapter1_round2 import pose as sit_pose,neutral_feet,seat_setup
from chapter1_round3 import pose as reach_pose
from r6_character import bounds,mesh_points

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--actor",choices=("lead","friend"),required=True)
    ap.add_argument("--motion",choices=("walk","wave","sit","reach"),required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,walls=studio()
    scene.render.resolution_x=scene.render.resolution_y=768
    scene.eevee.taa_render_samples=24
    scene.render.fps=30;scene.frame_start=1;scene.frame_end=60
    actor=build_actor(args.actor)
    light_origins={ob:ob.location.copy() for ob in scene.objects if ob.type=="LIGHT"}
    mode=args.motion;yaw=.20
    art=None;clothes=None;feet=None;seat=None;landing=None;lock=None
    if mode=="walk":
        lock=StrideLock(Retarget(actor),"walk_cycle",fps=30,yaw=yaw)
    elif mode in ("sit","reach"):
        assert os.environ.get("R6_KNEE_BLEND")=="1"
        art=Articulation(actor,legs=True,arms=(mode=="sit"))
        clothes=ArticulatedClothes(actor,art)
        feet=neutral_feet(actor,art,yaw)
        if mode=="sit":
            seat=seat_setup(actor,art,yaw,feet);top,c,wh=seat
            fixture=cube("Locked neutral seat fixture",(c.x,c.y,top/2),(wh[0],wh[1],top),mat("Seat grey",(.20,.25,.30)))
            fixture.rotation_euler.z=yaw
    samples=(0,10,20,30,40,50,59)
    views=("front","side")
    records=[]
    for f in range(60):
        scene.frame_set(f+1);u=f/59;t=f/30
        if mode=="walk":
            lock.step(t)
        elif mode=="wave":
            apply_corrected(actor,"wave",u,t,(0,0,0),yaw)
        else:
            fn=sit_pose if mode=="sit" else reach_pose
            p,landing=fn(actor,art,mode,u,t,yaw,feet,landing,seat)
            clothes.sync()
        bpy.context.view_layer.update()
        row={"frame":f+1,**clearance_metrics(actor,clothes)}
        if art:row.update(art.length_metrics())
        records.append(row)
        (out/"tracking_partial.json").write_text(json.dumps(records,indent=2))
        if f not in samples:continue
        # Camera follows only root translation, without changing body pose;
        # fixed scale and anatomical angles across the strip.
        lo,hi=bounds(v for ob in actor.skinned for v in mesh_points(ob))
        center=(lo+hi)*.5
        if mode=="walk":
            # Follow the moving actor with the studio rig, not just camera.
            # This is presentation only; the approved StrideLock path stays.
            shift=actor.root.location.copy();shift.z=0
            for light,original in light_origins.items():light.location=original+shift
            bpy.context.view_layer.update()
        for view,direction in (("front",Vector((0,-6,0))),("side",Vector((-6,0,0)))):
            from mathutils import Matrix
            d=Matrix.Rotation(yaw,3,"Z")@direction
            path=out/("%s_%02d.png"%(view,f+1))
            render_view(scene,cam,walls,actor,path,mode+"_"+view+"_"+str(f+1),center+d,center,3.2)
    for view in views:
        tile=420;board=Image.new("RGB",(tile*4,(tile+40)*2+55),(28,31,35));draw=ImageDraw.Draw(board)
        draw.text((18,8),args.actor.upper()+" / "+mode.upper()+" / "+view.upper(),font=font(30),fill="white")
        for i,f in enumerate(samples):
            x=(i%4)*tile;y=55+(i//4)*(tile+40)
            path=out/("%s_%02d.png"%(view,f+1))
            with Image.open(path) as im:board.paste(im.convert("RGB").resize((tile,tile),Image.Resampling.LANCZOS),(x,y))
            draw.text((x+12,y+tile+5),"FRAME %02d"%(f+1),font=font(21),fill="white")
        board.save(out/(view+"_strip.png"))
    manifest={"actor":args.actor,"motion":mode,"frames_evaluated":len(records),
        "rendered_samples":[f+1 for f in samples],"views":list(views),"engine":"EEVEE","denoising":False,
        "locked_motion_path":{"walk":"StrideLock/Retarget","wave":"apply_corrected","sit":"round2 pose + knee fabric","reach":"round3 pose + knee fabric"}[mode],
        "max_shell_source_gap":max(r["max_source_gap"] for r in records),
        "max_articulated_trim_tracking_error":max(r["max_articulated_trim_tracking_error"] for r in records),
        "tracking_pass":all(r["pass_tracking"] for r in records),
        "visual_clearance":"pending actual pixel inspection; source proximity alone does not prove absence of clipping",
        "records":records}
    if art:
        manifest["max_segment_length_change"]=max(r["max_segment_length_change"] for r in records)
        manifest["max_joint_gap"]=max(r["max_joint_gap"] for r in records)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("CLOTHING_CLEARANCE_COMPLETE",json.dumps({k:v for k,v in manifest.items() if k!="records"}),flush=True)
    assert manifest["tracking_pass"],"Shell tracking gate failed"
if __name__=="__main__":main()
