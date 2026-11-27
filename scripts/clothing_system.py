"""Chapter 3 textile and garment-fit layer for the unchanged source R6 rig.

This module is deliberately opt-in. Use clothed_character() for story/review
characters; the closed Chapter 1 motion and Chapter 2 expression builders stay
unchanged. It adds material detail and thin weighted garment shells without
editing source vertices, weights, bones, proportions or expression assets.
"""
import math
import bmesh
import bpy
from mathutils import Vector

from r6_character import bounds, group_points, dominant_group, matte
from r6_variant_character import apply_garments
from render_demo import cube

PALETTE_SRGB = {
    "hoodie": (104, 111, 116), "jacket": (176, 142, 95), "tee": (219, 198, 151),
    "cardigan": (161, 49, 87), "jeans": (34, 39, 46), "yellow_denim": (244, 164, 2),
    "stripe_pants": (25, 28, 33), "blue_denim": (25, 64, 128), "teacher_trousers": (47, 39, 57),
    "green_tee": (33, 151, 56), "blue_tee": (25, 89, 200),
    "green_student_denim": (29, 75, 162), "blue_student_denim": (250, 188, 3),
}

def _srgb_linear(value):
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _solid_fabric(actor, kind, suffix="raised detail", factor=1.0):
    rgb = PALETTE_SRGB[kind]
    color = tuple(_srgb_linear(v) * factor for v in rgb)
    material = matte(actor.role + " / " + kind + " " + suffix, color)
    _add_fabric_shader(material, kind)
    return material

ROLE_CLOTHES = {
    "lead": {"shirt": "hoodie", "pants": "jeans", "sleeve": "hoodie", "sleeve_cutoff": 0.14},
    "friend": {"shirt": "tee", "pants": "yellow_denim", "sleeve": "tee", "sleeve_cutoff": 0.48},
    "teacher": {"shirt": "cardigan", "pants": "teacher_trousers", "sleeve": "cardigan", "sleeve_cutoff": 0.14},
    "dad": {"shirt": "jacket", "pants": "stripe_pants", "sleeve": "jacket", "sleeve_cutoff": 0.14},
    "librarian": {"shirt": "cardigan", "pants": "blue_denim", "sleeve": "cardigan", "sleeve_cutoff": 0.14},
    "patron_green": {"shirt": "green_tee", "pants": "green_student_denim", "sleeve": "green_tee", "sleeve_cutoff": 0.48},
    "patron_blue": {"shirt": "blue_tee", "pants": "blue_student_denim", "sleeve": "blue_tee", "sleeve_cutoff": 0.48},
}
ARM_GROUPS = ("Left Arm_02", "Right Arm_03")
LEG_GROUPS = ("Left Leg_04", "Right Leg_05")
TORSO_GROUP = "Torso_00"


def _fabric_profile(kind):
    if "cardigan" in kind:
        return {"u": 38, "v": 26, "noise": 175, "distance": 0.0030, "roughness": 0.94}
    if "denim" in kind or kind in ("jeans", "teacher_trousers", "stripe_pants"):
        return {"u": 145, "v": 112, "noise": 205, "distance": 0.0025, "roughness": 0.88}
    if kind in ("green_tee", "blue_tee"):
        return {"u": 47, "v": 39, "noise": 115, "distance": 0.0055, "roughness": 0.93}
    if kind == "tee":
        return {"u": 112, "v": 92, "noise": 185, "distance": 0.0018, "roughness": 0.90}
    if kind == "hoodie":
        return {"u": 76, "v": 62, "noise": 160, "distance": 0.0025, "roughness": 0.92}
    return {"u": 102, "v": 128, "noise": 185, "distance": 0.0020, "roughness": 0.90}


