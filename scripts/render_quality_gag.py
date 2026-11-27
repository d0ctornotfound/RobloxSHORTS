"""Quality acceptance: 'The Surprise Gift', 8s continuous 30Hz visual gag.
Original assets; setup, anticipation, prop release, recoil, embarrassed payoff.
No modifications to approved proof-story drivers or footage."""
import argparse,json,math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_library_showcase import street_scene
from library_character import character
from r6_imported_cycles import Retarget
from library_locomotion import StrideLock
from library_acting import act,face_clear
from library_animation import pose
from library_props import build,palette
from library_camera import apply,metrics,fit_two_shot,project
from r6_character import mesh_points
from stage_b_interaction import smoothstep
from camera_visibility import visibility_gate

FPS=30;COUNT=240;WALK_END=72
def save(out,name,obj):(out/name).write_text(json.dumps(obj,indent=2)+"\n")
def check_lamps(scene,cam,actors):
    lamps=[o for o in scene.objects if o.type=="MESH" and ("lamp /" in o.name.lower() or "lamp." in o.name.lower()) and "base" not in o.name.lower()]
    # Reject image-plane overlap even when the lamp is behind the face.
    result={}
    for a in actors:
        f=project(scene,cam,mesh_points(a.face));over=0
        area=max(1e-8,(f[1]-f[0])*(f[3]-f[2]))
        for o in lamps:
            b=project(scene,cam,mesh_points(o))
            if b[4]<=0:continue
            over=max(over,max(0,min(f[1],b[1])-max(f[0],b[0]))*max(0,min(f[3],b[3])-max(f[2],b[2]))/area)
        result[a.role]=over
    return result
def render(scene,out,name):
    scene.render.filepath=str(out/(name+".png"));start=time.perf_counter();bpy.ops.render.render(write_still=True);return time.perf_counter()-start

