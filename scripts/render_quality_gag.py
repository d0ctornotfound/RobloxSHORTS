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
from library_acting import act,face_clear,sustained_laugh
from stage_a_cafe import light
from render_demo import point_at
import shutil
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
def body_gate(shot,bounds,prop_bounds=None):
    """Single acceptance predicate, shared by candidate search and final preflight."""
    if shot=="gift_action_insert":
        p=prop_bounds
        return p[4]>0 and .035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965
    if shot=="establishing_wide":
        return len(bounds)==2 and all(x["body_safe"] for x in bounds) and sum(x["coverage"] for x in bounds)>=.45
    return len(bounds)==1 and all(x["body_safe"] and x["coverage"]>=.45 for x in bounds)

def face_gate(face):
    return all(x["pass"] for x in face.values())

def lamp_gate(lamps):
    return all(x<=.05 for x in lamps.values())

def render(scene,out,name):
    scene.render.filepath=str(out/(name+".png"));start=time.perf_counter();bpy.ops.render.render(write_still=True);return time.perf_counter()-start

def main():
    p=argparse.ArgumentParser();p.add_argument("--part",type=int,required=True,help="-1 runs complete geometric preflight, no animation rendering");p.add_argument("--output",required=True);p.add_argument("--reuse-insert",type=Path,help="Exact original chunk 4 PNGs from run 45936954946")
    p.add_argument("--test-profile",choices=("low","medium","high","restaged","singles_proof","wide_grid","shadow_a","shadow_b"),help="Supervisor lighting review only; no production renders")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if args.test_profile:
        assert args.part==-1 and not args.reuse_insert
    # Exact trial values, never applied to production mode before approval.
    trials={"low":(230,70,.48),"medium":(340,100,.60),"high":(450,145,.74),"restaged":(85,0,.74),"singles_proof":(85,0,.74),"wide_grid":(85,0,.74),"shadow_a":(85,0,.74),"shadow_b":(85,0,.74)}
    singles_proof=args.test_profile in ("singles_proof","shadow_a","shadow_b")
    wide_grid=args.test_profile=="wide_grid"
    restaged=args.test_profile in ("restaged","singles_proof","wide_grid","shadow_a","shadow_b")
    test_frames={61,166} if singles_proof else {1,11,21} if wide_grid else {1,11,21,61,166} if restaged else {1,11,21,61,116,166} if args.test_profile else set()
    trial_lower,trial_torso,trial_world=trials[args.test_profile] if args.test_profile else (780,480,.34)
    scene,atm,cam,lead=street_scene(48,540,960);scene.render.fps=FPS;scene.render.fps_base=1
    scene.cycles.use_denoising=False;scene.cycles.adaptive_threshold=.035;scene.render.use_persistent_data=True
    atm.apply("golden_hour")
    ambient=scene.world.node_tree.nodes.get("Background").inputs[1]
    original_world=float(ambient.default_value)
    original_sun=float(atm.sun.data.energy);original_fill=float(atm.fill.data.energy);original_exposure=float(scene.view_settings.exposure)
    if restaged:print("BASE_EXPOSURE_AUDIT",json.dumps({"sun":original_sun,"world":original_world,"front_fill":original_fill,"exposure":original_exposure,"hoodie_srgb_original":[104,111,116],"hoodie_srgb_trial":[85,91,95]}),flush=True)
    # Warm motivated, camera-side bounce follows the lead only in three singles.
    lower_fill=light("Gag lead localized lower-body bounce",(0,-2,1.0),(0,0,.55),0,2.2,(1,.87,.73))
    torso_fill=light("Gag lead localized torso bounce",(0,-2,2.1),(0,0,1.35),0,2.6,(1,.91,.81))
    reuse_rows={}
    if args.reuse_insert:
        assert args.part==4
        prior=json.loads((args.reuse_insert/"manifest.json").read_text())
        assert prior["part"]==4 and prior["frames"]==COUNT
        reuse_rows={r["frame"]:r for r in prior["rows"] if r["shot"]=="gift_action_insert"}
        assert set(reuse_rows)==set(range(126,147)),sorted(reuse_rows)
    # Dress this daylight scene so street lamps do not cross face sightlines.
    # Move intact fixtures and their paired point lights out of the acting corridor.
    roots=sorted([o for o in scene.objects if o.type=="EMPTY" and (o.name=="lamp" or o.name.startswith("lamp."))],key=lambda o:o.location.x)
    pools=sorted([o for o in scene.objects if o.type=="LIGHT" and o.name.startswith("Street lamp warm pool")],key=lambda o:o.location.x)
    assert len(roots)==len(pools)==4,(len(roots),len(pools))
    for root,pool,x in zip(roots,pools,(-15.,-12.,12.,15.)):
        root.location.x=x;pool.location.x=x
    bpy.context.view_layer.update()
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
    # Constant shot-local translations preserve the contact-locked relative path.
    wide_lead_shift=Vector((1.9,0,0)) if restaged else Vector((0,0,0))
    wide_friend_shift=Vector((-1.6,0,0)) if restaged else Vector((0,0,0))
    fit={"design":"wide establishing, lead approach/wave/notice, gift insert, lead recoil, friend laugh","wide_total_minimum":.45,"singles_minimum":.45}
    offset=finish-end;offset.z=0
    pose(lead,"idle",0,finish,yaw);pose(friend,"idle",0,other,-.12)
    p=palette();gift=build("gift_box","Surprise gift",pos=(.12,-.64,0),scale=.78,p=p)
    ball=build("ball","Surprise ball",pos=(.12,-.64,.16),scale=.75,p=p)
    lid=[o for o in gift.children if any(k in o.name for k in ("lid","ribbon","bow"))];original={o:o.location.copy() for o in lid}
    # The ball sits inside the closed opaque box until the lid releases.
    for o in ball.children:o.hide_render=True
    print("GAG_SHOT_DESIGN",json.dumps(fit),flush=True)
    # Reproduce the exact first 21 timeline poses with a separate sequential
    # contact lock for each candidate; do not mutate the production walk lock.
    heroes=[lead,friend]
    def wide_pose(sample_lock,f):
        t=f/FPS;scene.frame_set(f+1)
        sample_lock.step(t,smoothstep((t-2.03)/.37),yaw=heading(t))
        lead.root.location+=offset+wide_lead_shift;bpy.context.view_layer.update()
        lead.pose("neutral")
        pose(friend,"idle",t,other+wide_friend_shift,-.12);friend.pose("neutral")
        cam.data.shift_x=0;cam.data.shift_y=0
        for actor in heroes:
            for obj in actor.meshes:obj.hide_render=False
        bpy.context.view_layer.update()
    def wide_sample(f):
        bounds=metrics(scene,cam,heroes)
        face={a.role:face_clear(scene,cam,a) for a in heroes}
        lamp=check_lamps(scene,cam,heroes)
        ratio=min(x["coverage"] for x in bounds)/max(x["coverage"] for x in bounds)
        return {"frame":f+1,"bounds":bounds,"face":face,"lamp_overlap":lamp,"size_ratio":ratio,
                "balance_pass":not restaged or (ratio>=.70 and sum(x["coverage"] for x in bounds)>=.75),
                "body_pass":body_gate("establishing_wide",bounds),
                "face_pass":face_gate(face),"lamp_pass":lamp_gate(lamp)}
    if wide_grid:
        from gag_wide_grid import search
        # Mutable vectors referenced by wide_pose; do not alter singles or contact lock.
        def set_stage(a,b):
            wide_lead_shift.x,wide_lead_shift.y,wide_lead_shift.z=a
            wide_friend_shift.x,wide_friend_shift.y,wide_friend_shift.z=b
        def new_lock():return StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
        def check(f):
            row=wide_sample(f);return row
        def wide_render(f,row):
            ambient.default_value=.74
            base=lead.root.location.copy();base.z=0
            forward=Vector((cam.location.x-base.x,cam.location.y-base.y,0)).normalized()
            lower_fill.location=base+2.8*forward+Vector((0,0,1.2))
            point_at(lower_fill,base+Vector((0,0,.52)));lower_fill.data.energy=115
            bpy.context.view_layer.update()
            if f==10:
                old=scene.render.resolution_percentage;scene.render.resolution_percentage=50
                groups={a.role:[o for o in a.meshes if o.type=="MESH" and o!=a.face] for a in heroes}
                gate=visibility_gate(scene,out,"wide_grid_0011",groups)
                scene.render.resolution_percentage=old;row["visibility"]=gate
                # Preserve the evidence even when the ID gate fails.
            row["shot"]="establishing_wide"
            row["test_light"]={"lower_w":115,"torso_w":0,"world_strength":float(ambient.default_value)}
            row["render_seconds"]=render(scene,out,"test_%04d"%(f+1))
        search(scene,cam,heroes,out,set_stage,new_lock,wide_pose,check,wide_render)
        return
    # Same candidate family and score as the prior revision. First-frame
    # screening is only an optimization: any rejected candidate has failed
    # a real shot frame. The winner MUST pass all 21 actual timeline samples.
    wide_camera=None
    if not singles_proof:
        probe=StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
        wide_pose(probe,0)
        a=lead.root.location.copy();b=friend.root.location.copy();q=(a+b)/2;q.z=1.30
        candidates=[]
        # More lower/closer viewpoints and portrait lens options. Rank
        # by useful character scale, balance and lower camera height.
        # Preserve old candidate family as a fallback; no hidden vetoes.
        for angle in (0,25,-25,45,-45,55,60,-60,65,70,75,80,-70):
            h=math.radians(angle)
            for dist in (5.,6.,7.5,9.,11.,13.):
                for height in (1.55,1.85,2.2,2.8):
                    pos=q+Vector((dist*math.sin(h),-dist*math.cos(h),height-q.z))
                    for lens in (28,35,42,50,58,66,74,85):
                        apply(cam,"static",0,pos,q,lens)
                        bounds=metrics(scene,cam,heroes)
                        if not body_gate("establishing_wide",bounds):continue
                        if restaged and (min(k["coverage"] for k in bounds)/max(k["coverage"] for k in bounds)<.70 or sum(k["coverage"] for k in bounds)<.75):continue
                        lamp=check_lamps(scene,cam,heroes)
                        if not lamp_gate(lamp):continue
                        face={a.role:face_clear(scene,cam,a) for a in heroes}
                        if not face_gate(face):continue
                        total=sum(k["coverage"] for k in bounds)
                        smaller=min(k["coverage"] for k in bounds)
                        separation=abs(bounds[0]["face_center"][0]-bounds[1]["face_center"][0])
                        # Ranking preferences only, never extra cutoffs.
                        score=total+.75*smaller+.05*separation-.09*(height-1.55)-.012*(dist-5.)
                        if args.test_profile:
                            # Prefer comparable projected subject heights, while retaining
                            # coverage and lower-camera preferences. No extra acceptance gate.
                            larger=max(k["coverage"] for k in bounds)
                            balance=smaller/max(larger,1e-8)
                            score=total+1.55*balance+.35*smaller+.05*separation-.09*(height-1.55)-.012*(dist-5.)
                        candidates.append((score,pos.copy(),q.copy(),lens))
        candidates.sort(key=lambda c:c[0],reverse=True)
        attempted=[];wide_camera=None
        for score,pos,target,lens in candidates:
            trial=StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
            checks=[]
            for f in range(21):
                wide_pose(trial,f);apply(cam,"static",0,pos,target,lens)
                row=wide_sample(f);checks.append(row)
                if not (row["body_pass"] and row["face_pass"] and row["lamp_pass"] and row["balance_pass"]):break
            passed=len(checks)==21 and all(r["body_pass"] and r["face_pass"] and r["lamp_pass"] and r["balance_pass"] for r in checks)
            attempted.append({"score":score,"position":list(pos),"target":list(target),"lens":lens,
                              "frames_tested":len(checks),"pass":passed,"last_check":checks[-1]})
            if passed:
                wide_camera=(pos,target,lens)
                save(out,"wide_candidate.json",{"position":list(pos),"target":list(target),"lens":lens,
                    "candidate_count":len(candidates),"candidates_tested":len(attempted),
                    "frames_tested":21,"pass":True,"frames":checks,"lead_shift":list(wide_lead_shift),"friend_shift":list(wide_friend_shift)})
                break
        save(out,"wide_search_audit.json",{"first_frame_candidates":len(candidates),"attempts":attempted})
        if wide_camera is None:raise RuntimeError("No camera candidate passes all 21 establishing frames")
        print("WIDE_ALL_FRAMES_PASS",json.dumps({"frames":21,"first_frame_candidates":len(candidates),
              "attempts":len(attempted),"position":list(wide_camera[0]),"target":list(wide_camera[1]),"lens":wide_camera[2]}),flush=True)
    # Sequential playback ensures stance detection is the same on every runner.
    lock=StrideLock(ret,"walk_cycle",FPS,rate,start,walk_yaw)
    rows=[];failures=[];first=0 if args.part<0 else args.part*30;last=COUNT if args.part<0 else min(COUNT,first+30)
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
        else:friend_beat=sustained_laugh(friend,t-5.55,other,-.12)
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
        # Independent singles proof skips every wide operation and non-proof camera.
        if singles_proof and f+1 not in test_frames:continue
        cam.data.shift_x=0;cam.data.shift_y=0
        # Restore shot-local visibility before every camera evaluation.
        for actor in (lead,friend):
            for obj in actor.meshes:obj.hide_render=False
        prop_points=[p for ob in (*gift.children_recursive,*ball.children_recursive) if ob.type=="MESH" and not ob.hide_render for p in mesh_points(ob)]
        insert=False
        if t<.70:
            heroes=[lead,friend];shot="establishing_wide"
            lead.root.location+=wide_lead_shift;friend.root.location+=wide_friend_shift
            bpy.context.view_layer.update()
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
            # Wave and anticipation have different silhouettes. Cut to a
            # centered sensor at the anticipation beat; keep the proven wave
            # framing unchanged. No lens, pose, or acceptance changes.
            if shot=="wave_notice_single":cam.data.shift_x=-.105 if t<3.25 else 0.0
            bpy.context.view_layer.update()
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
        # The gift insert and wide/friend lighting stay unchanged.
        lower_fill.data.energy=0;torso_fill.data.energy=0
        ambient.default_value=trial_world if args.test_profile and shot=="establishing_wide" else original_world
        atm.sun.data.energy=original_sun;atm.fill.data.energy=original_fill;scene.view_settings.exposure=original_exposure
        if restaged and shot=="establishing_wide":
            # Broad camera-side bounce localized to the dark lead lower body.
            base=lead.root.location.copy();base.z=0
            forward=Vector((cam.location.x-base.x,cam.location.y-base.y,0)).normalized()
            lower_fill.location=base+2.8*forward+Vector((0,0,1.2))
            point_at(lower_fill,base+Vector((0,0,.52)));lower_fill.data.energy=115
        if restaged and shot in ("approach_single","wave_notice_single","recoil_single"):
            atm.sun.data.energy=1.7;atm.fill.data.energy=90;scene.view_settings.exposure=-.15
            # Exactly one shadow-floor variable per supervisor trial.
            if args.test_profile=="shadow_a":ambient.default_value=.44
            if args.test_profile=="shadow_b":scene.view_settings.exposure=0.0
        if shot in ("approach_single","wave_notice_single","recoil_single"):
            x,y,_=lead.root.location
            a=heading(t) if t<2.4 else yaw
            forward=Vector((math.sin(a),-math.cos(a),0))
            side=Vector((math.cos(a),math.sin(a),0))
            base=Vector((x,y,0))
            lower_fill.location=base+2.0*forward+.40*side+Vector((0,0,1.05))
            torso_fill.location=base+2.3*forward-.65*side+Vector((0,0,2.12))
            point_at(lower_fill,base+Vector((0,0,.52)))
            point_at(torso_fill,base+Vector((0,0,1.32)))
            lower_fill.data.energy=trial_lower;torso_fill.data.energy=trial_torso
        bpy.context.view_layer.update()
        b=metrics(scene,cam,heroes)
        face={a.role:face_clear(scene,cam,a) for a in heroes}
        lamps=check_lamps(scene,cam,heroes)
        prop_bounds=project(scene,cam,prop_points) if insert else None
        body_ok=body_gate(shot,b,prop_bounds)
        if restaged and shot=="establishing_wide":body_ok=body_ok and min(x["coverage"] for x in b)/max(x["coverage"] for x in b)>=.70 and sum(x["coverage"] for x in b)>=.75
        face_ok=face_gate(face)
        lamp_ok=lamp_gate(lamps)
        rec={"frame":f+1,"time":t,"shot":shot,"bounds":b,"face":face,"lamp_overlap":lamps,"lead_beat":lead_beat,"friend_beat":friend_beat,"body_pass":body_ok,"face_pass":face_ok,"lamp_pass":lamp_ok,"prop_bounds":prop_bounds,"coverage_rule":"sum>=.45" if shot=="establishing_wide" else "prop_insert" if insert else "each>=.45"}
        rows.append(rec)
        if args.part<0:
            if not (body_ok and face_ok and lamp_ok):failures.append(rec)
            if f+1 in test_frames:
                assert body_ok and face_ok and lamp_ok,rec
                rec["test_profile"]=args.test_profile
                rec["test_light"]={"lower_w":lower_fill.data.energy,"torso_w":torso_fill.data.energy,"world_strength":float(ambient.default_value),"sun":float(atm.sun.data.energy),"base_fill":float(atm.fill.data.energy),"exposure":float(scene.view_settings.exposure)}
                rec["render_seconds"]=render(scene,out,"test_%04d"%(f+1))
            continue
        if first<=f<last:
            # Keep failure evidence instead of discarding the first offending image.
            if not (body_ok and face_ok and lamp_ok):
                save(out,"first_failure.json",rec);render(scene,out,"failure_%04d"%(f+1))
                raise RuntimeError("GAG composition or face gate "+json.dumps(rec))
            if insert and args.reuse_insert:
                prior=reuse_rows[f+1]
                assert prior["body_pass"] and prior["face_pass"] and prior["lamp_pass"]
                assert all(abs(a-b)<1e-5 for a,b in zip(prior["prop_bounds"],rec["prop_bounds"]))
                if "visibility" in prior:
                    rec["visibility"]=prior["visibility"]
                    assert all(v["pass"] for v in rec["visibility"].values())
                name="frame_%04d.png"%(f+1)
                shutil.copyfile(args.reuse_insert/name,out/name)
                rec["reused_from_run"]=45936954946
                continue
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
    if args.part<0:
        save(out,"geometry_preflight.json",{"rows":rows,"failures":failures,"walk":walk_actual,"run":run_rec})
        print("GAG_PREFLIGHT",json.dumps({"frames":len(rows),"failure_count":len(failures),"first_by_shot":{name:next(x for x in failures if x["shot"]==name) for name in sorted({x["shot"] for x in failures})}},default=str),flush=True)
        assert not failures,"Full timeline geometry preflight failed; see artifact"
        if args.test_profile:assert {r["frame"] for r in rows if r.get("test_profile")}==test_frames
        assert walk_actual["pass"] and run_rec["pass"]
        return
    save(out,"manifest.json",{"fps":FPS,"resolution":[540,960],"frames":COUNT,"part":args.part,"stride":walk_actual,"run_stride":run_rec,"rows":rows[first:last],"two_shot":fit,"source_sha256":ret.data["source_sha256"],"engine":scene.render.engine,"samples":48,"denoise":False})
    assert walk_actual["pass"] and run_rec["pass"],("stride lock validation", {k:v for k,v in walk_actual.items() if k!="records"},{k:v for k,v in run_rec.items() if k!="records"})
if __name__=="__main__":main()
