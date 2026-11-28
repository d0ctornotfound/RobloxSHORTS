"""General native timeline sampler. Scene construction is supplied by a declared
adapter; no story names, cast IDs, or shot numbers are defined in this module.
"""
import argparse,importlib,json,math,os,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ.setdefault("R6_KNEE_BLEND","1")
import bpy
from mathutils import Vector
from PIL import Image
import numpy as np
from film_walk_to_mark import construct
from film_direction import apply_grade, direct_camera, performance, directed_bounce, directed_hand_props, sample as direction_sample
from library_locomotion import StrideLock
from r6_imported_cycles import Retarget
from character_motion_correction import apply_corrected,rear_hip
from library_camera import project
from r6_character import mesh_points
def resolve(s):
    module,name=s.split(":");return getattr(importlib.import_module(module),name)
def dump(p,obj):p.write_text(json.dumps(obj,indent=2,default=str)+"\n")
def curve(u):u=max(0,min(1,u));return u*u*(3-2*u)
def safe(p):return p[4]>0 and .035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965
def make_driver(base,conf,task,scene,cam,cast,stage,local_map):
    spec=task["stage"]
    frame=resolve(conf["camera_function"]); camera=spec.get("camera")
    walk=spec.get("walk")
    class Driver(base):
        def prepare_stride(self,nframes):
            self.move_frames=nframes-self.pickup_frames
            original=self.end.copy()
            self.lock,sol=construct(Retarget(self.a),self.start,original-self.start,self.move_frames,cycles=walk.get("cycles",1),phase_strategy=walk.get("phase_strategy","transition"),fixed=walk.get("fixed_timing"))
            self.end=Vector(sol["destination"]);self.stride_offset=sol["offset_seconds"]
            self.yaw=self.lock.yaw;self.settle_len=0;self.hold=1;self.settle_frames=1
            self.stride_candidate={**sol,"original_destination":list(original),"planned_mark_change":(original-self.end).length}
            self.stride_search=[];self.cross_camera=walk["wide"];self.low_camera=walk["low"]
            for cid in walk["spectators"]:self.seat(cid)
            self.low_start=self.pickup_frames+2*(self.move_frames-1)//3
            frame(scene,cam,self.cross_camera["position"],self.cross_camera["target"],self.cross_camera["lens"])
            self.master_matrix=cam.matrix_world.copy();self.master_lens=cam.data.lens
    class DeclaredDriver(base):
        def setup_still(self,n):
            # Scene geometry remains the adapter responsibility. Story-owned
            # marks and explicit actor lists replace legacy template blocking.
            scene_spec=spec["declared_scene"]
            for cid in scene_spec.get("seated",[]):self.seat(cid)
            for cid,m in scene_spec.get("standing",{}).items():
                self.place(cid,m["position"],math.radians(m["yaw_deg"]),m.get("expression","neutral"))
            for name in scene_spec.get("visible_props",[]):
                ob=bpy.data.objects.get(name)
                if ob is None:raise ValueError("missing declared visible prop "+name)
                for child in [ob]+list(ob.children_recursive):child.hide_render=False
            if not self.actors and not scene_spec.get("empty",False):raise ValueError("empty declared scene")
            c=scene_spec.get("initial_camera",{"position":[0,1,2],"target":[0,4,1.25],"lens":35})
            frame(scene,cam,c["position"],c["target"],c["lens"])
    cls=Driver if walk else DeclaredDriver if spec.get("declared_scene") else base
    kw={}
    if spec.get("camera_cache"):kw["reviewed_camera"]=json.loads(Path(spec["camera_cache"]).read_text())["camera"]
    d=cls(scene,cam,cast,stage,spec["unit"],spec.get("setup_ids",task["sentence_ids"]),local_map,conf["lineup"],spec.get("variant"),**kw)
    if walk:d.prepare_stride(task["unit_end"]-task["unit_start"])
    # Story-owned blocking data: explicit stand marks for non-contact setups.
    direction=spec.get("direction",{})
    for cid,mark in direction.get("blocking",{}).items():
        d.place(cid,mark["position"],math.radians(mark["yaw_deg"]),mark.get("expression","neutral"))
    # Declared dynamic-adapter mark overrides retain the adapter\'s contact logic.
    for field,value in direction.get("adapter_vector_marks",{}).items():
        if not hasattr(d,field):raise ValueError("unknown adapter mark "+field)
        setattr(d,field,Vector(value))
    for field,value in direction.get("adapter_yaw_marks",{}).items():
        if not hasattr(d,field):raise ValueError("unknown adapter yaw "+field)
        setattr(d,field,math.radians(value))
    if camera:frame(scene,cam,camera["position"],camera["target"],camera["lens"])
    return d
