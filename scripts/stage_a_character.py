"""Original procedural R6-style actors and face decals for Stage A."""
import math

import bpy
import numpy as np
from mathutils import Vector

from render_demo import cube, empty, material

EXPRESSIONS = ("neutral", "happy", "shocked", "sad")


def fabric(name, colors, striped=False):
    """Object-local woven yarn, fine cross threads and raised stitch relief."""
    mat = material(name, colors[0])
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = .88
    shader.inputs["Sheen Weight" if "Sheen Weight" in shader.inputs else "Sheen"].default_value = .22
    coord = nodes.new("ShaderNodeTexCoord")
    def wave(axis, scale):
        w = nodes.new("ShaderNodeTexWave")
        w.wave_type = "BANDS"
        w.bands_direction = axis
        w.inputs["Scale"].default_value = scale
        w.inputs["Distortion"].default_value = .7
        links.new(coord.outputs["Generated"], w.inputs["Vector"])
        return w.outputs["Fac"]
    def math_node(op, a, b):
        node = nodes.new("ShaderNodeMath")
        node.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (float, int)):
                node.inputs[i].default_value = v
            else:
                links.new(v, node.inputs[i])
        return node.outputs[0]
    weave = math_node("MULTIPLY", wave("X", 36), wave("Z", 54))
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 95
    noise.inputs["Detail"].default_value = 2
    links.new(coord.outputs["Generated"], noise.inputs["Vector"])
    relief = math_node("ADD", math_node("MULTIPLY", weave, .7),
                       math_node("MULTIPLY", noise.outputs["Fac"], .3))
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .28
    bump.inputs["Distance"].default_value = .025
    links.new(relief, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    if striped:
        stripe = nodes.new("ShaderNodeTexWave")
        stripe.bands_direction = "Z"
        stripe.inputs["Scale"].default_value = 3.2
        links.new(coord.outputs["Generated"], stripe.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        ramp.color_ramp.elements[0].color = (*colors[0], 1)
        ramp.color_ramp.elements[1].position = .72
        ramp.color_ramp.elements[1].color = (*colors[1], 1)
        mid = ramp.color_ramp.elements.new(.54)
        mid.color = (*colors[2], 1)
        links.new(stripe.outputs["Fac"], ramp.inputs[0])
        base = ramp.outputs["Color"]
    else:
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*colors[0], 1)
        ramp.color_ramp.elements[1].color = (*colors[1], 1)
        links.new(noise.outputs["Fac"], ramp.inputs[0])
        base = ramp.outputs["Color"]
    grain = nodes.new("ShaderNodeMixRGB")
    grain.blend_type = "MULTIPLY"
    grain.inputs[0].default_value = .20
    links.new(base, grain.inputs[1])
    links.new(relief, grain.inputs[2])
    links.new(grain.outputs[0], shader.inputs["Base Color"])
    return mat


def face_image(expression):
    """RGBA decal from analytic strokes, not imported art. UV origin is lower left."""
    size = 512
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / (size - 1)
    alpha = np.zeros((size, size), dtype=np.float32)
    def ellipse(cx, cy, rx, ry):
        d = np.sqrt(((x-cx)/rx)**2 + ((y-cy)/ry)**2)
        np.maximum(alpha, np.clip((1-d)*min(rx,ry)*size, 0, 1), out=alpha)
    def stroke(points, width=.014):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx-ax, by-ay
            t = np.clip(((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy), 0, 1)
            d = np.sqrt((x-ax-t*dx)**2+(y-ay-t*dy)**2)
            np.maximum(alpha, np.clip((width-d)*size, 0, 1), out=alpha)
    for cx in (.33, .67):
        if expression == "happy":
            stroke([(cx-.055,.61),(cx-.035,.66),(cx,.68),(cx+.035,.66),(cx+.055,.61)], .017)
        elif expression == "shocked":
            ellipse(cx,.64,.047,.076)
            stroke([(cx-.065,.77),(cx,.79),(cx+.065,.77)], .013)
        else:
            ellipse(cx,.63,.034,.055)
            if expression == "sad":
                s = 1 if cx < .5 else -1
                stroke([(cx-s*.065,.72),(cx+s*.06,.77)], .014)
    if expression == "happy":
        stroke([(.36,.43),(.40,.37),(.46,.34),(.54,.34),(.60,.37),(.64,.43)], .025)
    elif expression == "shocked":
        ellipse(.5,.38,.081,.105)
    elif expression == "sad":
        stroke([(.37,.34),(.43,.40),(.50,.42),(.57,.40),(.63,.34)], .020)
    else:
        stroke([(.42,.39),(.50,.38),(.58,.39)], .017)
    rgba = np.empty((size,size,4), dtype=np.float32)
    rgba[:,:,:3] = (.028,.016,.012)
    rgba[:,:,3] = alpha
    img = bpy.data.images.new("Original face / "+expression, width=size, height=size, alpha=True)
    img.pixels.foreach_set(rgba.ravel())
    img.update()
    return img


def face_material(expression):
    mat = bpy.data.materials.new("Face decal / "+expression)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")
    clear = nodes.new("ShaderNodeBsdfTransparent")
    ink = nodes.new("ShaderNodeBsdfDiffuse")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = face_image(expression)
    tex.interpolation = "Linear"
    links.new(tex.outputs["Alpha"], mix.inputs[0])
    links.new(tex.outputs["Color"], ink.inputs["Color"])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(ink.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def palette():
    return {
        "skin": material("Warm skin", (.72,.43,.23)),
        "skin2": material("Peach skin", (.86,.60,.40)),
        "lead": fabric("Lead / teal cream rust knit", ((.035,.28,.27),(.75,.66,.43),(.65,.18,.075)), True),
        "friend": fabric("Friend / berry oat knit", ((.41,.07,.12),(.83,.66,.45),(.18,.08,.10)), True),
        "denim": fabric("Indigo denim", ((.024,.055,.12),(.13,.24,.39))),
        "shoe": material("Charcoal sneaker", (.045,.05,.055)),
        "sole": material("Cream rubber sole", (.65,.63,.55)),
        "hair": material("Lead / espresso hair", (.07,.032,.014)),
        "hat": fabric("Friend / mustard beanie knit", ((.45,.22,.03),(.90,.58,.12))),
        "faces": {name:face_material(name) for name in EXPRESSIONS},
    }


class Character:
    def __init__(self, name, p, lead=True):
        self.root = empty(name, (0,0,0))
        self.meshes = []
        self.arms = []
        self.face_materials = p["faces"]
        skin = p["skin" if lead else "skin2"]
        shirt = p["lead" if lead else "friend"]
        def box(label, loc, dims, mat, parent=None, bevel=.025):
            o = cube(name+" / "+label, loc, dims, mat, parent or self.root, bevel)
            self.meshes.append(o)
            return o
        box("torso", (0,0,1.70), (.90,.48,.90), shirt)
        self.head = box("head", (0,0,2.48), (.68,.61,.66), skin, bevel=.055)
        # A UV-mapped transparent face plane slightly in front of the head.
        verts = [(-.295,-.310,2.20),(.295,-.310,2.20),(.295,-.310,2.76),(-.295,-.310,2.76)]
        mesh = bpy.data.meshes.new(name+" face UV")
        mesh.from_pydata(verts, [], [(0,1,2,3)])
        mesh.update()
        uv = mesh.uv_layers.new(name="Face UV")
        for loop in mesh.loops:
            uv.data[loop.index].uv = [(0,0),(1,0),(1,1),(0,1)][loop.vertex_index]
        self.face = bpy.data.objects.new(name+" / expression decal", mesh)
        bpy.context.collection.objects.link(self.face)
        self.face.parent = self.root
        self.meshes.append(self.face)
        self.face.data.materials.append(p["faces"]["neutral"])
        if lead:
            box("hair cap", (0,.015,2.79), (.73,.65,.19), p["hair"], bevel=.055)
            for i,(x,z,w) in enumerate([(-.25,2.72,.19),(-.09,2.75,.22),(.10,2.78,.23),(.25,2.78,.16)]):
                tuft=box("swept fringe "+str(i),(x,-.255,z),(w,.19,.18),p["hair"],bevel=.035)
                tuft.rotation_euler.y=-.24
            box("back hair", (0,.26,2.61), (.70,.16,.37),p["hair"])
        else:
            box("beanie crown",(0,.015,2.82),(.74,.68,.28),p["hat"],bevel=.09)
            box("beanie cuff",(0,.01,2.72),(.77,.70,.12),p["hat"],bevel=.035)
        for side in (-1,1):
            arm = empty(name+" / shoulder",(side*.68,0,2.13), self.root)
            box("sleeve",(0,0,-.28),(.36,.44,.56),shirt,arm)
            box("hand",(0,0,-.70),(.35,.43,.30),skin,arm)
            self.arms.append(arm)
            leg=empty(name+" / hip",(side*.235,0,1.25),self.root)
            box("denim leg",(0,0,-.52),(.43,.45,1.04),p["denim"],leg)
            box("sneaker",(0,-.075,-1.10),(.45,.60,.22),p["shoe"],leg)
            box("rubber sole",(0,-.075,-1.205),(.46,.61,.065),p["sole"],leg,bevel=.012)

    def expression(self, name):
        self.face.data.materials[0] = self.face_materials[name]

    def visible(self, value):
        for mesh in self.meshes:
            mesh.hide_render = not value

    def pose(self, expression, arms=((0,0,0),(0,0,0))):
        self.expression(expression)
        for arm, rotation in zip(self.arms, arms):
            arm.rotation_euler = rotation

    def hand_position(self, index):
        bpy.context.view_layer.update()
        return self.arms[index].matrix_world @ Vector((0,0,-.70))