def _add_fabric_shader(material, kind):
    if not material or not material.use_nodes:
        return
    nt = material.node_tree
    nodes = nt.nodes
    bs = nodes.get("Principled BSDF")
    if bs is None or any(n.label == "Chapter 3 woven fabric bump" for n in nodes):
        return
    profile = _fabric_profile(kind)
    bs.inputs["Roughness"].default_value = profile["roughness"]
    if "Specular IOR Level" in bs.inputs:
        bs.inputs["Specular IOR Level"].default_value = 0.035

    uv = nodes.new("ShaderNodeTexCoord")
    uv.label = "Garment atlas UVs"
    wave_u = nodes.new("ShaderNodeTexWave")
    wave_u.label = "Warp fibers"
    wave_u.wave_type = "BANDS"
    wave_u.bands_direction = "X"
    wave_u.inputs["Scale"].default_value = profile["u"]
    wave_u.inputs["Distortion"].default_value = 0.7
    wave_u.inputs["Detail"].default_value = 2.0
    wave_v = nodes.new("ShaderNodeTexWave")
    wave_v.label = "Weft fibers"
    wave_v.wave_type = "BANDS"
    wave_v.bands_direction = "Y"
    wave_v.inputs["Scale"].default_value = profile["v"]
    wave_v.inputs["Distortion"].default_value = 0.45
    wave_v.inputs["Detail"].default_value = 2.0
    noise = nodes.new("ShaderNodeTexNoise")
    noise.label = "Micro-fiber variation"
    noise.inputs["Scale"].default_value = profile["noise"]
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.72
    for node in (wave_u, wave_v, noise):
        nt.links.new(uv.outputs["UV"], node.inputs["Vector"])

    cross = nodes.new("ShaderNodeMath")
    cross.operation = "MULTIPLY"
    nt.links.new(wave_u.outputs["Fac"], cross.inputs[0])
    nt.links.new(wave_v.outputs["Fac"], cross.inputs[1])
    noise_weight = nodes.new("ShaderNodeMath")
    noise_weight.operation = "MULTIPLY"
    noise_weight.inputs[1].default_value = 0.16
    nt.links.new(noise.outputs["Fac"], noise_weight.inputs[0])
    height = nodes.new("ShaderNodeMath")
    height.operation = "ADD"
    nt.links.new(cross.outputs[0], height.inputs[0])
    nt.links.new(noise_weight.outputs[0], height.inputs[1])

    bump = nodes.new("ShaderNodeBump")
    bump.label = "Chapter 3 woven fabric bump"
    bump.inputs["Strength"].default_value = 0.58 if kind in ("green_tee", "blue_tee") else 0.23 if "cardigan" not in kind else 0.28
    bump.inputs["Distance"].default_value = profile["distance"]
    nt.links.new(height.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])


def _material(actor, token):
    # Use the atlas slot actually assigned to the polygons, not the
    # earlier unused solid-color slot with a similar name.
    used = {p.material_index for p in actor.body.data.polygons}
    for i, mat in enumerate(actor.body.data.materials):
        if i in used and mat and mat.name.split(" / ")[-1].split(".")[0] == token.strip(" /"):
            return mat
    raise RuntimeError("Missing garment material %s / %s" % (actor.role, token))


def _clean_candidate_atlas(material, kind):
    """Private in-memory texture; legacy generated atlas stays unchanged."""
    from r6_variant_textures import cloth
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / (kind + "_physical.png")
        cloth(kind, physical_details=True).save(path)
        img = bpy.data.images.load(str(path), check_existing=False)
        img.pack()
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE":
            node.image = img


def _cover_shoulder_caps(actor, material):
    # The UV cap panel maps its vertical coordinate across depth, so the
    # painted hand stripe can land on the upper shoulder. Override only
    # horizontal top caps with fabric. Preserve bare hands/forearms.
    ob = actor.body
    idx = len(ob.data.materials)
    ob.data.materials.append(material)
    for group in ARM_GROUPS:
        lo, hi = bounds(group_points(ob, group))
        for poly in ob.data.polygons:
            if dominant_group(ob, ob.data.vertices[poly.vertices[0]]) != group:
                continue
            zs = [(ob.matrix_world @ ob.data.vertices[i].co).z for i in poly.vertices]
            if min(zs) >= hi.z - 0.035:
                poly.material_index = idx


