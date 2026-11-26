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
    scene.cycles.samples=24 if profile=="preview" else 48
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
    bg.inputs[0].default_value=(.44,.53,.65,1)
    bg.inputs[1].default_value=.34
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
    def hold():
        hand=lead.hand_position(1)
        held.location=hand+Vector((.08,-.19,-.10))
        bpy.context.view_layer.update()
    # Close-up: face and fringe are the intentional safe-area subject.
    lead.root.location=(0,-.65,0)
    lead.root.rotation_euler.z=0
    lead.pose("happy",((-.13,-.10,0),(-.18,.10,0)))
    friend.visible(False)
    set_visible(held,False)
    face_subjects=[o for o in lead.meshes if any(k in o.name for k in ("head","hair","fringe","decal"))]
    render("01_happy_closeup","happy",(.10,-3.65,2.72),(0,-.65,2.30),62,face_subjects)
    # Medium: raised free hand and a drink physically adjacent to the other hand.
    lead.root.location=(-.63,-.30,0)
    lead.root.rotation_euler.z=.04
    lead.pose("shocked",((-1.65,.12,0),(-1.14,.07,0)))
    set_visible(held,True)
    hold()
    table_cup.location.x=-.10
    upper=[o for o in lead.meshes if not any(k in o.name for k in ("denim leg","sneaker","sole"))]
    props=[*held.children_recursive,*table_cup.children_recursive]
    render("02_shocked_medium","shocked",(-.40,-4.15,2.65),(-.48,-.30,2.35),48,upper+props)
    # Wide: standing actors, two cups and furniture share a complete portrait shot.
    friend.visible(True)
    lead.root.location=(-1.02,-.35,0)
    table_cup.location.x=.22
    friend.root.location=(1.22,-.35,0)
    friend.root.rotation_euler.z=-.14
    friend.pose("sad",((-.20,-.08,0),(-.28,.10,0)))
    lead.pose("neutral",((-.13,-.06,0),(-1.14,.07,0)))
    hold()
    set_objects=[o for o in bpy.context.scene.objects if o.type=="MESH" and
                 any(k in o.name for k in ("Cafe table top","Chair seat","Window glass","Pendant shade","Counter carcass"))]
    render("03_cafe_wide","neutral",(.15,-8.9,3.95),(0,.65,2.16),36,
           lead.meshes+friend.meshes+props+set_objects)
    (output/"manifest.json").write_text(json.dumps({"profile":a.profile,"resolution":[scene.render.resolution_x,scene.render.resolution_y],
        "face_swaps_tested":["neutral","happy","shocked","sad"],"shots":records},indent=2)+"\n")
    print("STAGE_A_COMPLETE",flush=True)


if __name__=="__main__":
    main()
