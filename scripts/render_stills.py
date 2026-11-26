"""Render three vertical Stage A stills with original procedural assets (CI entry point)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import point_at
from stage_a_character import Character,palette
from stage_a_cafe import build_cafe,set_visible


def args():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--output",default="render/stills")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])


def configure(profile):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=64 if profile=="preview" else 128
    scene.cycles.use_denoising=False
    scene.cycles.max_bounces=5
    scene.cycles.transparent_max_bounces=8
    scene.render.resolution_x,scene.render.resolution_y=(540,960) if profile=="preview" else (1080,1920)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    scene.world=bpy.data.worlds.new("Warm café ambient")
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value=(.55,.34,.18,1)
    bg.inputs[1].default_value=.22
    scene.view_settings.view_transform="Standard"
    scene.view_settings.exposure=-.35
    return scene


def camera_setup(scene, camera, position, target, lens, safe_meshes, margin=.06):
    camera.location=position
    camera.data.lens=lens
    camera.data.type="PERSP"
    point_at(camera,target)
    # Keep specified subjects within the portrait safe area. The close-up
    # deliberately crops the body, but never the head or hair.
    for _ in range(24):
        bpy.context.view_layer.update()
        projected=[world_to_camera_view(scene,camera,obj.matrix_world@Vector(corner))
                   for obj in safe_meshes for corner in obj.bound_box]
        if projected and all(margin<=v.x<=1-margin and margin<=v.y<=1-margin and v.z>0 for v in projected):
            return {"min_x":min(v.x for v in projected),"max_x":max(v.x for v in projected),
                    "min_y":min(v.y for v in projected),"max_y":max(v.y for v in projected),
                    "lens_mm":camera.data.lens}
        camera.data.lens*=.94
    raise RuntimeError("Could not fit intended subjects in portrait camera")


def main():
    a=args()
    output=Path(a.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    scene=configure(a.profile)
    table_cup,held=build_cafe()
    p=palette()
    lead=Character("Series lead",p,True)
    friend=Character("Cafe friend",p,False)
    # All expressions exist and can be swapped without modifying geometry.
    for expression in ("neutral","happy","shocked","sad"):
        lead.expression(expression)
        assert lead.face.data.materials[0] == p["faces"][expression]
    bpy.ops.object.camera_add()
    camera=bpy.context.object
    scene.camera=camera
    records=[]
    def render(name,expr,position,target,lens,subjects):
        framing=camera_setup(scene,camera,position,target,lens,subjects)
        scene.render.filepath=str(output/(name+".png"))
        bpy.ops.render.render(write_still=True)
        records.append({"file":name+".png","lead_expression":expr,"framing":framing})
        print("STAGE_A_RENDERED",name,framing,flush=True)
    # Close-up: preserve the readable decal while adapting to chunkier proportions.
    lead.root.location=(0,-.65,0)
    lead.pose("happy",((-.13,-.10,0),(-.18,.10,0)))
    friend.visible(False)
    set_visible(held,False)
    face_subjects=[o for o in lead.meshes if any(k in o.name for k in ("head","hair","fringe","decal"))]
    render("01_happy_closeup","happy",(.10,-3.55,2.34),(0,-.65,1.97),62,face_subjects)
    def aim_arm(actor,index,direction):
        arm=actor.arms[index]
        arm.rotation_mode="QUATERNION"
        arm.rotation_quaternion=Vector(direction).normalized().to_track_quat("-Z","Y")
    # Medium: grip with screen-left hand, table drink on screen-right.
    lead.root.location=(-.40,.05,0)
    lead.root.rotation_euler.z=.04
    lead.pose("shocked")
    aim_arm(lead,0,(.33,-.55,.27))
    aim_arm(lead,1,(-.30,-.42,.48))
    set_visible(held,True)
    lead.attach_cup(held,0)
    table_cup.location=(.36,-.35,1.18)
    # Table rim and legs can crop; the face, hand and both drinks must fit.
    upper=[o for o in lead.meshes if any(k in o.name for k in ("head","hair","fringe","decal","torso","palm","grip finger"))]
    props=[*held.children_recursive,*table_cup.children_recursive]
    render("02_shocked_medium","shocked",(-.25,-3.75,2.13),(-.26,.05,1.85),40,upper+props)
    # Portrait environmental shot: stagger depth instead of fitting the entire room horizontally.
    friend.visible(True)
    lead.root.location=(-.43,-.50,0)
    lead.root.rotation_euler.z=.06
    friend.root.location=(.69,.83,0)
    friend.root.rotation_euler.z=-.16
    friend.pose("sad",((-.20,-.08,0),(-.28,.10,0)))
    lead.expression("neutral")
    aim_arm(lead,0,(.31,-.55,.28))
    aim_arm(lead,1,(-.32,-.15,-.60))
    lead.attach_cup(held,0)
    # Deliberately crop peripheral architecture, not faces; foreground table fills lower frame.
    wide_subjects=[o for actor in (lead,friend) for o in actor.meshes
                   if any(k in o.name for k in ("head","hair","fringe","decal","beanie","torso"))]
    render("03_cafe_wide","neutral",(.10,-5.65,2.20),(.07,.02,1.69),43,
           wide_subjects+props)
    (output/"manifest.json").write_text(json.dumps({"profile":a.profile,"resolution":[scene.render.resolution_x,scene.render.resolution_y],
        "face_swaps_tested":["neutral","happy","shocked","sad"],"shots":records},indent=2)+"\n")
    print("STAGE_A_COMPLETE",flush=True)


if __name__=="__main__":
    main()
