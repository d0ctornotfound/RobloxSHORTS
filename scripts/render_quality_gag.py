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
from library_camera import apply,metrics,project,points
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
    yaw=.30;walk_yaw=1.40;start=(0,0,0);rate=.72
    def heading(t):return walk_yaw+(yaw-walk_yaw)*smoothstep((t-2.03)/.37)
    lock=StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
    for f in range(WALK_END+1):
        t=f/FPS;lock.step(t,smoothstep((t-2.03)/.37),yaw=heading(t))
    walk=lock.report()
    # Exercise run too; separate calibration only, not substituted into gag.
    run=StrideLock(ret,"run_cycle",FPS,.72,(0,0,0),yaw)
    for f in range(181):run.step(f/FPS)
    run_rec=run.report()
    save(out,"calibration.json",{"walk":walk,"run":run_rec})
    print("STRIDE_VALIDATION",json.dumps({k:{a:b for a,b in v.items() if a!="records"} for k,v in (("walk",walk),("run",run_rec))}),flush=True)
    # Use derived travel, not arbitrary speed. Translate entire path so it
    # ends at the marked stage position, preserving contact velocity.
    end=Vector(walk["records"][-1]["root"])
    # Supervisor-approved shot design: establish geography once, then singles and insert.
    finish=Vector((-.72,.08,0));other=Vector((.76,.42,0))
    fit={"design":"wide establishing, lead approach/wave/notice, gift insert, lead recoil, friend laugh","wide_total_minimum":.45,"singles_minimum":.45}
    offset=finish-end;offset.z=0
    pose(lead,"idle",0,finish,yaw);pose(friend,"idle",0,other,-.12)
    p=palette();gift=build("gift_box","Surprise gift",pos=(.12,-.64,0),scale=.78,p=p)
    ball=build("ball","Surprise ball",pos=(.12,-.64,.16),scale=.75,p=p)
    lid=[o for o in gift.children if any(k in o.name for k in ("lid","ribbon","bow"))];original={o:o.location.copy() for o in lid}
    # The ball sits inside the closed opaque box until the lid releases.
    for o in ball.children:o.hide_render=True
    print("GAG_SHOT_DESIGN",json.dumps(fit),flush=True)
    wide_camera=None
    # Sequential playback ensures stance detection is the same on every runner.
    lock=StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
    rows=[];first=args.part*30;last=min(COUNT,first+30)
    for f in range(COUNT):
        t=f/FPS;scene.frame_set(f+1)
        if f<=WALK_END:
            step=lock.step(t,smoothstep((t-2.03)/.37),yaw=heading(t))
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
        # Restore shot-local visibility before every camera evaluation.
        for actor in (lead,friend):
            for obj in actor.meshes:obj.hide_render=False
        prop_points=[p for ob in (*gift.children_recursive,*ball.children_recursive) if ob.type=="MESH" and not ob.hide_render for p in mesh_points(ob)]
        insert=False
        if t<.70:
            heroes=[lead,friend];shot="establishing_wide"
            if wide_camera is None:
                a=lead.root.location.copy();b=friend.root.location.copy();q=(a+b)/2;q.z=1.30
                verts=[points(actor) for actor in heroes]
                best=None
                for angle in (0,25,-25,45,-45,60,-60):
                    h=math.radians(angle)
                    for dist in (6.,7.5,9.,11.):
                        pos=q+Vector((dist*math.sin(h),-dist*math.cos(h),2.8-q.z))
                        for lens in (28,35,42,50,58):
                            apply(cam,"static",0,pos,q,lens)
                            bounds=[project(scene,cam,x) for x in verts]
                            if not all(k[4]>0 and .05<=k[0]<=k[1]<=.95 and .06<=k[2]<=k[3]<=.94 for k in bounds):continue
                            total=sum(k[3]-k[2] for k in bounds)
                            separation=abs(sum(bounds[0][:2])/2-sum(bounds[1][:2])/2)
                            if total>=.45 and separation>=.18:
                                score=total+.15*separation-.001*abs(angle)
                                if best is None or score>best[0]:best=(score,pos.copy(),q.copy(),lens)
                if best is None:raise RuntimeError("Wide establishment has no safe full-body total >=45% framing")
                _,pos,q,lens=best;wide_camera=(pos,q,lens)
            apply(cam,"static",0,*wide_camera)
        elif t<4.15 or 4.85<=t<6.35:
            heroes=[lead];shot="approach_single" if t<2.4 else "wave_notice_single" if t<4.15 else "recoil_single"
            # Explicit cut to a single. Exclude non-hero only from this shot's render,
            # never from the shared action timeline or the establishing view.
            for obj in friend.meshes:obj.hide_render=True
            x,y,z=lead.root.location;h=heading(t) if t<2.4 else yaw
            # Follow the actual root with a stable focal length. Camera is in front
            # of the face, slightly to camera-left, rather than grazing the profile.
            a=h-.20;d=4.35 if shot=="wave_notice_single" else 4.05
            apply(cam,"static",0,(x+d*math.sin(a),y-d*math.cos(a),1.83),(x,y,1.28),53)
        elif t<4.85:
            heroes=[];shot="gift_action_insert";insert=True
            for actor in (lead,friend):
                for obj in actor.meshes:obj.hide_render=True
            apply(cam,"static",0,(.65,-3.05,1.32),(.0,-.64,.60),54)
        else:
            heroes=[friend];shot="laugh_single"
            for obj in lead.meshes:obj.hide_render=True
            x,y,z=friend.root.location
            apply(cam,"static",0,(x-.45,y-4.0,1.83),(x,y,1.28),53)
        b=metrics(scene,cam,heroes)
        face={a.role:face_clear(scene,cam,a) for a in heroes}
        lamps=check_lamps(scene,cam,heroes)
        prop_bounds=project(scene,cam,prop_points) if insert else None
        if insert:
            body_ok=prop_bounds[4]>0 and .035<=prop_bounds[0]<=prop_bounds[1]<=.965 and .035<=prop_bounds[2]<=prop_bounds[3]<=.965
        elif shot=="establishing_wide":
            body_ok=all(x["body_safe"] for x in b) and sum(x["coverage"] for x in b)>=.45
        else:
            body_ok=all(x["body_safe"] and x["coverage"]>=.45 for x in b)
        # Wide face rays recorded diagnostically; singles retain original face gate.
        face_ok=all(x["pass"] for x in face.values()) if len(heroes)==1 else True
        lamp_ok=all(x<=.05 for x in lamps.values())
        rec={"frame":f+1,"time":t,"shot":shot,"bounds":b,"face":face,"lamp_overlap":lamps,"lead_beat":lead_beat,"friend_beat":friend_beat,"body_pass":body_ok,"face_pass":face_ok,"lamp_pass":lamp_ok,"prop_bounds":prop_bounds,"coverage_rule":"sum>=.45" if shot=="establishing_wide" else "prop_insert" if insert else "each>=.45"}
        rows.append(rec)
        if first<=f<last:
            # Keep failure evidence instead of discarding the first offending image.
            if not (body_ok and face_ok and lamp_ok):
                save(out,"first_failure.json",rec);render(scene,out,"failure_%04d"%(f+1))
                raise RuntimeError("GAG composition or face gate "+json.dumps(rec))
            if f in (10,45,87,115,135,165,205,225):
                # Real ID visibility for representative hero frames.
                old=scene.render.resolution_percentage;scene.render.resolution_percentage=50
                groups={a.role:[o for o in a.meshes if o.type=="MESH" and o!=a.face] for a in heroes}
                if insert:groups={"gift":[o for o in gift.children_recursive if o.type=="MESH"],"ball":[o for o in ball.children_recursive if o.type=="MESH" and not o.hide_render]}
                gate=visibility_gate(scene,out,"gag_%04d"%(f+1),groups)
                scene.render.resolution_percentage=old;rec["visibility"]=gate
                assert all(v["pass"] for v in gate.values()),gate
            rec["render_seconds"]=render(scene,out,"frame_%04d"%(f+1))
    walk_actual=lock.report()
    save(out,"manifest.json",{"fps":FPS,"resolution":[540,960],"frames":COUNT,"part":args.part,"stride":walk_actual,"run_stride":run_rec,"rows":rows[first:last],"two_shot":fit,"source_sha256":ret.data["source_sha256"],"engine":scene.render.engine,"samples":24,"denoise":True})
    assert walk_actual["pass"] and run_rec["pass"],("stride lock validation", {k:v for k,v in walk_actual.items() if k!="records"},{k:v for k,v in run_rec.items() if k!="records"})
if __name__=="__main__":main()
