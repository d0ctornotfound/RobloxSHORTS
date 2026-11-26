"""Original cake and plate geometry, no external assets."""
import bpy
from render_demo import empty,material
from stage_a_cafe import cylinder


def wedge(name, parent, z, height, mat, scale=1):
    # Tip faces front, wide crust at rear. Flat base makes head contact exact.
    outline=[(0,-.22),(-.19,.17),(.19,.17)]
    verts=[(x*scale,y*scale,z+dz) for dz in (0,height) for x,y in outline]
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)])
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=parent
    obj.data.materials.append(mat)
    bevel=obj.modifiers.new("Soft cake edge","BEVEL")
    bevel.width=.009
    bevel.segments=2
    obj.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
    return obj


def build_plate_and_slice(plate_radius=.29):
    white=material("Plate / warm ivory",(.84,.72,.48))
    teal=material("Plate / glazed teal rim",(.008,.22,.17))
    sponge=material("Cake / golden sponge",(.59,.21,.035))
    filling=material("Cake / raspberry filling",(.58,.018,.035))
    frosting=material("Cake / vanilla icing",(.91,.68,.31))
    chocolate=material("Cake / cocoa icing",(.12,.032,.012))
    plate=empty("Story plate",(0,0,0))
    cylinder("Plate bottom",(0,0,.025),plate_radius-.035,.05,white,plate)
    cylinder("Plate colored edge",(0,0,.044),plate_radius,.042,teal,plate,top=plate_radius-.01)
    cylinder("Plate inner surface",(0,0,.061),plate_radius-.043,.008,white,plate)
    cake=empty("One last slice",(0,0,0))
    for name,z,height,mat in [
        ("Sponge base",0,.075,sponge),("Raspberry stripe",.075,.025,filling),
        ("Sponge middle",.10,.075,sponge),("Vanilla stripe",.175,.023,frosting),
        ("Sponge top",.198,.075,sponge),("Chocolate icing",.273,.035,chocolate),
        ("Vanilla icing",.308,.027,frosting)]:
        wedge(name,cake,z,height,mat)
    # A small red fruit identifies the same slice across the shots.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.053)
    fruit=bpy.context.object
    fruit.name="Cake / raspberry topper"
    fruit.parent=cake
    fruit.location=(0,.075,.37)
    fruit.data.materials.append(filling)
    return plate,cake
