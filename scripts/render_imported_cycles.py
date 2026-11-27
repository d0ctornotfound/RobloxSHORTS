"""Render actual imported walk/run actions and a walking clip; no manual gait."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_library_showcase import fresh,studio,fit,render,street_scene,visible
from render_demo import point_at
from quality_cafe import text
from library_props import palette
from library_character import character
from r6_character import mesh_points
from r6_imported_cycles import Retarget,load

def save(out,name,obj):(out/(name+".json")).write_text(json.dumps(obj,indent=2)+"\n")
def grounded(actor,position,yaw):
    actor.root.location=position;actor.root.rotation_euler=(0,0,yaw)
    bpy.context.view_layer.update()
    low=min(v.z for ob in actor.skinned for v in mesh_points(ob))
    actor.root.location.z+=position[2]-low;bpy.context.view_layer.update()
    return min(v.z for ob in actor.skinned for v in mesh_points(ob)),position[2]-low
def strip(out,name):
    scene=fresh(1920,700,32);scene.render.fps=60;cam=studio(scene,22.5);p=palette();data=load();actors=[];rows=[]
    for i in range(6):
        a=character(name+" "+str(i),"lead");ret=Retarget(a,data)
        if i==0:
            validation=ret.verify();cal=ret.calibrate(name);actions=ret.actions()
            assert set(actions)=={"walk_cycle","run_cycle"}
            action_record={n:{"fcurves":len(ac.fcurves),"frame_range":list(ac.frame_range)} for n,ac in actions.items()}
            assert all(len(ac.fcurves)==42 for ac in actions.values()),action_record
            # Check authored Action F-curves against the converted source keys,
            # not just the direct sampler used to construct the strip.
            rig=a.armature
            for n,ac in actions.items():
                rig.animation_data.action=ac
                for j in (0,len(ret.clips[n]["times"])//2,len(ret.clips[n]["times"])-1):
                    f=1+ret.clips[n]["times"][j]*60;scene.frame_set(int(f),subframe=f-int(f))
                    for part,(pb,Q,T) in ret.map.items():
                        expected=ret.clips[n]["keys"][j][part]
                        delta=a.bind_basis[pb.name].inverted()@pb.matrix_basis
                        assert (delta.translation-expected[0]).length<1e-4
                        assert abs(delta.to_quaternion().dot(expected[1]))>0.99999
                rig.animation_data.action=None
            a.reset()
        c=ret.clips[name];phase=i/6;t=phase*c["duration"];ret.at(name,t)
        low,adjust=grounded(a,((i-2.5)*3.4,0,0),.64);assert abs(low)<.001
        a.pose("happy");actors.append(a);rows.append({"phase":phase,"time":t,"ground_adjust":adjust})
        text("Phase label",f"{phase:.2f} / {t:.3f}s",((i-2.5)*3.4,-1.9,.22),.22,p["cream"])
    bs=fit(scene,cam,actors);render(scene,out,name+"_strip")
    save(out,name,{"source":data["source_sha256"],"source_name":data["clips"][name]["source_name"],"roundtrip":validation,"calibration":cal,"actions":action_record,"phases":rows,"bounds":bs})
    if name=="walk_cycle":bpy.ops.wm.save_as_mainfile(filepath=str(out/"imported_cycles.blend"))
def clip(out,part):
    scene,atm,cam,a=street_scene(16,360,640);scene.render.fps=12
    ret=Retarget(a);cal=ret.calibrate("walk_cycle");atm.apply("midday")
    c=ret.clips["walk_cycle"];fps=12;count=48;rate=min(1,8/(cal["speed_scene_units_per_second"]*(count-1)/fps))
    speed=cal["speed_scene_units_per_second"]*rate;dist=speed*(count-1)/fps
    first=part*16+1;last=first+15;rows=[]
    for f in range(first,last+1):
        t=(f-1)/fps;x=-dist/2+speed*t;scene.frame_set(f)
        ret.at("walk_cycle",t*rate)
        low,adjust=grounded(a,(x,0,0),math.pi/2);assert abs(low)<.001
        a.pose("smug");cam.location=(x+1.8,-4.6,2.65);point_at(cam,(x+.2,.8,1.65))
        bpy.context.view_layer.update()
        b=visible(scene,cam,a)
        rows.append({"frame":f,"source_seconds":t*rate%c["duration"],"root_x":x,"floor_z":low,"ground_adjust":adjust,"bounds":b})
        render(scene,out,f"frame_{f:04d}")
    save(out,"clip"+str(part),{"source_sha256":ret.data["source_sha256"],"action":"walk_cycle","fps":fps,"samples":16,"resolution":[360,640],"speed":speed,"playback_rate":rate,"calibration":cal,"frames":rows})
def main():
    p=argparse.ArgumentParser();p.add_argument("--job",choices=("walk","run","clip0","clip1","clip2"),required=True);p.add_argument("--output",default="render/imported");a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if a.job in ("walk","run"):strip(out,a.job+"_cycle")
    else:clip(out,int(a.job[-1]))
if __name__=="__main__":main()
