"""Authorized Itlay import with story-local well/wall adaptation.
Source: AdityapalW/Roblox-skill, pinned commit and git blob recorded in workflow.
"""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
from render_demo import cube,empty,material
from stage_a_cafe import cylinder

SOURCE_COMMIT="54b34ba1be2e3013a9de59e40db288d8f2ebda53"
SOURCE_BLOB="20108af3a19fae6b5beaa5fac2e3305b56112a41"

def import_itlay(path):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(Path(path).resolve()))
    imported=list(set(bpy.data.objects)-before)
    if not imported or not any(o.type=="MESH" for o in imported):
        raise RuntimeError("Itlay glTF did not produce scenery meshes")
    # glTF Y up -> Blender Z up. Preserve original scale/orientation and
    # material assignments. The source Town camera targets (0,2.9,1).
    root=empty("Itlay original scenery",(0,0,0))
    for ob in imported:
        if ob.parent is None:
            world=ob.matrix_world.copy();ob.parent=root;ob.matrix_world=world
    bpy.context.view_layer.update()
    return root,{"repository":"AdityapalW/Roblox-skill","commit":SOURCE_COMMIT,"file":"Itlay/Itlay.gltf","git_blob":SOURCE_BLOB,"mesh_objects":sum(o.type=="MESH" for o in imported),"objects":len(imported),"transform":"native Blender glTF axis conversion; root identity","texture_provenance":"Repository README: procedural geometry/textures with selected CC0 Poly Haven photo textures; individual texture attribution not supplied by source manifest."}

def build_square(stage,gltf_path):
    scenery,provenance=import_itlay(gltf_path)
    root=empty("Saying Hi story-local well and wall",(0,0,0))
    stone=material("plaza pale limestone",(.58,.48,.34));trim=material("warm trim",(.75,.62,.43))
    water=material("well blue water",(.06,.30,.38));brick=material("terracotta",(.42,.15,.09));wood=material("seat timber",(.30,.15,.065))
    # Reversible, local level support over the imported Town center.
    # No replacement facades or background. Confirm original paving elevation
    # and clashes on the smoke image before launching any motion render.
    cube("story support paving",(0,4,-.045),(12,13,.09),stone,root,bevel=.01)
    for x in range(-5,6):
        for y in range(-2,10):
            if (x+y)%2==0:cube("paving tile",(x,y,.004),(.97,.97,.008),trim,root,bevel=.003)
    for layer in range(3):
        for i in range(18):
            t=2*math.pi*(i+.5*(layer%2))/18
            ob=cube("well stone",(1.20*math.cos(t),1.20*math.sin(t),.20+layer*.36),(.41,.42,.35),stone,root,bevel=.025);ob.rotation_euler.z=t
    cylinder("water surface",(0,0,.54),1.02,.025,water,root)
    for x in (-1.35,1.35):cube("well roof post",(x,0,1.65),(.15,.15,2.7),wood,root,bevel=.01)
    for s in (-1,1):
        ob=cube("well roof",(0,s*.57,3.12),(3.12,1.42,.12),brick,root,bevel=.02);ob.rotation_euler.x=s*.32
    h=stage["marks"]["wall_narrator"]["seat_height"]
    cube("tally wall",(0,8.27,h/2),(8.5,.66,h),stone,root,bevel=.02)
    cube("wall cap",(0,8.27,h-.035),(8.65,.72,.07),trim,root,bevel=.01)
    for cid in stage["layouts"]["initial"]["well"]:
        m=stage["marks"]["well_"+cid];x,y,_=m["xyz"];h=m["seat_height"]
        ob=cube("seat "+cid,(x,y,h-.055),(.70,.58,.11),wood,root,bevel=.02);ob.rotation_euler.z=math.radians(m["yaw_deg"])
        cube("pedestal "+cid,(x,y,(h-.11)/2),(.40,.37,h-.11),stone,root,bevel=.01)
    provenance["adaptation"]="Story-local level platform, well, wall and seats; imported map objects remain present, no imported material changes. Alignment subject to smoke review."
    return root,provenance
