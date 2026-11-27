"""30fps character-only review. No maps, sets, props, generated dialogue.
One isolated action per clip. Motion gate evidence and per-frame metrics retained."""
import argparse,json,math,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_stills import configure
from render_demo import cube,point_at
from stage_a_cafe import light
from r6_character import matte
from render_r6_stills import camera
from library_camera import metrics
from library_character import character
from r6_imported_cycles import Retarget
from library_locomotion import StrideLock
from character_motion import MOTIONS,apply_weighted,high_five_contact,soles,floor

FPS=30;N=60
CLIPS=[(role,action) for role in ("lead","friend") for action in ("walk","run","jump")]+[("lead",x) for x in MOTIONS if x not in ("walk","run","jump")]
# 7 chunks of 3/4 clips. Per-frame geometry preflight before each render.
def studio():
    s=configure("preview");s.render.resolution_x=640;s.render.resolution_y=480;s.render.fps=FPS
    s.cycles.samples=16;s.cycles.use_denoising=True;s.cycles.adaptive_threshold=.10;s.render.use_persistent_data=True
    s.view_settings.view_transform="AgX";s.view_settings.look="AgX - Medium High Contrast";s.view_settings.exposure=-.10
    bg=s.world.node_tree.nodes.get("Background");bg.inputs[0].default_value=(.50,.50,.50,1);bg.inputs[1].default_value=.45
    gray=matte("Plain neutral studio",(.32,.32,.32))
    cube("Neutral studio floor",(0,0,-.12),(100,100,.24),gray,bevel=0)
    cube("Neutral studio backdrop",(0,14,5),(100,.12,15),gray,bevel=0)
    key=light("Soft neutral key",(-3,-5,6),(0,0,1.3),650,5,(1,.97,.94))
    fill=light("Soft neutral fill",(4,-4,4),(0,0,1.3),320,5,(.95,.97,1))
    rim=light("Soft neutral rim",(0,3,5),(0,0,1.3),240,4,(1,1,1))
    cam=camera(s,(3,-10,2.5),(0,0,1.5),5.8,True)
    return s,cam,(key,fill,rim)
def set_visible(a,visible):
    for o in a.meshes:o.hide_render=not visible
def main():
    p=argparse.ArgumentParser();p.add_argument("--part",type=int,required=True);p.add_argument("--output",required=True)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam,lights=studio()
    lead=character("Motion lead","lead");friend=character("Motion friend","friend")
    actors={"lead":lead,"friend":friend};ret={k:Retarget(a) for k,a in actors.items()}
    clipids=list(range(len(CLIPS)))[args.part::7]
    results=[]
    for idx in clipids:
        role,name=CLIPS[idx];actor=actors[role];partner=friend if role=="lead" else lead
        paired=name in ("hug","high_five");set_visible(actor,True);set_visible(partner,paired)
        clip=out/f"{idx:02d}_{role}_{name}";clip.mkdir(exist_ok=True)
        base=(0,0,0);yaw=.25
        lock=StrideLock(ret[role],name+"_cycle",FPS,.72,base,yaw) if name in ("walk","run") else None
        rows=[];landing=None
        for f in range(N):
            scene.frame_set(f+1);t=f/FPS;u=f/(N-1)
            if lock:
                rec=lock.step(t);actor.pose("neutral");p={"flight":rec["flight"],"phase":"imported_contact_corrected","lift":rec["floor_error"]}
            elif paired:
                p=apply_weighted(actor,name,u,t,(-.78,0,0),0 if name=="high_five" else .85)
                apply_weighted(partner,name,u,t,(.78,0,0),0 if name=="high_five" else -.85)
                if name=="high_five":contact=high_five_contact(actor,partner,u)
                else:contact=None
                actor.pose("happy");partner.pose("happy")
            else:
                p=apply_weighted(actor,name,u,t,base,yaw)
                actor.pose("shocked" if name=="fall" and .25<u<.8 else "happy" if name=="jump" and .25<u<.8 else "neutral")
            # Keep both soles at landing location using mean support correction;
            # track residual for each rigid leg rather than claim exact two-foot IK.
            if name=="jump" and t>=1.1:
                feet=soles(actor)
                if landing is None:landing=[x.copy() for x in feet]
                d=(landing[0]+landing[1]-feet[0]-feet[1])/2;d.z=0
                actor.root.location+=d;bpy.context.view_layer.update()
            feet=soles(actor)
            anchor=actor.root.location.copy() if lock else Vector((0,0,0));anchor.z=0
            # Smooth translated camera for locomotion; frame-safe full body.
            cam.location=anchor+Vector((5,-10,2.6)) if lock else Vector((2.5,-10,2.7))
            point_at(cam,anchor+Vector((0,0,1.42)))
            cam.data.ortho_scale=5.2 if not paired else 5.8
            for obj,offset in zip(lights,((-3,-5,6),(4,-4,4),(0,3,5))):
                obj.location=anchor+Vector(offset);point_at(obj,anchor+Vector((0,0,1.3)))
            bpy.context.view_layer.update()
            heroes=[actor,partner] if paired else [actor]
            b=metrics(scene,cam,heroes)
            if not all(x["body_safe"] for x in b):
                # Deterministic wider review framing, not crop.
                for _ in range(12):
                    cam.data.ortho_scale*=1.045;bpy.context.view_layer.update();b=metrics(scene,cam,heroes)
                    if all(x["body_safe"] for x in b):break
            assert all(x["body_safe"] for x in b),(idx,f,b)
            row={"frame":f+1,"seconds":t,"phase":p["phase"],"floor":floor(actor),"soles":[list(x) for x in feet],"bounds":b,"flight":p["flight"],"lift":p["lift"],"camera_scale":cam.data.ortho_scale}
            if name=="jump" and landing is not None:row["landing_sole_drift"]=[(a-b).length for a,b in zip(feet,landing)]
            if paired and name=="high_five":row["hand_contact_error"]=contact
            rows.append(row)
            scene.render.filepath=str(clip/f"frame_{f+1:04d}.png");bpy.ops.render.render(write_still=True)
        report={"index":idx,"role":role,"action":name,"frames":N,"fps":FPS,"rows":rows,"motion_review_pending":True}
        if lock:
            report["stride"]=lock.report();assert report["stride"]["pass"],report["stride"]
        if name=="jump":
            airborne=[x for x in rows if x["flight"]];ground=[x for x in rows if not x["flight"]]
            drifts=[max(x["landing_sole_drift"]) for x in rows if "landing_sole_drift" in x]
            report["jump"]={"airborne_frames":len(airborne),"apex_height":max(x["floor"] for x in airborne),"max_ground_error":max(abs(x["floor"]) for x in ground),"max_landing_sole_drift":max(drifts),"landing_frames":len(drifts)}
            assert report["jump"]["max_ground_error"]<=.002 and report["jump"]["apex_height"]>.25 and len(airborne)>=15,report["jump"]
            # Drift is disclosed for review, not silently treated as planted.
        if name=="high_five":report["min_hand_contact_error"]=min((x["hand_contact_error"] for x in rows if x.get("hand_contact_error") is not None),default=None)
        (clip/"metrics.json").write_text(json.dumps(report,indent=2)+"\n")
        print("MOTION_CLIP",json.dumps({k:v for k,v in report.items() if k not in ("rows","stride")}),flush=True)
        results.append({"clip":clip.name,"action":name,"role":role,"frames":N})
    (out/"part.json").write_text(json.dumps(results,indent=2)+"\n")
if __name__=="__main__":main()
