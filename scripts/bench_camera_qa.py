"""Story-local camera QA adapters around the existing library. No motion edits.

The driver should call geometry() on *every* evaluated shot frame, then
rendered_visibility() on representative frames before a full render. The
legacy helper's 60% pass flag is not sufficient: this exam uses 69%.
"""
from library_camera import project
from camera_visibility import visibility_gate
from r6_character import mesh_points
import bpy

def in_frame(b,margin=.035):
    return b[4]>0 and margin<=b[0]<=b[1]<=1-margin and margin<=b[2]<=b[3]<=1-margin

def geometry(scene,cam,actors,heroes,kind):
    """actors maps story names to Actor instances; heroes explicitly shot-local.
    For close-ups, require full head safety, not full-body framing.
    Inserts require an independent prop boundary/contact check.
    """
    rows={}
    for name in heroes:
        a=actors[name]
        body=project(scene,cam,[v for ob in a.meshes() for v in mesh_points(ob)])
        head=project(scene,cam,mesh_points(a.a.head))
        coverage=max(0,min(1,body[3])-max(0,body[2]))
        body_required=kind in ('medium','wide')
        rows[name]={'body_bounds':list(body),'head_bounds':list(head),
            'coverage':coverage,'body_safe':in_frame(body),'head_safe':in_frame(head),
            'pass':in_frame(head) and (not body_required or (coverage>=.45 and in_frame(body)))}
    return rows

def prop_geometry(scene,cam,root):
    meshes=[ob for ob in root.children_recursive if ob.type=='MESH' and not ob.hide_render]
    bounds=project(scene,cam,[v for ob in meshes for v in mesh_points(ob)])
    return {'bounds':list(bounds),'pass':in_frame(bounds)}

def rendered_visibility(scene,out,segment,actors,heroes):
    """Actual rendered object-ID fraction; diagnostic render must succeed.
    Uses repository helper, explicitly overrides its weaker threshold in the report.
    No geometry-only fallback is considered a pass.
    """
    groups={name:[ob for ob in actors[name].meshes() if ob!=actors[name].a.face] for name in heroes}
    if not groups:return {}
    old_pct=scene.render.resolution_percentage
    old_filepath=scene.render.filepath
    try:
        scene.render.resolution_percentage=50
        result=visibility_gate(scene,out,segment,groups)
        for value in result.values():
            value['visible_fraction']=1-value['occluded_fraction']
            value['threshold']=.69
            value['pass']=value['projected_silhouette_pixels']>0 and value['visible_fraction']>=.69
        return result
    finally:
        scene.render.resolution_percentage=old_pct
        scene.render.filepath=old_filepath