def _make_shell(actor, label, groups, arm_cutoff=None):
    body = actor.body
    shell = body.copy()
    shell.data = body.data.copy()
    bpy.context.collection.objects.link(shell)
    shell.name = actor.root.name + " / garment shell / " + label
    shell.data.name = shell.name + " mesh"

    group_by_vertex = [dominant_group(body, v) for v in body.data.vertices]
    group_bounds = {}
    if arm_cutoff is not None:
        for group in ARM_GROUPS:
            group_bounds[group] = bounds(group_points(body, group))

    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    remove = []
    for face in bm.faces:
        group = group_by_vertex[face.verts[0].index]
        if group not in groups:
            remove.append(face)
            continue
        if group in ARM_GROUPS and arm_cutoff is not None:
            world_z = sum((body.matrix_world @ body.data.vertices[v.index].co).z for v in face.verts) / len(face.verts)
            lo, hi = group_bounds[group]
            cutoff_z = lo.z + arm_cutoff * (hi.z - lo.z)
            if world_z < cutoff_z:
                remove.append(face)
    if not any(face not in remove for face in bm.faces):
        bm.free()
        bpy.data.objects.remove(shell, do_unlink=True)
        raise RuntimeError("No garment faces selected for %s" % label)
    bmesh.ops.delete(bm, geom=remove, context="FACES")
    bm.to_mesh(shell.data)
    bm.free()
    shell.data.update()

    solid = shell.modifiers.new("Fabric thickness — " + label, "SOLIDIFY")
    solid.thickness = 0.010
    solid.offset = 1.0
    solid.use_rim = True
    solid.use_even_offset = True
    solid.use_quality_normals = True
    bevel = shell.modifiers.new("Soft stitched garment edges — " + label, "BEVEL")
    bevel.width = 0.0022
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(32)
    actor.meshes.append(shell)
    return shell


def _add_box(actor, label, location, dimensions, material, bone="torso", bevel=0.004, rotation_y=0.0):
    ob = cube(actor.root.name + " / " + label, tuple(location), tuple(dimensions), material, bevel=bevel)
    for modifier in list(ob.modifiers):
        if modifier.type == "WEIGHTED_NORMAL":
            ob.modifiers.remove(modifier)
    ob.rotation_euler.y = rotation_y
    bpy.context.view_layer.update()
    actor.attach_mesh(ob, bone)
    return ob


def _add_button(actor, label, location, radius, material, bone="torso"):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=radius, location=tuple(location))
    ob = bpy.context.object
    ob.name = actor.root.name + " / " + label
    ob.scale.y = 0.34
    ob.data.materials.append(material)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.update()
    actor.attach_mesh(ob, bone)
    return ob


def _add_cuffs(actor, sleeve_material, cutoff):
    for key in ("right_arm", "left_arm"):
        group = actor.bones[key].name
        lo, hi = bounds(group_points(actor.body, group))
        extent = hi - lo
        center = (lo + hi) * 0.5
        z = lo.z + cutoff * extent.z + 0.021
        height = 0.042 if cutoff < 0.2 else 0.035
        _add_box(
            actor, key + " fabric cuff",
            (center.x, center.y, z),
            (extent.x + 0.014, extent.y + 0.014, height),
            sleeve_material, bone=key, bevel=0.006
        )


def _add_denim_pockets(actor, pants_material):
    for key in ("right_leg", "left_leg"):
        group = actor.bones[key].name
        lo, hi = bounds(group_points(actor.body, group))
        extent = hi - lo
        center = (lo + hi) * 0.5
        width = extent.x * 0.43
        height = extent.z * 0.18
        z = lo.z + extent.z * 0.73
        y = hi.y + 0.021
        _add_box(
            actor, key + " raised back pocket",
            (center.x, y, z), (width, 0.024, height),
            pants_material, bone=key, bevel=0.009
        )
        _add_box(
            actor, key + " pocket top stitch",
            (center.x, y + 0.014, z + height * 0.40),
            (width * 0.82, 0.006, 0.009),
            pants_material, bone=key, bevel=0.003
        )


