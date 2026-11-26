"""Procedural café set, original furniture and drink props."""
import math
import bpy
from render_demo import cube, empty, material, point_at


def brick(name, colors, axis, scale, width, height):
    mat=material(name,colors[0])
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    shader=nodes.get("Principled BSDF")
    coord=nodes.new("ShaderNodeTexCoord")
    sep=nodes.new("ShaderNodeSeparateXYZ")
    combine=nodes.new("ShaderNodeCombineXYZ")
    links.new(coord.outputs["Generated"],sep.inputs[0])
    links.new(sep.outputs["X"],combine.inputs["X"])
    links.new(sep.outputs[axis],combine.inputs["Y"])
    tex=nodes.new("ShaderNodeTexBrick")
    tex.inputs["Color1"].default_value=(*colors[0],1)
    tex.inputs["Color2"].default_value=(*colors[1],1)
    tex.inputs["Mortar"].default_value=(*colors[2],1)
    tex.inputs["Scale"].default_value=scale
    tex.inputs["Brick Width"].default_value=width
    tex.inputs["Row Height"].default_value=height
    tex.inputs["Mortar Size"].default_value=.025
    links.new(combine.outputs[0],tex.inputs["Vector"])
    links.new(tex.outputs["Color"],shader.inputs["Base Color"])
    bump=nodes.new("ShaderNodeBump")
    bump.invert=True
    bump.inputs["Strength"].default_value=.30
    bump.inputs["Distance"].default_value=.055
    links.new(tex.outputs["Fac"],bump.inputs["Height"])
    links.new(bump.outputs[0],shader.inputs["Normal"])
    return mat


def wood(name, low, high):
    mat=material(name,low)
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    coord=nodes.new("ShaderNodeTexCoord")
    scale=nodes.new("ShaderNodeVectorMath")
    scale.operation="MULTIPLY"
    scale.inputs[1].default_value=(2,38,15)
    links.new(coord.outputs["Generated"],scale.inputs[0])
    noise=nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=4
    noise.inputs["Detail"].default_value=3
    links.new(scale.outputs[0],noise.inputs["Vector"])
    ramp=nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color=(*low,1)
    ramp.color_ramp.elements[1].color=(*high,1)
    links.new(noise.outputs["Fac"],ramp.inputs[0])
    links.new(ramp.outputs[0],nodes.get("Principled BSDF").inputs["Base Color"])
    return mat


def cylinder(name, loc, radius, depth, mat, parent=None, top=None):
    if top is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=radius,depth=depth)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=radius,radius2=top,depth=depth)
    obj=bpy.context.object
    obj.name=name
    obj.parent=parent
    obj.location=loc
    obj.data.materials.append(mat)
    bevel=obj.modifiers.new("Soft rim","BEVEL")
    bevel.width=.008
    bevel.segments=2
    obj.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
    return obj


def emission(name, color, strength):
    mat=material(name,color)
    s=mat.node_tree.nodes.get("Principled BSDF")
    s.inputs["Emission Color" if "Emission Color" in s.inputs else "Emission"].default_value=(*color,1)
    s.inputs["Emission Strength"].default_value=strength
    return mat


def light(name, loc, target, power, size, color):
    bpy.ops.object.light_add(type="AREA",location=loc)
    obj=bpy.context.object
    obj.name=name
    obj.data.energy=power
    obj.data.shape="DISK"
    obj.data.size=size
    obj.data.color=color
    point_at(obj,target)
    return obj


def cup(name, pos, p):
    root=empty(name,pos)
    cylinder(name+" paper cup",(0,0,.15),.105,.30,p["cream"],root,top=.145)
    cylinder(name+" kraft sleeve",(0,0,.145),.126,.14,p["kraft"],root,top=.138)
    cylinder(name+" teal lid",(0,0,.31),.151,.038,p["teal"],root)
    straw=cylinder(name+" straw",(.045,0,.42),.014,.24,p["red"],root)
    straw.rotation_euler.y=-.12
    return root


def set_visible(root, visible):
    for obj in root.children_recursive:
        obj.hide_render=not visible