def main():
    p=argparse.ArgumentParser();p.add_argument("--part",type=int,required=True);p.add_argument("--output",required=True)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,atm,cam,lead=street_scene(24,540,960);scene.render.fps=FPS;scene.render.fps_base=1
    scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.065;scene.render.use_persistent_data=True
    atm.apply("golden_hour")
    friend=character("Gift giver","friend");ret=Retarget(lead)
    yaw=.36;start=(0,0,0);rate=.72
    lock=StrideLock(ret,"walk_cycle",FPS,rate,start,yaw)
    for f in range(WALK_END+1):
        t=f/FPS;lock.step(t,smoothstep((t-2.03)/.37))
    walk=lock.report()
    # Exercise run too; separate calibration only, not substituted into gag.
    run=StrideLock(ret,"run_cycle",FPS,.72,(0,0,0),yaw)
    for f in range(61):run.step(f/FPS)
    run_rec=run.report()
    # Use derived travel, not arbitrary speed. Translate entire path so it
    # ends at the marked stage position, preserving contact velocity.
    finish=Vector((-.74,-.12,0));end=Vector(walk["records"][-1]["root"]);offset=finish-end;offset.z=0
    pose(lead,"idle",0,finish,yaw)
    other=Vector((.68,.73,0));pose(friend,"idle",0,other,-.12)
    p=palette();gift=build("gift_box","Surprise gift",pos=(.12,-.64,0),scale=.78,p=p)
    ball=build("ball","Surprise ball",pos=(.12,-.64,.16),scale=.75,p=p)
    lid=[o for o in gift.children if any(k in o.name for k in ("lid","ribbon","bow"))];original={o:o.location.copy() for o in lid}
    # The ball sits inside the closed opaque box until the lid releases.
    for o in ball.children:o.hide_render=True
    # Solve the static two-shot with widest meaningful gesture at payoff.
    act(lead,"embarrassed",.72,finish,yaw);act(friend,"laugh",.72,other,-.12)
    fit=fit_two_shot(scene,cam,[lead,friend],target=(0,.25,1.35),minimum=.45)
    print("GAG_TWO_SHOT",json.dumps(fit),flush=True)
    # Sequential playback ensures stance detection is the same on every runner.
    lock=StrideLock(ret,"walk_cycle",FPS,rate,start,yaw)
    rows=[];first=args.part*30;last=min(COUNT,first+30)
    for f in range(COUNT):
        t=f/FPS;scene.frame_set(f+1)
        if f<=WALK_END:
            step=lock.step(t,smoothstep((t-2.03)/.37))
            lead.root.location+=offset;bpy.context.view_layer.update()
            lead.pose("neutral")
            lead_beat={"beat":"imported_walk","expression":"neutral","body_weight":1}
        elif t<3.25:lead_beat=act(lead,"greet",(t-2.4)/.85,finish,yaw)
        elif t<4.15:lead_beat=act(lead,"anticipate",(t-3.25)/.9,finish,yaw)
        elif t<5.55:lead_beat=act(lead,"recoil",(t-4.15)/1.4,finish,yaw)
        else:lead_beat=act(lead,"embarrassed",(t-5.55)/1.0,finish,yaw)
        if t<3.25:
            pose(friend,"idle",t,other,-.12);friend.pose("neutral");friend_beat={"beat":"idle","expression":"neutral","body_weight":0}
        elif t<4.15:friend_beat=act(friend,"point",(t-3.25)/.9,other,-.12)
        elif t<5.55:friend_beat=act(friend,"recoil",(t-4.15)/1.4,other,-.12)
        else:friend_beat=act(friend,"laugh",(t-5.55)/1.0,other,-.12)
        # Mechanical spring-lid and ball flight; no simulated unseen contact.
        dt=max(0,t-4.15);lift=min(1,dt/.20)
        for ob in lid:
            ob.location=original[ob]+Vector((.35*lift,0,1.3*lift*(1-.52*lift)))
        for o in ball.children:o.hide_render=t<4.15
        if t>=4.15:
            z=.38+3.4*dt-4.905*dt*dt
            # Ball lands at t~4.91, rolls forward, settles on sidewalk.
            ball.location=(.12-.44*min(dt,.95),-.64-.26*min(dt,1.35),max(0,z))
        bpy.context.view_layer.update()
        if t<2.4:
            x,y,z=lead.root.location
            apply(cam,"static",0,(x+.65,y-3.8,1.92),(x,y,1.28),53)
            heroes=[lead];shot="approach"
        elif t<3.25:
            apply(cam,"static",0,(-.74+.25,-3.8,1.92),(-.74,-.12,1.31),49)
            heroes=[lead];shot="wave"
        elif t<5.55:
            apply(cam,"static",0,fit["position"],fit["target"],fit["lens"])
            heroes=[lead,friend];shot="surprise"
        else:
            apply(cam,"static",0,fit["position"],fit["target"],fit["lens"])
            heroes=[lead,friend];shot="payoff"
        b=metrics(scene,cam,heroes)
        face={a.role:face_clear(scene,cam,a) for a in heroes}
        lamps=check_lamps(scene,cam,heroes)
        body_ok=all(x["body_safe"] and x["coverage"]>=.45 for x in b)
        face_ok=all(x["pass"] for x in face.values())
        lamp_ok=all(x<=.05 for x in lamps.values())
        rec={"frame":f+1,"time":t,"shot":shot,"bounds":b,"face":face,"lamp_overlap":lamps,"lead_beat":lead_beat,"friend_beat":friend_beat,"body_pass":body_ok,"face_pass":face_ok,"lamp_pass":lamp_ok}
        rows.append(rec)
        if first<=f<last:
            # Keep failure evidence instead of discarding the first offending image.
            if not (body_ok and face_ok and lamp_ok):
                save(out,"first_failure.json",rec);render(scene,out,"failure_%04d"%(f+1))
                raise RuntimeError("GAG composition or face gate "+json.dumps(rec))
            if f in (15,87,115,135,185,225):
                # Real ID visibility for representative hero frames.
                old=scene.render.resolution_percentage;scene.render.resolution_percentage=50
                gate=visibility_gate(scene,out,"gag_%04d"%(f+1),{a.role:[o for o in a.meshes if o.type=="MESH" and o!=a.face] for a in heroes})
                scene.render.resolution_percentage=old;rec["visibility"]=gate
                assert all(v["pass"] for v in gate.values()),gate
            rec["render_seconds"]=render(scene,out,"frame_%04d"%(f+1))
    walk_actual=lock.report()
    save(out,"manifest.json",{"fps":FPS,"resolution":[540,960],"frames":COUNT,"part":args.part,"stride":walk_actual,"run_stride":run_rec,"rows":rows[first:last],"two_shot":fit,"source_sha256":ret.data["source_sha256"],"engine":scene.render.engine,"samples":24,"denoise":True})
    assert walk_actual["pass"] and run_rec["pass"],("stride lock validation", {k:v for k,v in walk_actual.items() if k!="records"},{k:v for k,v in run_rec.items() if k!="records"})
if __name__=="__main__":main()
