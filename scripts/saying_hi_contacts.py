"""Opt-in Blender story props and geometric contact diagnostics. No locked module edits.
These are candidate helpers; run evaluated meshes and inspect actual pixels before approval.
"""
import bpy, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from render_demo import cube,empty,material
from stage_a_cafe import cylinder

def surface_tree(obj):
    dep=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(dep);me=ev.to_mesh()
    try:
        pts=[ev.matrix_world@v.co for v in me.vertices]
        polys=[tuple(p.vertices) for p in me.polygons]
        return BVHTree.FromPolygons(pts,polys,all_triangles=False),pts
    finally:ev.to_mesh_clear()

def contact_metrics(hand_mesh,prop_mesh):
    """Minimum sampled vertex-to-surface distance, plus intersecting triangle/polygon pairs.
    Distances are surface samples, not exact continuous signed clearance; overlap may include touch.
    """
    a,ap=surface_tree(hand_mesh);b,bp=surface_tree(prop_mesh)
    gaps=[b.find_nearest(v)[3] for v in ap]+[a.find_nearest(v)[3] for v in bp]
    return {"sampled_min_surface_gap":min(gaps),"surface_overlap_pairs":len(a.overlap(b))}

def attach_to_socket(prop,socket,local_offset=(0,0,0)):
    """Call every sample after pose evaluation; caller supplies separate hand sockets."""
    bpy.context.view_layer.update()
    prop.matrix_world=socket.matrix_world.copy()
    prop.location=socket.matrix_world@Vector(local_offset)
    bpy.context.view_layer.update()
    return {"socket_to_target_error":(prop.matrix_world.translation-(socket.matrix_world@Vector(local_offset))).length}

def carry_two(chart,pencil,left_socket,right_socket,chart_offset=(0,0,0),pencil_offset=(0,0,0)):
    if left_socket==right_socket:raise ValueError("Two props require two distinct sockets")
    return {"chart":attach_to_socket(chart,left_socket,chart_offset),"pencil":attach_to_socket(pencil,right_socket,pencil_offset)}

def seat_metrics(hip_mesh,foot_meshes,seat_top,ground=0):
    """Hip underside to horizontal support plane; each foot's lowest evaluated world vertex.
    Caller must separately check seat footprint coverage and body/seat mesh overlap.
    """
    _,hip=surface_tree(hip_mesh)
    return {"signed_hip_plane_gap":min(v.z for v in hip)-seat_top,
            "signed_foot_plane_gaps":[min(v.z for v in surface_tree(f)[1])-ground for f in foot_meshes]}

def stance_drift(samples):
    """Samples are ordered (time, world sole contact XYZ, stance bool), per foot.
    Measures only consecutive stance intervals, not swing.
    """
    displacements=[(Vector(b[1])-Vector(a[1])).length for a,b in zip(samples,samples[1:]) if a[2] and b[2]]
    return {"stance_intervals":len(displacements),"max_step_drift":max(displacements,default=None),"total_drift":sum(displacements)}

def waffle(name="Waffle"):
    """Original cuboid dog, local -Y forward, Z up; no external assets."""
    root=empty(name,(0,0,0))
    body=empty(name+" roll pivot",(0,0,.29),root)
    caramel=material(name+" caramel",(.62,.32,.13));cream=material(name+" cream",(.91,.75,.49));dark=material(name+" nose",(.08,.055,.04))
    cube(name+" body",(0,0,0),(.36,.62,.31),caramel,body,bevel=.035)
    cube(name+" head",(0,-.39,.13),(.36,.32,.34),cream,body,bevel=.035)
    cube(name+" muzzle",(0,-.59,.075),(.25,.16,.16),cream,body,bevel=.025)
    cube(name+" nose",(0,-.68,.11),(.11,.045,.07),dark,body,bevel=.012)
    for x in (-.18,.18):
        cube(name+" ear",(x,-.38,.13),(.09,.23,.28),caramel,body,bevel=.025)
        cube(name+" eye",(x*.59,-.555,.18),(.036,.022,.047),dark,body,bevel=.005)
    legs=[]
    for x in (-.135,.135):
        for y in (-.21,.21):
            pivot=empty(name+" leg pivot",(x,y,-.10),body)
            cube(name+" leg",(0,0,-.11),(.115,.13,.22),cream,pivot,bevel=.015);legs.append(pivot)
    tail=empty(name+" tail pivot",(0,.30,.04),body)
    cube(name+" tail",(0,.105,.05),(.08,.22,.08),caramel,tail,bevel=.02)
    return root,body,legs,tail

def waffle_pose(dog,mode,u=0):
    root,body,legs,tail=dog
    if mode not in ("lie_down","roll_over"):raise ValueError(mode)
    u=max(0,min(1,u));body.rotation_euler=(0,0,0)
    for i,leg in enumerate(legs):leg.rotation_euler.x=(-1 if i%2 else 1)*1.45
    if mode=="roll_over":body.rotation_euler.y=2*math.pi*u
    tail.rotation_euler.z=.35*math.sin(2*math.pi*u)
    bpy.context.view_layer.update()
    # Ground evaluated dog geometry; no physics or collision solver.
    zs=[v.z for o in root.children_recursive if o.type=="MESH" for v in surface_tree(o)[1]]
    body.location.z-=min(zs)-root.matrix_world.translation.z
    bpy.context.view_layer.update()
    return {"evaluated_min_z":min(v.z for o in root.children_recursive if o.type=="MESH" for v in surface_tree(o)[1])}