def _add_tee_collar(actor, shirt_material):
    lo, hi = actor.torso_bounds
    center = (lo + hi) * 0.5
    bpy.ops.mesh.primitive_torus_add(
        major_segments=40, minor_segments=12,
        major_radius=0.118, minor_radius=0.014,
        location=(center.x, center.y, hi.z - 0.035)
    )
    ob = bpy.context.object
    ob.name = actor.root.name + " / raised cotton neckline"
    ob.data.materials.append(shirt_material)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.update()
    actor.attach_mesh(ob, "torso")


def _add_hoodie_details(actor, shirt_material):
    lo, hi = actor.torso_bounds
    center = (lo + hi) * 0.5
    extent = hi - lo
    front = lo.y - 0.022
    # Tapered, curved pouch: a shallow perimeter and a fuller middle,
    # with continuous UVs, smooth normals and actual cloth thickness.
    verts, faces, coords = [], [], []
    nx, nz = 12, 8
    for j in range(nz + 1):
        v = j / nz
        halfwidth = extent.x * (0.29 - 0.075 * v)
        for i in range(nx + 1):
            u = i / nx
            q = 2*u - 1
            x = center.x + q * halfwidth
            z = lo.z + extent.z * (0.15 + 0.24*v + 0.012*(1-q*q))
            depth = 0.005 + 0.027 * math.sin(math.pi*u) * math.sin(math.pi*v)**0.75
            verts.append((x, lo.y - 0.009 - depth, z))
            coords.append((u, v))
    for j in range(nz):
        for i in range(nx):
            a = j*(nx+1)+i
            faces.append((a, a+1, a+nx+2, a+nx+1))
    mesh = bpy.data.meshes.new(actor.role + " tapered fabric pouch")
    mesh.from_pydata(verts, [], faces); mesh.update()
    ob = bpy.data.objects.new(actor.root.name + " / tapered kangaroo pouch", mesh)
    bpy.context.collection.objects.link(ob)
    mesh.materials.append(shirt_material)
    uv = mesh.uv_layers.new(name="Pouch weave")
    for p in mesh.polygons:
        p.use_smooth = True
        for k in p.loop_indices:
            uv.data[k].uv = coords[mesh.loops[k].vertex_index]
    solid = ob.modifiers.new("Pouch textile edge", "SOLIDIFY")
    solid.thickness = 0.004
    solid.offset = -1
    actor.attach_mesh(ob, "torso")
    cord = matte(actor.role + " hoodie drawcord", (0.70, 0.72, 0.73))
    for sign in (-1, 1):
        _add_box(
            actor, "hoodie drawcord",
            (center.x + sign * extent.x * 0.045, front - 0.022, hi.z - extent.z * 0.29),
            (0.008, 0.008, extent.z * 0.25),
            cord, bevel=0.003
        )
    # A softly folded hood rests on the upper back; the head and source neck stay untouched.
    _add_box(
        actor, "hoodie folded hood",
        (center.x, hi.y + 0.045, hi.z - extent.z * 0.11),
        (extent.x * 0.54, 0.12, extent.z * 0.25),
        shirt_material, bevel=0.045
    )


