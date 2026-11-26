"""Procedural R6-inspired proof of concept; run with Blender in background mode."""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("preview", "full"), default="preview")
    parser.add_argument("--output", default="render")
    parser.add_argument("--still", action="store_true")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.78
    return mat


def cube(name, location, dimensions, mat, parent=None, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if parent:
        obj.parent = parent
    obj.location = location
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Soft edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def empty(name, location, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    obj.location = location
    return obj


def character(name, shirt, hair, palette):
    root = empty(name, (0, 0, 0))
    skin, pants, shoe, ink = (palette[key] for key in ("skin", "pants", "shoe", "ink"))
    body = [cube(name + " torso", (0, 0, 1.70), (0.90, 0.48, 0.90), shirt, root),
            cube(name + " head", (0, 0, 2.48), (0.68, 0.61, 0.66), skin, root),
            cube(name + " hair", (0, 0.025, 2.79), (0.72, 0.66, 0.17), hair, root)]
    # Characters face negative Y; the camera is on that side.
    for side in (-1, 1):
        cube(name + " eye", (side * 0.145, -0.312, 2.52), (0.075, 0.025, 0.10), ink, root, 0.008)
    cube(name + " smile", (0, -0.315, 2.34), (0.19, 0.025, 0.045), ink, root, 0.008)
    arms, legs = [], []
    for side in (-1, 1):
        arm = empty(name + " shoulder", (side * 0.68, 0, 2.13), root)
        body.append(cube(name + " sleeve", (0, 0, -0.28), (0.36, 0.44, 0.56), shirt, arm))
        body.append(cube(name + " hand", (0, 0, -0.70), (0.35, 0.43, 0.31), skin, arm))
        arms.append(arm)
        leg = empty(name + " hip", (side * 0.235, 0, 1.25), root)
        body.append(cube(name + " leg", (0, 0, -0.52), (0.43, 0.45, 1.04), pants, leg))
        body.append(cube(name + " shoe", (0, -0.075, -1.13), (0.45, 0.60, 0.24), shoe, leg))
        legs.append(leg)
    return root, arms, legs, body


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, location, power, size, color):
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = power
    light.data.shape = "DISK"
    light.data.size = size
    light.data.color = color
    point_at(light, (0, 0, 1.5))


def main():
    args = arguments()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fps, width, height, samples = (12, 360, 640, 4) if args.profile == "preview" else (24, 1080, 1920, 16)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = fps * 10
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output / "frame_")
    scene.world = bpy.data.worlds.new("Daylight")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value = (0.55, 0.68, 0.85, 1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value = 0.5
    colors = {"skin": (0.91, 0.64, 0.40), "pants": (0.08, 0.13, 0.22),
              "shoe": (0.10, 0.10, 0.13), "ink": (0.035, 0.027, 0.025),
              "blue": (0.07, 0.34, 0.91), "orange": (0.95, 0.30, 0.065),
              "hair": (0.14, 0.07, 0.03), "blond": (0.80, 0.50, 0.13),
              "grass": (0.24, 0.57, 0.26), "path": (0.62, 0.64, 0.68),
              "wall": (0.66, 0.77, 0.85), "roof": (0.24, 0.29, 0.40),
              "glass": (0.13, 0.38, 0.53), "trunk": (0.30, 0.14, 0.065)}
    p = {name: material(name, value) for name, value in colors.items()}
    cube("Ground", (0, 0, -0.20), (45, 45, 0.36), p["grass"], bevel=0)
    cube("Town walkway", (0, 0, -0.035), (18, 5.8, 0.07), p["path"], bevel=0)
    for i, x in enumerate((-7, -3.5, 0, 3.5, 7)):
        h = 4 + (i % 3) * 0.6
        cube("Town building", (x, 5.8, h / 2), (3.0, 3.4, h), p["wall"])
        cube("Roof", (x, 5.8, h + 0.08), (3.2, 3.6, 0.18), p["roof"])
        for z in (1.4, 2.7):
            for dx in (-0.72, 0.72):
                cube("Window", (x + dx, 4.08, z), (0.82, 0.06, 0.76), p["glass"])
    for x in (-5.5, 5.5):
        cube("Tree trunk", (x, 2.9, 1.0), (0.28, 0.28, 2.0), p["trunk"])
        cube("Tree canopy", (x, 2.9, 2.5), (1.45, 1.45, 1.65), p["grass"], bevel=0.14)
    a = character("Blue", p["blue"], p["hair"], p)
    b = character("Orange", p["orange"], p["blond"], p)
    area_light("Key", (-5, -5, 8), 1100, 5, (1, 0.87, 0.71))
    area_light("Fill", (5, -2, 5), 650, 5, (0.72, 0.85, 1))
    area_light("Rim", (0, 4, 7), 850, 4, (1, 0.94, 0.80))
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 8.7
    # Bake poses and camera at the actual output frame rate. All characters
    # stay within a conservative central safe area, including their limbs.
    for frame in range(1, scene.frame_end + 1):
        t = (frame - 1) / fps
        approach = min(t / 4.0, 1.0)
        stride = math.sin(t * math.tau * 1.3) * 0.48 if t < 4 else 0
        for index, (root, arms, legs, _) in enumerate((a, b)):
            sign = -1 if index == 0 else 1
            root.location = (sign * (2.0 - 1.0 * approach), 0, 0.04 + (0.06 * abs(stride)))
            root.rotation_euler.z = sign * 0.52 if t < 4 else sign * 0.15
            root.keyframe_insert("location", frame=frame)
            root.keyframe_insert("rotation_euler", frame=frame)
            for j in range(2):
                arms[j].rotation_euler.x = (-1 if j == 0 else 1) * stride
                legs[j].rotation_euler.x = (1 if j == 0 else -1) * stride
                arms[j].rotation_euler.y = 0
                if 5 <= t <= 8 and j == (1 if index == 0 else 0):
                    arms[j].rotation_euler.y = sign * (1.0 + 0.30 * math.sin(t * 8)) * min(1, (t-5)*3, (8-t)*3)
                arms[j].keyframe_insert("rotation_euler", frame=frame)
                legs[j].keyframe_insert("rotation_euler", frame=frame)
        camera.location = (0.55 * math.sin(t * 0.24), -10, 4.25)
        point_at(camera, (0, 0, 1.65))
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
    # Confirm framing of evaluated world-space object bounding boxes.
    # Orthographic scale refers to the longer image dimension in Blender.
    # Increase it automatically if the actual projection needs more space.
    for attempt in range(12):
        safe = True
        for frame in range(1, scene.frame_end + 1):
            scene.frame_set(frame)
            for actor in (a, b):
                for obj in actor[3] + [o for o in actor[0].children if o.type == "MESH"]:
                    for corner in obj.bound_box:
                        uv = world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
                        if not (0.07 <= uv.x <= 0.93 and 0.10 <= uv.y <= 0.90 and uv.z > 0):
                            safe = False
            if not safe:
                break
        if safe:
            break
        camera.data.ortho_scale *= 1.12
    else:
        raise RuntimeError("Character framing failed")
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    if args.still:
        scene.render.filepath = str(output / "still.png")
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
