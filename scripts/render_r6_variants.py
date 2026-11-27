"""Render the two variant approval stills; no animation workflow."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_stills import configure
from render_demo import cube
from stage_a_cafe import light,set_visible
from quality_cafe import build as cafe
from stage_c_props import build_plate_and_slice
from r6_character import ASSET,SOURCE_SHA256,matte,mesh_points
from r6_variant_character import VariantCharacter
from render_r6_stills import camera,actor_bounds,smoke

def main():
    p=argparse.ArgumentParser();p.add_argument("--shot",choices=("00_variant_lineup","01_variant_cafe"),required=True);p.add_argument("--output",default="render/variants")
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene=configure("preview");scene.cycles.samples=96;scene.cycles.adaptive_threshold=.035
    scene.view_settings.view_transform="AgX";scene.view_settings.look="AgX - Medium High Contrast";scene.view_settings.exposure=.05
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.48,.46,.43,1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.35
    if a.shot=="00_variant_lineup":
        scene.render.resolution_x,scene.render.resolution_y=1920,1080
        gray=matte("Neutral studio",(.30,.32,.35))
        cube("Studio floor",(0,0,-.08),(500,500,.16),gray,bevel=0)
        cube("Studio background",(0,4,4),(35,.2,9),gray,bevel=0)
        light("Studio key",(-3,-4,5),(0,0,1.25),700,4,(1,.96,.91))
        light("Studio fill",(3,-4,3.2),(0,0,1.25),470,5,(.91,.96,1))
        light("Studio rim",(0,2.8,4.8),(0,0,1.25),320,3,(1,1,1))
        roles=("lead","friend","teacher","dad");positions=((-2.82,0,0),(-.94,0,0),(.94,0,0),(2.82,0,0))
        cam=camera(scene,(0,-10,2.65),(0,0,1.30),8.0,True)
    else:
        scene.render.resolution_x,scene.render.resolution_y=720,1280
        for drink in cafe():set_visible(drink,False)
        roles=("lead","friend");positions=((-1.0,.76,0),(1.0,.76,0))
        plate,cake=build_plate_and_slice(.29);plate.location=(.04,-.03,1.18);cake.location=(.04,-.03,1.245)
        light("Variant cafe frontal bounce",(0,-3,3.4),(0,.85,1.65),340,4.2,(1,.95,.88))
        cam=camera(scene,(0,-3.8,2.18),(0,.72,1.58),52)
    actors=[VariantCharacter(role,role) for role in roles]
    checks={actor.role:smoke(actor) for actor in actors}
    expressions={"lead":"smug","friend":"happy","teacher":"unimpressed","dad":"worried"}
    for actor,pos in zip(actors,positions):
        actor.root.location=pos
        actor.pose(expressions[actor.role])
        if a.shot=="01_variant_cafe":
            from render_story import seat,shoulder,arm_length,rim_contact
            side=1 if actor.role=="lead" else -1;chair="Chair 1" if side==1 else "Chair 2"
            seat(actor,pos[0],pos[1],chair)
            idx=max(range(2),key=lambda i:side*shoulder(actor,i).x)
            length=arm_length(actor,idx)
            j=shoulder(actor,idx);center=Vector((.04,-.03,1.18));dx=center.x-side*.29-j.x;dz=1.24-j.z
            actor.root.location.y+=center.y+max(.04,length*length-dx*dx-dz*dz)**.5-j.y
            bpy.context.view_layer.update()
            target,direction=rim_contact(actor,idx,center,.29,length,side)
            actor.aim_arm(idx,direction)
            actor.aim_arm(1-idx,(0,-.15,-.98))
            assert (actor.grips[idx].matrix_world.translation-target).length<.002
    bpy.context.view_layer.update()
    for _ in range(45):
        protected=[actor_bounds(scene,cam,x,a.shot!="00_variant_lineup") for x in actors]
        if all(.035<=b[0] and b[1]<=.965 and .035<=b[2] and b[3]<=.965 for b in protected):break
        if cam.data.type=="ORTHO":cam.data.ortho_scale*=1.035
        else:cam.data.lens*=.97
    else:raise RuntimeError(("camera failed",protected))
    if a.shot=="00_variant_lineup":assert all(b[3]-b[2]>.45 for b in protected),protected
    rec={"shot":a.shot,"source_sha256":SOURCE_SHA256,"source_size":ASSET.stat().st_size,"samples":scene.cycles.samples,
         "resolution":[scene.render.resolution_x,scene.render.resolution_y],
         "characters":[{"role":x.role,"bones":list(x.armature.pose.bones.keys()),"skinned_mesh_count":len(x.skinned),"measurements":x.measurements,
          "skin_tone":x.variant_skin,"garment":x.variant_garment,"facial_hair":x.facial_hair,"expression":expressions[x.role],"expression_count":len(x.face_materials),
          "protected_bounds":b,"whole_body_bounds":actor_bounds(scene,cam,x),"smoke_test":checks[x.role]} for x,b in zip(actors,protected)]}
    for actor in actors:
        assert len(actor.skinned)==2 and len(actor.face_materials)==9
        for ob in actor.accessories:assert ob.parent==actor.armature and ob.parent_type=="BONE"
    scene.render.filepath=str(out/(a.shot+".png"))
    (out/(a.shot+".json")).write_text(json.dumps(rec,indent=2)+"\n")
    print("R6_VARIANT_VALIDATED",json.dumps(rec),flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(a.shot+".blend")))
    bpy.ops.render.render(write_still=True)
if __name__=="__main__":main()