def _add_cardigan_details(actor, shirt_material):
    lo, hi = actor.torso_bounds
    center = (lo + hi) * 0.5
    extent = hi - lo
    front = lo.y - 0.022
    trim = matte(actor.role + " cardigan raised knit trim", (0.28, 0.025, 0.075))
    _add_fabric_shader(trim, "cardigan")
    buttons = matte(actor.role + " cardigan warm pearl buttons", (0.78, 0.57, 0.34))
    _add_box(
        actor, "cardigan raised front placket",
        (center.x, front - 0.006, center.z),
        (extent.x * 0.095, 0.032, extent.z * 0.82),
        trim, bevel=0.008
    )
    for sign in (-1, 1):
        _add_box(
            actor, "cardigan raised collar",
            (center.x + sign * extent.x * 0.15, front - 0.012, hi.z - extent.z * 0.12),
            (extent.x * 0.10, 0.032, extent.z * 0.20),
            trim, bevel=0.006, rotation_y=sign * 0.38
        )
    for frac in (0.72, 0.52, 0.32, 0.12):
        _add_button(
            actor, "cardigan pearl button",
            (center.x, front - 0.034, lo.z + extent.z * frac),
            0.017, buttons
        )


def _add_jacket_details(actor, shirt_material):
    lo, hi = actor.torso_bounds
    center = (lo + hi) * 0.5
    extent = hi - lo
    front = lo.y - 0.024
    button = matte(actor.role + " jacket buttons", (0.72, 0.56, 0.34))
    flap = matte(actor.role + " jacket pocket flap", (0.42, 0.27, 0.14))
    _add_fabric_shader(flap, "jacket")
    for sign in (-1, 1):
        x = center.x + sign * extent.x * 0.26
        z = center.z + extent.z * 0.12
        _add_box(
            actor, "jacket front patch pocket",
            (x, front, z), (extent.x * 0.22, 0.026, extent.z * 0.17),
            shirt_material, bevel=0.009
        )
        _add_box(
            actor, "jacket raised pocket flap",
            (x, front - 0.019, z + extent.z * 0.095),
            (extent.x * 0.23, 0.026, extent.z * 0.055),
            flap, bevel=0.006
        )
        # Angular lapel panels give the jacket's front opening a real edge.
        verts = [
            (center.x + sign * extent.x * 0.045, front - 0.022, hi.z - extent.z * 0.045),
            (center.x + sign * extent.x * 0.30, front - 0.022, hi.z - extent.z * 0.045),
            (center.x + sign * extent.x * 0.11, front - 0.022, hi.z - extent.z * 0.37),
        ]
        mesh = bpy.data.meshes.new(actor.role + " jacket lapel mesh")
        mesh.from_pydata(verts, [], [(0, 1, 2)])
        mesh.update()
        ob = bpy.data.objects.new(actor.root.name + " / jacket raised lapel", mesh)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(shirt_material)
        solid = ob.modifiers.new("Lapel fabric thickness", "SOLIDIFY")
        solid.thickness = 0.012
        bevel = ob.modifiers.new("Lapel softened edge", "BEVEL")
        bevel.width = 0.004
        bevel.segments = 2
        bpy.context.view_layer.update()
        actor.attach_mesh(ob, "torso")
    for frac in (0.76, 0.58, 0.40, 0.22):
        _add_button(
            actor, "jacket front button",
            (center.x, front - 0.042, lo.z + extent.z * frac),
            0.018, button
        )


def _remove_old_teacher_cardigan_details(actor):
    tokens = ("cardigan raised placket", "cardigan raised collar", "raised cardigan button")
    for ob in list(actor.accessories):
        if any(token in ob.name.lower() for token in tokens):
            actor.accessories.remove(ob)
            if ob in actor.meshes:
                actor.meshes.remove(ob)
            bpy.data.objects.remove(ob, do_unlink=True)