def build_cafe():
    p={
        "brick":brick("Terracotta running bond",((.37,.115,.065),(.60,.25,.13),(.56,.45,.32)),"Z",9,.62,.27),
        "floor":brick("Sandstone checker tile",((.24,.23,.19),(.55,.49,.37),(.12,.11,.095)),"Y",6,.55,.55),
        "wood":wood("Walnut grain",(.095,.033,.014),(.39,.20,.075)),
        "oak":wood("Honey oak grain",(.32,.14,.045),(.68,.43,.20)),
        "teal":material("Deep teal painted wood",(.025,.18,.17)),
        "cream":material("Ivory ceramic",(.84,.75,.57)),
        "black":material("Dark steel",(.045,.052,.049)),
        "kraft":material("Kraft sleeve",(.37,.18,.075)),
        "red":material("Coral straw",(.69,.08,.035)),
        "sky":emission("Window blue glass",(.20,.46,.58),.5),
        "lamp":emission("Warm lamp diffuser",(1,.67,.30),3),
        "green":material("Plant leaves",(.085,.29,.11)),
    }
    cube("Tiled floor",(0,-.7,-.10),(7.8,8.0,.20),p["floor"],bevel=0)
    cube("Rear brick wall",(0,2.6,2.35),(7.8,.22,4.7),p["brick"],bevel=0)
    cube("Left brick return",(-3.88,.55,2.35),(.18,4.1,4.7),p["brick"],bevel=0)
    cube("Wall baseboard",(0,2.44,.13),(7.8,.12,.24),p["teal"])
    # Framed window inset, stylized glass with exterior silhouette.
    cube("Window glass",(1.47,2.455,3.10),(2.25,.045,1.70),p["sky"])
    for x in (.31,1.47,2.63):
        cube("Window vertical mullion",(x,2.40,3.10),(.085,.12,1.84),p["oak"])
    for z in (2.20,3.10,4.00):
        cube("Window horizontal mullion",(1.47,2.40,z),(2.40,.12,.085),p["oak"])
    cube("Window sill",(1.47,2.32,2.16),(2.53,.37,.12),p["oak"])
    # Counter with paneled front, backsplash shelf, jars and coffee machine.
    cube("Counter carcass",(-1.84,1.94,.66),(2.35,.96,1.32),p["teal"])
    cube("Counter top",(-1.84,1.94,1.36),(2.52,1.08,.14),p["oak"])
    for x in (-2.76,-2.30,-1.84,-1.38,-.92):
        cube("Counter raised panel",(x,1.44,.68),(.39,.09,1.12),p["wood"])
    cube("Espresso machine",(-2.15,1.95,1.69),(.77,.51,.55),p["black"])
    cube("Espresso face",(-2.15,1.68,1.70),(.70,.07,.40),p["cream"])
    for x in (-2.36,-2.04):
        cylinder("Espresso dial",(x,1.62,1.81),.055,.07,p["black"]).rotation_euler.x=math.pi/2
    cube("Shelf",(-1.9,2.32,2.55),(2.45,.34,.10),p["oak"])
    for i in range(4):
        cylinder("Coffee tin",(-2.68+i*.46,2.28,2.75),.13,.30,p["cream"] if i%2 else p["teal"])
        cylinder("Tin lid",(-2.68+i*.46,2.28,2.91),.14,.04,p["wood"])
    # Round table, two slatted wooden chairs.
    cylinder("Cafe table top",(.04,-.03,1.12),.65,.12,p["oak"])
    cylinder("Table pedestal",(.04,-.03,.56),.085,1.05,p["black"])
    cylinder("Table foot",(.04,-.03,.055),.35,.09,p["black"])
    for i,(x,y,angle) in enumerate([(-.91,.89,-.42),(1.00,.89,.42)]):
        root=empty("Chair "+str(i+1),(x,y,0))
        root.rotation_euler.z=angle
        cube("Chair seat",(0,0,.62),(.58,.58,.10),p["oak"],root)
        for dx in (-.23,.23):
            for dy in (-.23,.23):
                cube("Chair leg",(dx,dy,.31),(.075,.075,.62),p["wood"],root)
            cube("Chair back upright",(dx,.245,1.0),(.075,.08,.75),p["wood"],root)
        for z in (.94,1.17):
            cube("Chair back slat",(0,.245,z),(.53,.08,.12),p["oak"],root)
    # Pendant light, cord and shade. Small potted plant near window.
    cylinder("Pendant cable",(.04,-.03,4.18),.018,.94,p["black"])
    cylinder("Pendant shade",(.04,-.03,3.65),.33,.27,p["teal"],top=.15)
    cylinder("Pendant luminous underside",(.04,-.03,3.51),.26,.035,p["lamp"])
    cylinder("Plant pot",(2.25,2.25,2.34),.11,.25,p["cream"],top=.16)
    for i in range(5):
        leaf=cube("Plant leaf",(2.25+.10*math.cos(i*1.26),2.25+.10*math.sin(i*1.26),2.56),(.11,.07,.28),p["green"],bevel=.035)
        leaf.rotation_euler.y=.55*math.cos(i*1.26)
        leaf.rotation_euler.x=.55*math.sin(i*1.26)
    table_cup=cup("Table drink",(.22,-.12,1.18),p)
    held=cup("Held drink",(0,0,0),p)
    light("Window / warm soft key",(1.9,-3.5,5.1),(0,0,1.7),850,4,(1,.82,.62))
    light("Soft fill",(-3.0,-3.5,3.6),(0,0,1.8),400,3.8,(.72,.83,1))
    light("Rim through window",(2.4,1.7,4.1),(0,-.5,1.8),450,2.5,(1,.72,.43))
    light("Pendant pool",(.04,-.03,3.48),(.04,-.03,1),85,.5,(1,.64,.34))
    return table_cup,held
