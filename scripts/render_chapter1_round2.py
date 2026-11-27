"""One independent 60-frame 30fps correction clip per runner. Evidence first."""
import argparse,json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from PIL import Image,ImageFilter,ImageChops,ImageStat
from render_character_correction import studio
from render_demo import cube,point_at
from library_camera import metrics
from library_character import character
from r6_character import matte
from character_motion import floor,soles
from character_motion_correction import rear_hip
from chapter1_articulation import Articulation
from chapter1_round2 import pose,neutral_feet,seat_setup,mouth_pose,hug

CLIPS=[("lead","jump"),("friend","jump"),("lead","sit"),("lead","stand_up"),("lead","reach"),("lead","point"),("lead","eat"),("lead","drink"),("lead","hug"),("lead","fall")]
N=60;FPS=30
def main():
    p=argparse.ArgumentParser();p.add_argument("--part",type=int,required=True);p.add_argument("--output",required=True);p.add_argument("--smoke",action="store_true")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    role,name=CLIPS[args.part];clip=out/f"{args.part:02d}_{role}_{name}";clip.mkdir(exist_ok=True)
    scene,cam,lights=studio();actor=character("Round two "+role,role)
    partner=character("Round two friend","friend") if name=="hug" else None
    art=Articulation(actor,legs=name in ("jump","sit","stand_up","reach","point","fall"),arms=name in ("sit","stand_up","eat","drink")) if not partner else None
    yaw=.20;feet=neutral_feet(actor,art,yaw) if art and art.legs else None
    seat=None;cup=None
    if name in ("sit","stand_up"):
        seat=seat_setup(actor,art,yaw,feet);top,c,wh=seat
        assert top>.05,(top,c,wh)
        ob=cube("Studio seat contact fixture",(c.x,c.y,top/2),(wh[0],wh[1],top),matte("Neutral seat",(.20,.25,.30)),bevel=0);ob.rotation_euler.z=yaw
    if name=="drink":
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.085,depth=.20)
        cup=bpy.context.object;cup.name="Studio sip contact cup";cup.data.materials.append(matte("Cup muted teal",(.13,.34,.36)))
    # Camera remains stable across the entire shot. Seat gets a side view;
    # mouth gestures are viewed from opposite the acting arm.
    cam.location=(6,-8,3.2) if seat else (6,-8,3.1) if name in ("eat","drink") else (0,-10,3.1) if partner else (3,-10,2.9)
    point_at(cam,Vector((0,0,1.15 if seat or name=="fall" else 1.35)));cam.data.ortho_scale=5.0 if partner else 4.2
    rows=[];maes=[];previous=None;landing=None;land_soles=None
    frames=range(N)
    for f in frames:
        scene.frame_set(f+1);u=f/(N-1);t=f/FPS
        if partner:p=hug(actor,partner,u,t)
        else:
            p,landing=pose(actor,art,name,u,t,yaw,feet,landing,seat)
            actor.pose("shocked" if name=="fall" and .18<u<.80 else "happy" if name=="jump" and .25<u<.8 else "neutral")
        bpy.context.view_layer.update()
        b=metrics(scene,cam,[actor,partner] if partner else [actor])
        # Fixed framing for the entire clip; do not hide a failure by frame zoom.
        safe=all(x["body_safe"] and x["head_safe"] for x in b)
        s=art.soles() if art else soles(actor)
        row={"frame":f+1,"seconds":t,"phase":p["phase"],"floor":floor(actor),"soles":[list(x) for x in s],"bounds":b,"flight":p["flight"],"lift":p["lift"],"framing_safe":safe}
        if art:row["max_segment_axial_adjustment"]=max((l.stretch for l in art.limbs.values()),default=0)
        if name=="jump" and t>=1.1:
            if land_soles is None:land_soles=[x.copy() for x in s]
            row["landing_sole_drift"]=[(x-y).length for x,y in zip(s,land_soles)]
        if seat:
            row.update(seated_fraction=p["seated_fraction"],seat_error=rear_hip(actor)[0]-seat[0],sole_tilt_deg=[l.tilt() for l in art.legs])
        if name in ("eat","drink"):row.update(mouth_pose(actor,art,name,p,cam,cup,yaw))
        if partner:row.update(intersections=p["intersections"],engagement=p["engagement"],spacing=p["spacing"],spread=p["spread"])
        rows.append(row)
        # Smoke uses the most representative action pose, not a neutral frame.
        smoke_frame={"jump":40,"sit":59,"stand_up":0,"reach":28,"point":28,"eat":15,"drink":30,"hug":32,"fall":25}[name]
        if args.smoke and f!=smoke_frame:continue
        path=clip/f"frame_{f+1:04d}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        assert path.is_file() and path.stat().st_size>0
        if args.smoke:
            (out/"smoke.json").write_text(json.dumps({"render_pass":True,"action":name,"role":role,"sample":row,"samples":scene.cycles.samples,"denoising":scene.cycles.use_denoising},indent=2)+"\n");return
        with Image.open(path) as im:gray=im.convert("L").resize((160,120),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.8))
        if previous is not None:maes.append(ImageStat.Stat(ImageChops.difference(previous,gray)).mean[0])
        previous=gray
    fraction=sum(v<.25 for v in maes)/len(maes)
    report={"index":args.part,"role":role,"action":name,"frames":N,"fps":FPS,"rows":rows,"motion_review_pending":True,"near_static":{"threshold_mae":.25,"count":sum(v<.25 for v in maes),"transitions":len(maes),"fraction":fraction,"maes":maes}}
    gates={"performance_motion":fraction<=.40,"full_body_framing":all(x["framing_safe"] for x in rows)}
    if art:report["max_segment_axial_adjustment"]=max(x["max_segment_axial_adjustment"] for x in rows)
    if name=="reach":
        d=[max(math.hypot(a["soles"][i][0]-b["soles"][i][0],a["soles"][i][1]-b["soles"][i][1]) for a,b in zip(rows,rows[1:])) for i in range(2)]
        report["sole_displacement_per_frame"]=d;gates["planted_foot"]=max(d)<.02
    if name=="point":
        report["sole_displacement_per_frame"]=[max(math.hypot(a["soles"][i][0]-b["soles"][i][0],a["soles"][i][1]-b["soles"][i][1]) for a,b in zip(rows,rows[1:])) for i in range(2)]
    if seat:
        seated=[x for x in rows if x["seated_fraction"]>=.999]
        report["seat"]={"height":seat[0],"max_hip_gap":max(abs(x["seat_error"]) for x in seated),"max_sole_height":max(abs(v[2]) for x in seated for v in x["soles"]),"max_sole_tilt_deg":max(v for x in seated for v in x["sole_tilt_deg"])}
        q=report["seat"];gates.update(seat_contact=q["max_hip_gap"]<=.02,feet_on_floor=q["max_sole_height"]<=.02,feet_flat=q["max_sole_tilt_deg"]<=5)
    if name in ("eat","drink"):
        report["face_blocked_samples_max"]=max(x["face_body_blocked_samples"] for x in rows)
        gates["face_clear_geometry"]=report["face_blocked_samples_max"]==0
        action=[x for x in rows if x["mouth_action"]>=.90]
        report["mouth_contact"]={"hand_min_gap":min(x["hand_to_mouth"] for x in action if x["hand_to_mouth"] is not None),"cup_rim_min_gap":min((x["cup_rim_to_mouth"] for x in action if x["cup_rim_to_mouth"] is not None),default=None),"visual_contact_review_required":True}
    if name=="hug":
        report["max_cross_body_surface_intersections"]=max(x["intersections"] for x in rows if x["engagement"]>.15)
        gates["embrace_no_intersections"]=report["max_cross_body_surface_intersections"]==0
    if name=="jump":
        air=[x for x in rows if x["flight"]];ground=[x for x in rows if not x["flight"]]
        q={"airborne_frames":len(air),"apex_height":max(x["floor"] for x in air),"max_ground_error":max(abs(x["floor"]) for x in ground),"max_landing_sole_drift":max(max(x["landing_sole_drift"]) for x in rows if "landing_sole_drift" in x)}
        report["jump"]=q;gates["jump_trajectory"]=q["max_ground_error"]<=.002 and q["apex_height"]>.25 and len(air)>=15
        # Use the existing planted-foot tolerance for landing as well.
        gates["landing_sole_lock"]=q["max_landing_sole_drift"]<.02
    report["correction_gates"]=gates
    (clip/"metrics.json").write_text(json.dumps(report,indent=2)+"\n")
    print("ROUND_TWO",json.dumps({k:v for k,v in report.items() if k!="rows"}),flush=True)
if __name__=="__main__":main()
