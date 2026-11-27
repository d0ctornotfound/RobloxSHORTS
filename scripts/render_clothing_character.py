#!/usr/bin/env python3
"""Per-character Chapter 3 clothing review renders; baseline mode uses current assets."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from PIL import Image, ImageDraw, ImageFont

from library_character import clothed_character
from facial_expressions import disable_blinking

ACTORS = {
    "lead": ("Lead", "variant"),
    "friend": ("Friend", "variant"),
    "teacher": ("Teacher", "variant"),
    "dad": ("Dad", "variant"),
    "librarian": ("Librarian", "recipe"),
    "patron_green": ("Student Green", "standard"),
    "patron_blue": ("Student Blue", "standard"),
}
DETAIL_TARGETS = {
    "lead": (0.0, 0.0, 1.38, 1.10),
    "friend": (0.0, 0.0, 2.17, 0.90),
    "teacher": (0.0, 0.0, 1.38, 1.05),
    "dad": (0.0, 0.0, 1.38, 1.05),
    "librarian": (0.0, 0.0, 1.38, 1.05),
    "patron_green": (0.0, 0.0, 1.38, 1.05),
    "patron_blue": (0.0, 0.0, 1.38, 1.05),
}

def mat(name, color, roughness=0.9):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["Specular IOR Level"].default_value = 0.08
    return m

def cube(name, location, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(material)
    return ob

def point_at(obj, target):
    from mathutils import Vector
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()

def area_light(name, location, target, power, size, color):
    bpy.ops.object.light_add(type="AREA", location=location)
    ob = bpy.context.object
    ob.name = name
    ob.data.energy = power
    ob.data.shape = "DISK"
    ob.data.size = size
    ob.data.color = color
    point_at(ob, target)
    return ob

def studio():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_percentage = 100
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 6
    scene.render.film_transparent = False
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True
            scene.eevee.gtao_distance = 0.35
            scene.eevee.gtao_factor = 1.25
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = 0
    world = bpy.data.worlds.new("Chapter 3 neutral studio world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.34, 0.36, 0.39, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    scene.world = world
    gray = mat("Neutral grey seamless studio", (0.34, 0.36, 0.39))
    # A uniform world background is the seamless studio; no physical wall or
    # floor meshes are placed in the camera path, so every limb remains visible.
    walls = {}
    area_light("Large soft key", (-3.4, -4.2, 5.2), (0, 0, 1.25), 760, 4.2, (1.0, 0.96, 0.91))
    area_light("Front fill", (4.0, -3.0, 3.5), (0, 0, 1.25), 420, 4.0, (0.88, 0.93, 1.0))
    area_light("Rear rim", (0.0, 3.0, 4.4), (0, 0, 1.35), 520, 3.0, (1.0, 1.0, 1.0))
    area_light("Side fill", (4.0, 2.5, 3.0), (0, 0, 1.25), 260, 3.0, (0.90, 0.94, 1.0))
    bpy.ops.object.camera_add(location=(0, -6, 1.2))
    cam = bpy.context.object
    cam.name = "Chapter 3 clothing review camera"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 3.0
    scene.camera = cam
    return scene, cam, walls

def build_actor(key):
    label, kind = ACTORS[key]
    actor = clothed_character("Clothing review " + label, key)
    actor.root.location = (0, 0, 0)
    actor.root.rotation_euler = (0, 0, 0)
    actor.pose("neutral")
    disable_blinking(bpy.context.scene, [actor])
    bpy.context.view_layer.update()
    return actor

def font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def contact_sheet(root, label):
    names = ("front", "side", "back", "detail")
    tile = (1024, 1024)
    header = 74
    board = Image.new("RGB", (tile[0] * 2, tile[1] * 2 + header), (28, 31, 35))
    draw = ImageDraw.Draw(board)
    draw.text((24, 18), label.upper() + " — CLOTHING REVIEW", font=font(34), fill=(255, 255, 255))
    for i, name in enumerate(names):
        x = (i % 2) * tile[0]
        y = header + (i // 2) * tile[1]
        path = root / (name + ".png")
        if path.is_file():
            with Image.open(path) as raw:
                im = raw.convert("RGB").resize(tile, Image.Resampling.LANCZOS)
            board.paste(im, (x, y))
        else:
            draw.rectangle((x, y, x + tile[0], y + tile[1]), fill=(52, 55, 60))
            draw.text((x + 30, y + 470), "NOT RENDERED", font=font(30), fill=(240, 190, 110))
        draw.rectangle((x, y, x + 210, y + 48), fill=(12, 16, 20))
        draw.text((x + 16, y + 8), name.upper(), font=font(25), fill=(255, 255, 255))
    out = root / "clothing_contact_sheet.png"
    board.save(out)
    return out

def render_view(scene, cam, walls, actor, path, view, location, target, scale):
    cam.location = location
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    point_at(cam, target)
    scene.camera = cam
    bpy.context.view_layer.update()
    started = time.monotonic()
    print("CLOTHING_RENDER_START actor=%s view=%s engine=EEVEE denoising=OFF" % (actor.role, view), flush=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    elapsed = time.monotonic() - started
    if not path.is_file() or path.stat().st_size < 1000:
        raise RuntimeError("Missing/empty clothing render: " + str(path))
    print("CLOTHING_RENDER_DONE actor=%s view=%s seconds=%.2f bytes=%d" % (actor.role, view, elapsed, path.stat().st_size), flush=True)
    return elapsed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", required=True, choices=tuple(ACTORS))
    ap.add_argument("--output", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    label = ACTORS[args.actor][0]
    started = time.monotonic()
    scene, cam, walls = studio()
    actor = build_actor(args.actor)
    views = [
        ("front", (0, -6, 1.20), (0, 0, 1.20), 3.0),
        ("side", (6, 0, 1.20), (0, 0, 1.20), 3.0),
        ("back", (0, 6, 1.20), (0, 0, 1.20), 3.0),
    ]
    render_times = {}
    for name, loc, target, scale in views:
        render_times[name] = render_view(scene, cam, walls, actor, out / (name + ".png"), name, loc, target, scale)
    tx, ty, tz, detail_scale = DETAIL_TARGETS[args.actor]
    render_times["detail"] = render_view(
        scene, cam, walls, actor, out / "detail.png", "detail",
        (tx, -4.0, tz), (tx, ty, tz), detail_scale
    )
    sheet = contact_sheet(out, label)
    manifest = {
        "actor": args.actor,
        "label": label,
        "render_engine": "BLENDER_EEVEE",
        "denoising": False,
        "resolution": [1024, 1024],
        "views": ["front", "side", "back", "detail"],
        "render_seconds": render_times,
        "whole_character_job_seconds": round(time.monotonic() - started, 2),
        "contact_sheet": sheet.name,
        "clothing_upgrade": actor.clothing_report,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("CLOTHING_CHARACTER_COMPLETE " + json.dumps(manifest), flush=True)

if __name__ == "__main__":
    main()
