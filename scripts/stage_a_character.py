"""Original procedural R6-style actors and face decals for Stage A."""
import math

import bpy
from array import array
from mathutils import Vector

from render_demo import cube, empty, material
from quality_textures import face_canvas

EXPRESSIONS = ("neutral","happy","smug","tired","worried","laughing","shocked","surprised","sad","unimpressed","embarrassed","angry","sleep_closed")


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
    """Shared transparent low-face decal artwork for all legacy R6 variants."""
    return face_canvas(expression).image("Original face / "+expression)

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
        "skin": material("Warm skin", (.69,.36,.14)),
        "skin2": material("Peach skin", (.84,.51,.27)),
        "lead": fabric("Lead / teal cream rust knit", ((.008,.19,.15),(.68,.41,.14),(.56,.055,.012)), True),
        "friend": fabric("Friend / berry oat knit", ((.35,.015,.045),(.75,.43,.18),(.10,.012,.035)), True),
        "denim": fabric("Indigo denim", ((.008,.025,.09),(.045,.12,.32))),
        "shoe": material("Charcoal sneaker", (.045,.05,.055)),
        "sole": material("Cream rubber sole", (.65,.63,.55)),
        "hair": material("Lead / espresso hair", (.07,.032,.014)),
        "hat": fabric("Friend / mustard beanie knit", ((.45,.15,.008),(.85,.38,.025))),
        "faces": {name:face_material(name) for name in EXPRESSIONS},
    }


class Character:
    def __init__(self, name, p, lead=True):
        self.root = empty(name, (0,0,0))
        self.meshes = []
        self.arms = []
        self.wrists = []
        self.grips = []
        self.fingers = []
        self.face_materials = p["faces"]
        self.current_expression="neutral";self._expression_tracks=[]
        skin = p["skin" if lead else "skin2"]
        shirt = p["lead" if lead else "friend"]
        def box(label, loc, dims, mat, parent=None, bevel=.025):
            o = cube(name+" / "+label, loc, dims, mat, parent or self.root, bevel)
            self.meshes.append(o)
            return o
        box("torso", (0,0,1.36), (1.02,.57,.77), shirt)
        self.head = box("head", (0,0,2.10), (.79,.67,.70), skin, bevel=.055)
        # A UV-mapped transparent face plane slightly in front of the head.
        verts = [(-.34,-.341,1.80),(.34,-.341,1.80),(.34,-.341,2.40),(-.34,-.341,2.40)]
        mesh = bpy.data.meshes.new(name+" face UV")
        mesh.from_pydata(verts, [], [(0,1,2,3)])
        mesh.update()
        uv = mesh.uv_layers.new(name="Face UV")
        for loop in mesh.loops:
            uv.data[loop.index].uv = [(0,0),(1,0),(1,1),(0,1)][loop.vertex_index]
        self.face = bpy.data.objects.new(name+" / expression decal", mesh)
        bpy.context.collection.objects.link(self.face)
        self.face.parent = self.root
        bpy.context.view_layer.update()
        face_world=self.face.matrix_world.copy()
        self.face.parent=self.head
        self.face.matrix_world=face_world
        self.meshes.append(self.face)
        self.face.data.materials.append(p["faces"]["neutral"])
        if lead:
            box("hair cap", (0,.015,2.43), (.84,.72,.19), p["hair"], bevel=.055)
            for i,(x,z,w) in enumerate([(-.29,2.36,.22),(-.10,2.39,.24),(.12,2.42,.25),(.29,2.42,.19)]):
                tuft=box("swept fringe "+str(i),(x,-.30,z),(w,.19,.18),p["hair"],bevel=.035)
                tuft.rotation_euler.y=-.24
            box("back hair", (0,.29,2.25), (.81,.16,.37),p["hair"])
        else:
            box("beanie crown",(0,.015,2.46),(.85,.74,.28),p["hat"],bevel=.09)
            box("beanie cuff",(0,.01,2.36),(.88,.76,.12),p["hat"],bevel=.035)
        for side in (-1,1):
            arm = empty(name+" / shoulder",(side*.74,0,1.72), self.root)
            box("sleeve",(0,0,-.28),(.43,.52,.56),shirt,arm)
            wrist=empty(name+" / wrist",(0,0,-.70),arm)
            box("palm",(0,.07,0),(.35,.17,.30),skin,wrist)
            digits=[]
            for sign in (-1,1):
                digit=box("grip finger",(sign*.155,-.095,0),(.09,.24,.17),skin,wrist,bevel=.025)
                digits.append(digit)
            socket=empty(name+" / cup grip",(0,-.137,-.145),wrist)
            self.arms.append(arm)
            self.wrists.append(wrist)
            self.grips.append(socket)
            self.fingers.append(digits)
            leg=empty(name+" / hip",(side*.265,0,.98),self.root)
            box("denim leg",(0,0,-.405),(.50,.54,.81),p["denim"],leg)
            box("sneaker",(0,-.075,-.875),(.52,.65,.19),p["shoe"],leg)
            box("rubber sole",(0,-.075,-.956),(.53,.66,.048),p["sole"],leg,bevel=.012)
        from facial_expressions import enable_blinking
        enable_blinking(bpy.context.scene,[self])

    def expression(self, name):
        if name not in self.face_materials:raise KeyError("Unknown face expression: "+name)
        self.current_expression=name
        self.face.data.materials[0] = self.face_materials[name]
        from facial_expressions import refresh_expression
        refresh_expression(self)

    def visible(self, value):
        for mesh in self.meshes:
            mesh.hide_render = not value

    def pose(self, expression, arms=((0,0,0),(0,0,0))):
        self.expression(expression)
        for arm, rotation in zip(self.arms, arms):
            arm.rotation_euler = rotation

    def hand_position(self, index):
        bpy.context.view_layer.update()
        return self.wrists[index].matrix_world.translation.copy()

    def upright_grip(self, index):
        """Keep cup axis vertical independently of shoulder angle."""
        bpy.context.view_layer.update()
        wrist=self.wrists[index]
        wrist.rotation_mode="QUATERNION"
        wrist.rotation_quaternion=self.arms[index].matrix_world.to_quaternion().inverted()
        bpy.context.view_layer.update()
        return self.grips[index]

    def grip_closed(self, index, closed=True):
        for sign,digit in zip((-1,1),self.fingers[index]):
            digit.location.x=sign*(.155 if closed else .20)
            digit.rotation_euler.z=0 if closed else sign*.30

    def attach_cup(self, cup, index):
        socket=self.upright_grip(index)
        self.grip_closed(index)
        cup.parent=socket
        cup.matrix_parent_inverse.identity()
        cup.location=(0,0,0)
        cup.rotation_euler=(0,0,0)
        bpy.context.view_layer.update()
        return socket
