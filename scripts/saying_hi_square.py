"""Authorized Itlay import with story-local well/wall adaptation.
Source: AdityapalW/Roblox-skill, pinned commit and git blob recorded in workflow.
"""
import bpy,math,json
from pathlib import Path
from mathutils import Vector,Matrix
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

def fountain_as_well(scenery):
    """Recenter and uniformly scale the actual named source fountain group.
    Bounds are evaluated in Blender world space, not guessed from source axes.
    """
    matches=[o for o in scenery.children_recursive if o.name=="Piazza fountain"]
    if len(matches)!=1:raise RuntimeError("Expected the one pinned native Piazza fountain group")
    fountain=matches[0];meshes=[o for o in fountain.children_recursive if o.type=="MESH"]
    if len(meshes)!=6:raise RuntimeError("Unexpected source fountain mesh count")
    def world_bounds():
        points=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
        return Vector(tuple(min(v[i] for v in points) for i in range(3))),Vector(tuple(max(v[i] for v in points) for i in range(3)))
    lo,hi=world_bounds();center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    scale=2.85/max(hi.x-lo.x,hi.y-lo.y)
    transform=Matrix.Scale(scale,4)@Matrix.Translation(-center)
    fountain.matrix_world=transform@fountain.matrix_world;bpy.context.view_layer.update()
    newlo,newhi=world_bounds()
    return {"source_group":fountain.name,"mesh_children":len(meshes),"original_world_min":list(lo),"original_world_max":list(hi),"uniform_scale":scale,"adapted_world_min":list(newlo),"adapted_world_max":list(newhi),"note":"Native source stone water feature is the story well; no duplicate added well, material assignments unchanged."}

def build_square(stage,gltf_path):
    scenery,provenance=import_itlay(gltf_path);provenance["native_well_adaptation"]=fountain_as_well(scenery)
    root=empty("Saying Hi story-local wall and seats",(0,0,0))
    stone=material("plaza pale limestone",(.58,.48,.34));trim=material("warm trim",(.75,.62,.43));wood=material("seat timber",(.30,.15,.065))
    # Leave source cobblestone visible; no coplanar replacement paving.
    h=stage["marks"]["wall_narrator"]["seat_height"]
    cube("tally wall",(0,8.27,h/2),(8.5,.66,h),stone,root,bevel=.02)
    cube("wall cap",(0,8.27,h-.035),(8.65,.72,.07),trim,root,bevel=.01)
    for cid in stage["layouts"]["initial"]["well"]:
        m=stage["marks"]["well_"+cid];x,y,_=m["xyz"];h=m["seat_height"]
        ob=cube("seat "+cid,(x,y,h-.055),(.70,.58,.11),wood,root,bevel=.02);ob.rotation_euler.z=math.radians(m["yaw_deg"])
        cube("pedestal "+cid,(x,y,(h-.11)/2),(.40,.37,h-.11),stone,root,bevel=.01)
    bench=stage.get("pair_bench")
    if bench:
        cx,cy,cz=bench["center"];dx,dy,dz=bench["dimensions"];top=bench["top"]
        cube("Actual pair seat",(cx,cy,cz),(dx,dy,dz),wood,root,bevel=.025)
        for side in (-1,1):
            cube("Pair bench leg",(cx,cy+side*(dy/2-.23),(top-dz)/2),(.60,.18,top-dz),stone,root,bevel=.02)
    provenance["adaptation"]="Actual source fountain recentered/scaled as the sole central water feature; source cobbles and facades preserved. Story-local wall and seats calibrated from measured seated pose data. No duplicate fountain or replacement paving."
    return root,provenance
