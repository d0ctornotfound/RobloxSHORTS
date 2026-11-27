"""Chapter 3 garment-only runtime layer for the approved articulated poses."""
import bpy
import bmesh
from mathutils import Vector
from r6_character import dominant_group
from chapter1_articulation import tree_for_object
from clothing_system import ROLE_CLOTHES, ARM_GROUPS

def filter_shell(ob, selected):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bad = [p for p in bm.faces if dominant_group(ob, ob.data.vertices[p.verts[0].index]) in selected]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context="FACES")
    count = len(bm.faces)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return count

def make_piece_shell(actor, source, cutoff=None, rim=True):
    ob = source.copy(); ob.data = source.data.copy()
    bpy.context.collection.objects.link(ob)
    ob.name = source.name + " / articulated garment shell"
    if cutoff is not None:
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=1e-6, plane_co=(0,0,cutoff), plane_no=(0,0,1), clear_inner=True)
        count = len(bm.faces)
        bm.to_mesh(ob.data); bm.free(); ob.data.update()
        if not count:
            bpy.data.objects.remove(ob, do_unlink=True)
            return None
    # Same world thickness as the original weighted shell: the source
    # GLB is scaled down, while articulated geometry is in scene units.
    solid = ob.modifiers.new("Articulated garment thickness", "SOLIDIFY")
    solid.thickness = .010 * actor.scale
    solid.offset = 1
    solid.use_rim = rim
    solid.use_even_offset = True
    actor.meshes.append(ob)
    return ob

class ArticulatedClothes:
    """Mirror evaluated locked limb pieces, without feeding shells to motion metrics."""
    def __init__(self, actor, articulation):
        self.actor = actor
        self.pieces = []
        self.trims = []
        selected = set(articulation.limbs)
        for ob in list(actor.meshes):
            if " / garment shell / " not in ob.name:
                continue
            if not filter_shell(ob, selected):
                actor.meshes.remove(ob); bpy.data.objects.remove(ob, do_unlink=True)
        for group, limb in articulation.limbs.items():
            is_arm = group in ARM_GROUPS
            cut = limb.end.z + ROLE_CLOTHES[actor.role]["sleeve_cutoff"]*(limb.top.z-limb.end.z)
            for source, origin in ((limb.upper, limb.top), (limb.lower, limb.mid)):
                shell = make_piece_shell(actor, source, cut-origin.z if is_arm else None, rim=limb.fabric is None)
                if shell is not None:
                    self.pieces.append((shell, source, False))
            if limb.fabric is not None:
                shell = make_piece_shell(actor, limb.fabric, rim=False)
                self.pieces.append((shell, limb.fabric, True))
            key = next(k for k,b in actor.bones.items() if b.name == group)
            for trim in actor.accessories:
                if " / "+key+" " not in trim.name:
                    continue
                if not any(token in trim.name for token in ("fabric cuff", "raised back pocket", "pocket top stitch")):
                    continue
                world = trim.matrix_world.copy()
                source = limb.upper if world.translation.z >= limb.mid.z else limb.lower
                self.trims.append((trim, source, source.matrix_world.inverted() @ world))
        self.sync()

    def sync(self):
        for shell, source, dynamic in self.pieces:
            shell.matrix_world = source.matrix_world
            if dynamic:
                for a,b in zip(shell.data.vertices, source.data.vertices):
                    a.co = b.co
                shell.data.update()
        for trim, source, relative in self.trims:
            trim.matrix_world = source.matrix_world @ relative
        bpy.context.view_layer.update()

    def source_pairs(self):
        return [(shell, source) for shell,source,_ in self.pieces]

def clearance_metrics(actor, articulated=None):
    """Evaluated outer-shell-to-source residual, NOT an inter-limb collision proof."""
    pairs = [(ob,actor.body) for ob in actor.meshes if " / garment shell / " in ob.name]
    if articulated:
        pairs += articulated.source_pairs()
    trees = {}
    max_gap = 0.0
    vertices = 0
    deps = bpy.context.evaluated_depsgraph_get()
    for shell, source in pairs:
        if source.name not in trees:
            trees[source.name] = tree_for_object(source)
        tree = trees[source.name]
        ev = shell.evaluated_get(deps); mesh = ev.to_mesh()
        try:
            for v in mesh.vertices:
                p = ev.matrix_world @ v.co
                hit = tree.find_nearest(p)
                if hit[0] is None:
                    raise RuntimeError("Missing shell source surface")
                max_gap = max(max_gap,hit[3]); vertices += 1
        finally:
            ev.to_mesh_clear()
    trim_error = max(((trim.matrix_world.translation-(source.matrix_world @ rel).translation).length
        for trim,source,rel in articulated.trims),default=0.0) if articulated else 0.0
    return {"shell_count":len(pairs),"shell_vertices":vertices,"max_source_gap":max_gap,
        "max_articulated_trim_tracking_error":trim_error,
        "pass_tracking":bool(vertices) and max_gap <= .035 and trim_error <= .001}