def upgrade_character(actor):
    """Apply the textile, shell-fit and raised-detail pass once to one R6 actor."""
    if getattr(actor, "clothing_upgraded", False):
        return actor.clothing_report
    if actor.role not in ROLE_CLOTHES:
        raise ValueError("No Chapter 3 clothing recipe for role " + actor.role)

    cfg = ROLE_CLOTHES[actor.role]
    original_vertices = len(actor.body.data.vertices)
    original_bones = tuple(b.name for b in actor.armature.data.bones)

    # Student Green/Blue were still using the raw solid-colour R6 material slots.
    if actor.role in ("patron_green", "patron_blue"):
        actor.variant_garment = apply_garments(actor, cfg["shirt"], cfg["pants"])

    shirt = _material(actor, " / shirt")
    pants = _material(actor, " / pants")
    sleeve = _material(actor, " / sleeve")
    for material, kind in ((shirt, cfg["shirt"]), (pants, cfg["pants"]), (sleeve, cfg["sleeve"])):
        _add_fabric_shader(material, kind)
    # Raised geometry uses solid fabric materials, not an atlas sampled at an
    # arbitrary UV coordinate. The original atlas remains on the body shells.
    solid_shirt = _solid_fabric(actor, cfg["shirt"])
    solid_pants = _solid_fabric(actor, cfg["pants"])
    solid_sleeve = _solid_fabric(actor, cfg["sleeve"], "sleeve edge")

    if cfg["shirt"] in ("hoodie", "jacket"):
        _clean_candidate_atlas(shirt, cfg["shirt"])
    _cover_shoulder_caps(actor, solid_sleeve)
    shirt_groups = (TORSO_GROUP,) + ARM_GROUPS
    _make_shell(actor, "shirt and sleeves", shirt_groups, arm_cutoff=cfg["sleeve_cutoff"])
    _make_shell(actor, "trousers", LEG_GROUPS)

    _add_cuffs(actor, solid_sleeve, cfg["sleeve_cutoff"])
    if cfg["pants"] in ("jeans", "yellow_denim", "blue_denim", "green_student_denim", "blue_student_denim"):
        _add_denim_pockets(actor, solid_pants)

    if actor.role == "lead":
        _add_hoodie_details(actor, solid_shirt)
    elif actor.role in ("friend", "patron_green", "patron_blue"):
        _add_tee_collar(actor, solid_shirt)
    elif actor.role == "teacher":
        _remove_old_teacher_cardigan_details(actor)
        _add_cardigan_details(actor, solid_shirt)
    elif actor.role == "librarian":
        _add_cardigan_details(actor, solid_shirt)
    elif actor.role == "dad":
        _add_jacket_details(actor, solid_shirt)

    # The shared cube helper adds Weighted Normal modifiers that require
    # Auto Smooth; the bevelled garment details do not need those modifiers.
    for ob in list(actor.accessories):
        for modifier in list(ob.modifiers):
            if modifier.type == "WEIGHTED_NORMAL":
                ob.modifiers.remove(modifier)
    bpy.context.view_layer.update()
    if len(actor.body.data.vertices) != original_vertices:
        raise RuntimeError("Chapter 3 changed original body vertex count")
    if tuple(b.name for b in actor.armature.data.bones) != original_bones:
        raise RuntimeError("Chapter 3 changed original armature bones")

    report = {
        "role": actor.role,
        "garments": {"shirt": cfg["shirt"], "sleeves": cfg["sleeve"], "pants": cfg["pants"]},
        "sleeve_cutoff_fraction_from_wrist": cfg["sleeve_cutoff"],
        "fabric_shader": "UV cross-weave / knit bump + atlas color and stitched artwork",
        "garment_shells": ["shirt and sleeves", "trousers"],
        "shell_thickness_local_units": 0.010,
        "raised_details": {
            "cuffs": True,
            "denim_back_pockets": cfg["pants"] in ("jeans", "yellow_denim", "blue_denim", "green_student_denim", "blue_student_denim"),
            "hoodie_pouch_drawcords_folded_hood": actor.role == "lead",
            "tee_neckline": actor.role in ("friend", "patron_green", "patron_blue"),
            "cardigan_placket_collar_buttons": actor.role in ("teacher", "librarian"),
            "jacket_lapels_pockets_buttons": actor.role == "dad",
        },
        "original_body_vertices_preserved": original_vertices,
        "original_armature_bones_preserved": len(original_bones),
    }
    actor.clothing_upgraded = True
    actor.clothing_report = report
    print("CHAPTER3_CLOTHING_UPGRADE " + str(report), flush=True)
    return report