def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--task",required=True);p.add_argument("--map",required=True);p.add_argument("--output",required=True);p.add_argument("--preflight",action="store_true")
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    conf=json.loads(Path(a.config).read_text());task=json.loads(a.task);spec=task["stage"];plan=json.loads(Path(conf["plan"]).read_text())
    cast=json.loads(Path(plan["cast_path"]).read_text());stage=json.loads(Path(plan["staging_path"]).read_text())
    scene=resolve(conf["setup_function"])(540,960);scene.frame_end=round(plan["audio_duration"]*30);cam=resolve(conf["create_camera"])(scene)
    if spec.get("diagram"):
        from film_diagram_driver import DiagramDriver
        d=DiagramDriver(scene,cam,cast,spec,conf,task)
    else:
        base=resolve(spec.get("driver",conf["default_driver"]));d=make_driver(base,conf,task,scene,cam,cast,stage,a.map)
    actor_points=resolve(conf["actor_points"]);frame=resolve(conf["camera_function"])
    grade=apply_grade(scene,conf["grade_preset"]) if conf.get("grade_preset") else None
    vis=resolve(conf["visibility_function"]);meshes=resolve(conf["meshes_function"])
    action_tracks=None
    if spec.get("actions"):
        from film_action_tracks import ActionTracks
        action_tracks=ActionTracks(d,spec["actions"],task)
    # Declarative generic animated props and performance tracks; no story IDs.
    roots={name:bpy.data.objects.get(name) for name in spec.get("translate_props",{})}
    origin={name:o.location.copy() for name,o in roots.items() if o is not None}
    for name,o in roots.items():
        if o is None:print("MISSING_PROP",name,flush=True)
    dog=None
    if spec.get("animal"):
        pet=spec["animal"];dog=resolve(conf["animal_factory"])(pet["name"])
        dog[0].location=pet["position"];dog[0].rotation_euler.z=math.radians(pet["yaw_deg"])
    rows=[];rendered=[];first=task["start"];end=task["end"];unit_start=task["unit_start"];unit_end=task["unit_end"]
    camera_state={};previous_shot=None
    camera_search=None
    if spec.get("direction",{}).get("camera_candidates"):
        if not a.preflight or spec.get("walk") or action_tracks:raise ValueError("camera candidate search is preflight-only on stateless pose adapters")
        from film_direction import face_facing
        raw=spec["direction"];candidates=raw["camera_candidates"]
        trials=[{"override":v,"spec":{**raw,**v},"state":{},"min_visibility":1.,"min_face_height":1.,"min_facing":1.,"max_external_blocks":0,"safe":True,"min_pencil_visibility":1.,"max_prop_external_blocks":0,"samples":0,"blockers":set()} for v in candidates]
        for gf in range(first,end):
            shot=next(s for s in plan["shots"] if round(s["edit_in"]*30)<=gf<round(s["edit_out"]*30))
            n=int(shot["sentence_ids"][0]);u=(gf-round(shot["edit_in"]*30))/max(1,round(shot["edit_out"]*30)-round(shot["edit_in"]*30)-1);t=(gf-unit_start)/30
            scene.frame_set(gf+1);d.update(n,u,t,gf-unit_start,gf/30>=shot["audio_out"])
            performance(d.actors,raw,u,t)
            hero=d.actors[raw["principal"]]
            for q in trials:
                directed_hand_props(d.actors,q["spec"],t)
                direct_camera(scene,cam,d.actors,q["spec"],u,frame,q["state"])
                v=vis(scene,cam,[hero.face],7);ex=vis(scene,cam,[hero.face],7,meshes(hero.root))
                b=v["bounds"];q["safe"]&=bool(b[4]>0 and .025<=b[0]<=b[1]<=.975 and .025<=b[2]<=b[3]<=.975)
                q["min_visibility"]=min(q["min_visibility"],v["visible_fraction"]);q["min_face_height"]=min(q["min_face_height"],b[3]-b[2]);q["min_facing"]=min(q["min_facing"],face_facing(hero,cam))
                q["max_external_blocks"]=max(q["max_external_blocks"],ex["blocked"]);q["samples"]+=1;q["blockers"].update(v["blockers"])
                if raw.get("camera_search_prop"):
                    ob=bpy.data.objects.get(raw["camera_search_prop"])
                    if ob is None:raise ValueError("camera search prop missing")
                    pv=vis(scene,cam,meshes(ob),9)
                    pe=vis(scene,cam,meshes(ob),9,meshes(hero.root))
                    q["min_pencil_visibility"]=min(q["min_pencil_visibility"],pv["visible_fraction"] if pe["safe"] else 0.)
                    q["max_prop_external_blocks"]=max(q["max_prop_external_blocks"],pe["blocked"])
        def rank(q):
            return (not(q["safe"] and q["min_visibility"]>=.85 and q["min_face_height"]>=.40 and q["min_facing"]>=.65 and q["max_external_blocks"]==0 and q["min_pencil_visibility"]>=raw.get("camera_search_prop_min",0) and q["max_prop_external_blocks"]==0),q["max_external_blocks"],max(0,.85-q["min_visibility"]),not q["safe"],max(0,.40-q["min_face_height"]),-q["min_pencil_visibility"],-q["min_visibility"])
        best=min(trials,key=rank)
        camera_search={"selected":best["override"],"candidates":[{k:(sorted(v) if k=="blockers" else v) for k,v in q.items() if k not in ("state","spec")} for q in trials]}
        spec["direction"]={**raw,**best["override"]};spec["direction"].pop("camera_candidates")
        print("CAMERA_SEARCH",json.dumps(camera_search),flush=True)
    for gf in range(unit_start,end):
        shot=next(s for s in plan["shots"] if round(s["edit_in"]*30)<=gf<round(s["edit_out"]*30))
        n=int(shot["sentence_ids"][0]);u=(gf-round(shot["edit_in"]*30))/max(1,round(shot["edit_out"]*30)-round(shot["edit_in"]*30)-1);t=(gf-unit_start)/30
        if shot["id"]!=previous_shot:camera_state={};previous_shot=shot["id"]
        scene.frame_set(gf+1)
        if spec.get("walk"):
            q=d.cross_camera;frame(scene,cam,q["position"],q["target"],q["lens"])
        m=d.update(n,u,t,gf-unit_start,gf/30>=shot["audio_out"])
        if action_tracks:m["declared_walks"]=action_tracks.before_performance(gf-unit_start)
        if spec.get("walk") and gf-unit_start>=d.low_start:
            q=d.low_camera;frame(scene,cam,q["position"],q["target"],q["lens"])
        # Stage-specific base pose is followed by reusable animation tracks.
        # All timings are normalized to the declared segment.
        su=(gf-unit_start)/max(1,unit_end-unit_start-1)
        for cid,track in spec.get("actors",{}).items():
            if cid not in d.actors:continue
            actor=d.actors[cid]
            if "head" in track:
                v=track["head"];actor.set_bone("head",tuple(x*math.sin(math.pi*su) for x in v))
            if "arm" in track:
                arm=track["arm"];start=arm.get("start",[0,-.2,-1]);finish=arm["end"]
                w=math.sin(math.pi*su) if arm.get("return",True) else curve(su)
                actor.aim_arm(arm.get("index",0),tuple(x+(y-x)*w for x,y in zip(start,finish)))
            if "sit_at" in track:
                q=track["sit_at"];v=curve((su-.40)/.60)
                apply_corrected(actor,"sit",v,t,q["position"],math.radians(q["yaw_deg"]))
            if "expression" in track:actor.pose(track["expression"] if su>=.5 else track.get("initial_expression",track["expression"]))
        for name,vec in spec.get("translate_props",{}).items():
            if roots[name] is not None:roots[name].location=origin[name]+Vector(vec)*curve(su)
        if dog: m["animal_contact"]=resolve(conf["animal_pose"])(dog,spec["animal"]["motion"],su)
        bpy.context.view_layer.update()
        if spec.get("direction"):
            performance(d.actors,spec["direction"],su if spec.get("segment_performance") else u,t)
        if action_tracks:m["declared_socket_contacts"]=action_tracks.after_performance(gf-unit_start)
        if spec.get("direction",{}).get("hand_props"):
            m["directed_hand_props"]=directed_hand_props(d.actors,spec["direction"],t)
        if spec.get("direction"):
            direct_camera(scene,cam,d.actors,spec["direction"],su if spec.get("segment_performance") else u,frame,camera_state)
        frame_grade=grade
        if spec.get("direction",{}).get("grade_fill"):
            frame_grade={**grade,"directed_bounce":directed_bounce(scene,cam,spec["direction"],d.actors)}
        if gf<first:continue
        for hp in spec.get("direction",{}).get("hand_props",[]):
            ob=bpy.data.objects[hp["object"]];hero=d.actors[hp["actor"]];prefix=hp.get("metric_prefix","hand_prop")
            m[prefix+"_visibility"]=vis(scene,cam,meshes(ob),9)
            m[prefix+"_external_visibility"]=vis(scene,cam,meshes(ob),9,meshes(hero.root))
            if hp.get("contact_function"):m[prefix+"_contact"]=resolve(hp["contact_function"])(hero,int(hp["socket"]),ob)
        # Generic external vs own-character visibility; the full original ray
        # result is retained, never reclassified as a geometry pass.
        quality={}
        for cid in spec.get("qc_actors",[]):
            if cid not in d.actors:continue
            actor=d.actors[cid];b=project(scene,cam,actor_points(actor))
            face=vis(scene,cam,[actor.face],7)
            external=vis(scene,cam,[actor.face],7,meshes(actor.root))
            quality[cid]={"bounds":list(b),"safe":safe(b),"vertical_coverage":b[3]-b[2],"face_all":face,"face_external":external,"own_ray_difference":max(0,face["blocked"]-external["blocked"])}
        row={"frame":gf,"shot":shot["id"],"unit_window":[unit_start,unit_end],"actor_qc":quality,"geometry":m,**({"direction":direction_sample(scene,cam,d.actors,spec["direction"],frame_grade,vis,meshes)} if spec.get("direction") else {})}
        rows.append(row)
        if not a.preflight or gf in (first,(first+end)//2,end-1):
            path=out/f"frame_{gf:05d}.png";scene.render.filepath=str(path)
            clock=time.monotonic()
            print("SMOKE_START" if gf==first else "FRAME_START",gf,flush=True)
            bpy.ops.render.render(write_still=True)
            pix=np.asarray(Image.open(path).convert("RGB"))
            render={"frame":gf,"render_seconds":time.monotonic()-clock,"near_black_percent":100*float(np.mean(np.max(pix,axis=2)<=24))}
            rendered.append(render)
            print("SMOKE_PASS" if gf==first else "FRAME_DONE",gf,flush=True)
        if not a.preflight or gf==end-1:dump(out/"partial.json",{"rendered":rendered,"rows":rows})
    assert len(rows)==end-first
    if not a.preflight:assert len(rendered)==end-first
    extra={}
    if camera_search:extra["camera_search"]=camera_search
    if action_tracks:extra["declared_walks"]=action_tracks.report()
    if spec.get("walk") and end==unit_end:
        report=d.lock.report();extra["walk"]={**d.stride_candidate,"metrics":{k:v for k,v in report.items() if k!="records"},"root_stop_error_to_plant":(d.lock.pos-d.end).length,"final_contact_error":(Vector(d.lock.records[-1]["contact_world"])-d.end).length,"complete_unit":end==unit_end,"end_mode":spec["walk"].get("end_mode","stop"),"last_support":d.lock.records[-1]["support"],"last_forward_speed":d.lock.records[-1]["forward_speed"]}
    dump(out/"manifest.json",{"task":task,"preflight_only":a.preflight,"engine":"EEVEE","denoising":False,"spatial_samples":32,"render_sampling_hz":30,"rendered":rendered,"rows":rows,"extra":extra,"missing_props":[n for n,o in roots.items() if o is None]})
if __name__=="__main__":main()
