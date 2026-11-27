"""Isolated library quality review; never modifies approved proof scenes on disk."""
import argparse,json,math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_library_showcase import fresh,street_scene
from library_camera import MOVES,create,apply,fit_two_shot,metrics
from library_character import character
from library_animation import pose
from r6_imported_cycles import Retarget
from render_imported_cycles import grounded
from camera_visibility import visibility_gate

def save(out,name,data):(out/(name+".json")).write_text(json.dumps(data,indent=2)+"\n")
def render(scene,out,name):
    scene.render.filepath=str(out/(name+".png"));start=time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed=time.perf_counter()-start
    print("QUALITY_RENDER",name,elapsed,flush=True);return elapsed

def eevee(scene):
    identifiers={x.identifier for x in scene.render.bl_rna.properties["engine"].enum_items}
    scene.render.engine="BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in identifiers else "BLENDER_EEVEE"
    e=getattr(scene,"eevee",None)
    if e:
        for k,v in (("taa_render_samples",64),("use_gtao",True),("gtao_distance",1.5),("gtao_factor",1.2),("use_soft_shadows",True)):
            if hasattr(e,k):setattr(e,k,v)
    scene.render.resolution_x=1080;scene.render.resolution_y=1920;scene.render.resolution_percentage=100
    scene.render.fps=30;scene.render.fps_base=1

def benchmark(out,kind,blend,mode):
    if kind=="cafe":
        bpy.ops.wm.open_mainfile(filepath=str(Path(blend).resolve()))
        scene=bpy.context.scene;oldfps=scene.render.fps
        def at(t):
            f=49+t*oldfps;scene.frame_set(int(f),subframe=f-int(f))
    else:
        scene,atm,cam,actor=street_scene(16,360,640);scene.render.fps=12
        atm.apply("midday");ret=Retarget(actor)
        def at(t):
            x=-3+1.678321678*t
            ret.at("walk_cycle",t*.4937511)
            grounded(actor,(x,0,0),math.pi/2);actor.pose("smug")
            apply(cam,"static",0,(x+.85,-3.75,2.24),(x+.12,.25,1.78),43)
            atm.fill.location=(x,-5,5)
    at(0);bpy.context.view_layer.update()
    old=[scene.render.resolution_x,scene.render.resolution_y,scene.cycles.samples]
    rec={"scene":kind,"blender":bpy.app.version_string,"preview_resolution":old[:2],"preview_samples":old[2],"timing":"wall clock bpy.ops.render.render including PNG write, same runner"}
    if mode=="still":
        rec["cycles_preview_seconds"]=render(scene,out,"cycles_preview")
        scene.render.resolution_x=1080;scene.render.resolution_y=1920
        rec["cycles_matched_seconds"]=render(scene,out,"cycles_1080")
    eevee(scene);rec["eevee_engine"]=scene.render.engine
    if mode=="still":
        at(0);rec["eevee_seconds"]=render(scene,out,"eevee_1080")
        rec["speedup_vs_preview"]=rec["cycles_preview_seconds"]/rec["eevee_seconds"]
        rec["speedup_vs_matched"]=rec["cycles_matched_seconds"]/rec["eevee_seconds"]
    else:
        # Real 30Hz samples, not duplicated 12fps images. One second each.
        timings=[]
        for i in range(30):
            at(i/30);bpy.context.view_layer.update()
            timings.append(render(scene,out,"frame_%04d"%(i+1)))
        rec["frames"]=30;rec["fps"]=30;rec["seconds_per_frame"]=timings;rec["mean_seconds"]=sum(timings)/30
    rec["final_resolution"]=[scene.render.resolution_x,scene.render.resolution_y];rec["final_fps"]=scene.render.fps
    save(out,"benchmark",rec)

def demos(out,part):
    scene,atm,cam,lead=street_scene(24,540,960);atm.apply("midday")
    friend=character("Camera demo friend","friend")
    pose(lead,"idle",.3,(-.73,-.18,0));pose(friend,"idle",.4,(.73,.45,0))
    lead.pose("happy");friend.pose("laughing")
    cam=create(scene,"Portrait library camera")
    fit=fit_two_shot(scene,cam,[lead,friend],target=(0,.12,1.35))
    if part==0:
        render(scene,out,"tight_two_shot")
        scene.render.resolution_percentage=50
        gate=visibility_gate(scene,out,"tight_two_shot",{a.role:[o for o in a.meshes if o.type=="MESH" and o!=a.face] for a in (lead,friend)})
        scene.render.resolution_percentage=100
        save(out,"two_shot",{"fit":fit,"visibility":gate})
    rows=[]
    for kind in MOVES[part*3:part*3+3]:
        for suffix,t in (("start",0),("end",1)):
            pose(lead,"idle",.3,(-.73,-.18,0));pose(friend,"idle",.4,(.73,.45,0))
            p=Vector(fit["position"]);q=Vector(fit["target"]);lens=fit["lens"];kw={}
            if kind=="push_in":kw={"distance":.40}
            if kind=="pull_back":kw={"distance":.55}
            if kind=="pan":kw={"end_target":(.4,.2,1.45)}
            if kind=="tracking_follow":
                x=-.73+t*1.8;pose(lead,"walk",t*.8,(x,-.18,0),yaw=math.pi/2)
                p=Vector((-1.1,-4,2.3));q=Vector((-.73,-.18,1.35));lens=43
                kw={"subject_start":(-.73,-.18,0),"subject_now":(x,-.18,0)}
            if kind=="orbit":kw={"angle":22}
            if kind=="over_shoulder":
                p=Vector((-.35,-.65,.18));q=Vector((.73,.45,1.65));lens=42
                # apply uses offset position-target; explicit anchor at lead shoulder.
                shoulder=Vector((-.73,-.18,1.95));p=q+Vector((-.35,-.65,.18));kw={"shoulder":shoulder}
            if kind=="pov":
                p=Vector((0,-3,2));q=Vector((.73,.45,1.65));lens=32
                kw={"eye":(-.73,-.30,1.98),"look":(.73,.45,1.65)}
                for o in lead.meshes:o.hide_render=True
            if kind=="close_up_punch_in":
                p=Vector((-.73,-3.7,2.0));q=Vector((-.73,-.18,1.9));lens=43;kw={"punch_lens":68}
            row=apply(cam,kind,t,p,q,lens,**kw);row["subjects"]=metrics(scene,cam,[lead,friend])
            render(scene,out,kind+"_"+suffix);rows.append(row)
            for o in lead.meshes:o.hide_render=False
    save(out,"camera_moves",rows)

def main():
    p=argparse.ArgumentParser();p.add_argument("--job",required=True);p.add_argument("--output",required=True);p.add_argument("--cafe-blend",default="approved/story.blend")
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if a.job.startswith("camera"):demos(out,int(a.job[-1]))
    else:
        kind,mode=a.job.split("_");benchmark(out,kind,a.cafe_blend,mode)
if __name__=="__main__":main()
