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
from film_direction import apply_grade, direct_camera, performance, sample as direction_sample
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
            self.lock,sol=construct(Retarget(self.a),self.start,original-self.start,self.move_frames,cycles=walk.get("cycles",1))
            self.end=Vector(sol["destination"]);self.stride_offset=sol["offset_seconds"]
            self.yaw=self.lock.yaw;self.settle_len=0;self.hold=1;self.settle_frames=1
            self.stride_candidate={**sol,"original_destination":list(original),"planned_mark_change":(original-self.end).length}
            self.stride_search=[];self.cross_camera=walk["wide"];self.low_camera=walk["low"]
            for cid in walk["spectators"]:self.seat(cid)
            self.low_start=self.pickup_frames+2*(self.move_frames-1)//3
            frame(scene,cam,self.cross_camera["position"],self.cross_camera["target"],self.cross_camera["lens"])
            self.master_matrix=cam.matrix_world.copy();self.master_lens=cam.data.lens
    cls=Driver if walk else base
    kw={}
    if spec.get("camera_cache"):kw["reviewed_camera"]=json.loads(Path(spec["camera_cache"]).read_text())["camera"]
    d=cls(scene,cam,cast,stage,spec["unit"],task["sentence_ids"],local_map,conf["lineup"],spec.get("variant"),**kw)
    if walk:d.prepare_stride(task["unit_end"]-task["unit_start"])
    if camera:frame(scene,cam,camera["position"],camera["target"],camera["lens"])
    return d
def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--task",required=True);p.add_argument("--map",required=True);p.add_argument("--output",required=True)
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    conf=json.loads(Path(a.config).read_text());task=json.loads(a.task);spec=task["stage"];plan=json.loads(Path(conf["plan"]).read_text())
    cast=json.loads(Path(plan["cast_path"]).read_text());stage=json.loads(Path(plan["staging_path"]).read_text())
    scene=resolve(conf["setup_function"])(540,960);scene.frame_end=round(plan["audio_duration"]*30);cam=resolve(conf["create_camera"])(scene)
    base=resolve(spec.get("driver",conf["default_driver"]));d=make_driver(base,conf,task,scene,cam,cast,stage,a.map)
    actor_points=resolve(conf["actor_points"]);frame=resolve(conf["camera_function"])
    grade=apply_grade(scene,conf["grade_preset"]) if conf.get("grade_preset") else None
    vis=resolve(conf["visibility_function"]);meshes=resolve(conf["meshes_function"])
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
    for gf in range(unit_start,end):
        shot=next(s for s in plan["shots"] if round(s["edit_in"]*30)<=gf<round(s["edit_out"]*30))
        n=int(shot["sentence_ids"][0]);u=(gf-round(shot["edit_in"]*30))/max(1,round(shot["edit_out"]*30)-round(shot["edit_in"]*30)-1);t=(gf-unit_start)/30
        scene.frame_set(gf+1)
        if spec.get("walk"):
            q=d.cross_camera;frame(scene,cam,q["position"],q["target"],q["lens"])
        m=d.update(n,u,t,gf-unit_start,gf/30>=shot["audio_out"])
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
            performance(d.actors,spec["direction"],u,t)
            direct_camera(scene,cam,d.actors,spec["direction"],u,frame)
        if gf<first:continue
        # Generic external vs own-character visibility; the full original ray
        # result is retained, never reclassified as a geometry pass.
        quality={}
        for cid in spec.get("qc_actors",[]):
            if cid not in d.actors:continue
            actor=d.actors[cid];b=project(scene,cam,actor_points(actor))
            face=vis(scene,cam,[actor.face],5)
            external=vis(scene,cam,[actor.face],5,meshes(actor.root))
            quality[cid]={"bounds":list(b),"safe":safe(b),"vertical_coverage":b[3]-b[2],"face_all":face,"face_external":external,"own_ray_difference":max(0,face["blocked"]-external["blocked"])}
        path=out/f"frame_{gf:05d}.png";scene.render.filepath=str(path)
        clock=time.monotonic()
        print("SMOKE_START" if gf==first else "FRAME_START",gf,flush=True)
        bpy.ops.render.render(write_still=True)
        pix=np.asarray(Image.open(path).convert("RGB"))
        render={"frame":gf,"render_seconds":time.monotonic()-clock,"near_black_percent":100*float(np.mean(np.max(pix,axis=2)<=24))}
        rendered.append(render);rows.append({"frame":gf,"shot":shot["id"],"actor_qc":quality,"geometry":m,**({"direction":direction_sample(scene,cam,d.actors,spec["direction"],grade)} if spec.get("direction") else {})})
        dump(out/"partial.json",{"rendered":rendered,"rows":rows})
        print("SMOKE_PASS" if gf==first else "FRAME_DONE",gf,flush=True)
    assert len(rendered)==end-first
    extra={}
    if spec.get("walk") and end==unit_end:
        report=d.lock.report();extra["walk"]={**d.stride_candidate,"metrics":{k:v for k,v in report.items() if k!="records"},"root_stop_error_to_plant":(d.lock.pos-d.end).length,"final_contact_error":(Vector(d.lock.records[-1]["contact_world"])-d.end).length,"complete_unit":end==unit_end}
    dump(out/"manifest.json",{"task":task,"engine":"EEVEE","denoising":False,"spatial_samples":32,"render_sampling_hz":30,"rendered":rendered,"rows":rows,"extra":extra,"missing_props":[n for n,o in roots.items() if o is None]})
if __name__=="__main__":main()
