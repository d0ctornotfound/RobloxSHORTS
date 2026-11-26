"""Dressed café hero set. Extends the original layout with authored detail."""
import math
import random
import bpy
from mathutils import Vector
from render_demo import cube,empty,material,point_at
from stage_a_cafe import build_cafe as base_cafe,cylinder,wood,light,emission,brick,cup


def sphere(name,loc,dims,mat,ico=False):
    if ico:bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2)
    else:bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12)
    ob=bpy.context.object;ob.name=name;ob.location=loc;ob.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=not ico
    return ob


def text(name,body,loc,size,mat):
    cu=bpy.data.curves.new(name,"FONT");cu.body=body;cu.size=size
    cu.align_x="CENTER";cu.align_y="CENTER"
    ob=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(ob)
    ob.location=loc;ob.rotation_euler=(math.pi/2,0,0);cu.materials.append(mat)
    return ob


def chair(name,x,y,angle,p):
    root=empty(name,(x,y,0));root.rotation_euler.z=angle
    cube(name+" seat",(0,0,.62),(.57,.56,.10),p["oak"],root)
    for dx in (-.22,.22):
        for dy in (-.22,.22):
            cube(name+" leg",(dx,dy,.31),(.075,.075,.62),p["wood"],root)
        cube(name+" back post",(dx,.24,1.0),(.075,.08,.75),p["wood"],root)
    cube(name+" upholstered back",(0,.245,1.08),(.52,.105,.30),p["rust"],root,bevel=.045)
    return root


def plant(name,pos,scale,p):
    x,y,z=pos
    cylinder(name+" terracotta planter",(x,y,z+.14*scale),.17*scale,.28*scale,p["rust"],top=.22*scale)
    for i in range(8):
        a=i*2.39996
        ob=sphere(name+" leaf",(x+.19*scale*math.cos(a),y+.19*scale*math.sin(a),z+(.40+.055*(i%3))*scale),
            (.17*scale,.09*scale,.43*scale),p["leaf" if i%2 else "leaf2"])
        ob.rotation_euler.y=.62*math.cos(a);ob.rotation_euler.x=-.62*math.sin(a)


def pendant(name,x,y,p):
    cylinder(name+" cord",(x,y,4.22),.016,.90,p["black"])
    cylinder(name+" shade",(x,y,3.72),.31,.26,p["teal"],top=.14)
    cylinder(name+" warm diffuser",(x,y,3.58),.26,.038,p["glow"])
    light(name+" practical pool",(x,y,3.52),(x,y,1.15),65,.55,(1,.68,.34))


def wall_brick(name,axis):
    # Use physical local mesh coordinates, so brick size is consistent on
    # separate wall pieces instead of stretched across normalized bounds.
    m=material(name,(.23,.065,.036))
    ns,ls=m.node_tree.nodes,m.node_tree.links
    co=ns.new("ShaderNodeTexCoord");sep=ns.new("ShaderNodeSeparateXYZ");comb=ns.new("ShaderNodeCombineXYZ")
    ls.new(co.outputs["Object"],sep.inputs[0]);ls.new(sep.outputs[axis],comb.inputs["X"]);ls.new(sep.outputs["Z"],comb.inputs["Y"])
    b=ns.new("ShaderNodeTexBrick")
    b.inputs["Color1"].default_value=(.17,.042,.025,1)
    b.inputs["Color2"].default_value=(.32,.086,.046,1)
    b.inputs["Mortar"].default_value=(.18,.13,.09,1)
    b.inputs["Scale"].default_value=1
    b.inputs["Brick Width"].default_value=.43;b.inputs["Row Height"].default_value=.18
    b.inputs["Mortar Size"].default_value=.013
    ls.new(comb.outputs[0],b.inputs["Vector"])
    shader=ns.get("Principled BSDF");ls.new(b.outputs["Color"],shader.inputs["Base Color"])
    bump=ns.new("ShaderNodeBump");bump.invert=True;bump.inputs["Strength"].default_value=.26;bump.inputs["Distance"].default_value=.032
    ls.new(b.outputs["Fac"],bump.inputs["Height"]);ls.new(bump.outputs[0],shader.inputs["Normal"])
    return m


def build():
    table_cup,held=base_cafe()
    p={"wood":wood("Hero walnut",(.055,.018,.006),(.31,.145,.045)),
       "oak":wood("Hero honey oak",(.20,.075,.022),(.57,.32,.10)),
       "teal":material("Petrol green enamel",(.009,.10,.085)),
       "cream":material("Cream crockery",(.83,.68,.42)),
       "black":material("Blackened brass",(.038,.032,.025)),
       "rust":material("Rust upholstery",(.42,.08,.025)),
       "leaf":material("Plant forest green",(.035,.23,.055)),
       "leaf2":material("Plant fresh green",(.095,.36,.075)),
       "red":material("Cherry",(.55,.018,.018)),
       "kraft":material("Kraft paper",(.36,.16,.055)),
       "glow":emission("Warm practical bulb",(1,.68,.30),4.0),
       "chalk":material("Chalk cream",(.87,.78,.55)),
       "board":material("Chalkboard",(.022,.045,.035)),
       "gold":material("Brass detail",(.44,.24,.055)),
       "glass":material("Case glass subtle tint",(.18,.33,.32)),
       "pastry":material("Golden pastry",(.62,.25,.045)),
       "choc":material("Chocolate pastry",(.16,.045,.014)),
       "sky":emission("Exterior sky",(.34,.64,.92),.72)}
    # Replace blank pane with a genuine opening, preserving the window frame.
    wall=bpy.data.objects.get("Rear brick wall")
    brickmat=wall_brick("Consistent terracotta running bond","X")
    sidebrick=wall_brick("Side running bond","Y")
    wall.hide_render=True
    # Window aperture x=.31..2.63, z=2.20..4.00.
    for name,loc,dims in [
        ("Brick below window",(0,2.6,1.10),(7.8,.22,2.20)),
        ("Brick above window",(0,2.6,4.75),(7.8,.22,1.50)),
        ("Brick left of window",(-1.795,2.6,3.10),(4.21,.22,1.80)),
        ("Brick right of window",(3.265,2.6,3.10),(1.27,.22,1.80))]:
        cube(name,loc,dims,brickmat,bevel=0)
    bpy.data.objects.get("Window glass").hide_render=True
    # Enclose the set on both sides and above. A taller back wall prevents
    # the portrait wide shot from being dominated by a close ceiling.
    for obj in list(bpy.data.objects):
        if obj.name.startswith(("Left brick return","Cream plaster ceiling","Ceiling timber beam")):
            obj.hide_render=True
    cube("Left enclosed café wall",(-3.88,-.40,2.75),(.20,6.0,5.5),sidebrick,bevel=0)
    cube("Right enclosed café wall",(3.88,-.40,2.75),(.20,6.0,5.5),sidebrick,bevel=0)
    cube("High café ceiling",(0,-.40,5.60),(7.8,6.0,.18),p["cream"],bevel=0)
    for x in (-3.76,3.76):
        cube("Side wall wooden wainscot",(x,-.30,.66),(.08,5.9,1.32),p["wood"])
        cube("Side wall chair rail",(x,-.30,1.34),(.12,5.9,.10),p["oak"])
    cube("High wall oak sign board",(0,2.38,4.62),(3.05,.12,.60),p["wood"])
    text("Cafe wall sign","THE CORNER CAFE",(0,2.305,4.65),.24,p["chalk"])
    for x in (-2.95,2.95):
        cube("High wall vertical beam",(x,2.40,4.65),(.15,.18,1.38),p["wood"])
    # Exterior geometry is visible only through the real window opening.
    # Background is geometry rather than a flat photograph.
    cube("Exterior sky backcloth",(0,12,5.4),(25,.12,13),p["sky"],bevel=0)
    grass=material("Exterior grass",(.065,.22,.045))
    stucco=material("Exterior warm stucco",(.61,.42,.24))
    roof=material("Exterior blue roof",(.065,.14,.20))
    outsideglass=emission("Exterior reflected glass",(.18,.37,.48),.28)
    cube("Outside green strip",(0,6,-.12),(20,7,.20),grass,bevel=0)
    for i,(x,y,w,hh) in enumerate([(-2,8,2.4,3.5),(1.5,8.5,2.7,3.2),(4.6,9,2.5,4.0)]):
        cube("Exterior building "+str(i),(x,y,hh/2),(w,1.2,hh),stucco)
        cube("Exterior roof "+str(i),(x,y,hh+.15),(w+.22,1.4,.28),roof)
        for xx in (-.31,.31):
            for z in (1.3,2.4):
                cube("Exterior house window",(x+xx*w,y-.62,z),(.43,.05,.65),outsideglass)
    cylinder("Exterior tree trunk",(2.9,4.85,1.45),.16,2.9,p["wood"])
    for x,y,z,s in [(2.9,4.8,3.5,1.8),(2.3,4.7,3.0,1.3),(3.5,4.9,3.2,1.45),(2.8,5.2,4.1,1.2)]:
        sphere("Exterior rounded tree canopy",(x,y,z),(s,s,s),p["leaf2"],True)
    # Window trim, curtains, sill plants.
    for x in (.25,2.68):
        cube("Window jamb",(x,2.34,3.10),(.11,.20,1.86),p["wood"])
    plant("Sill foliage",(.52,2.25,2.22),.65,p)
    # Counter display cabinet: visible pastry rows on a tiered open display.
    cube("Pastry display base",(-1.05,1.88,1.49),(.82,.68,.15),p["wood"])
    for x in (-1.43,-.67):
        for y in (1.57,2.19):
            cube("Display brass upright",(x,y,1.88),(.04,.04,.74),p["gold"])
    for z in (1.65,1.96,2.23):
        cube("Display shelf",(-1.05,1.88,z),(.82,.68,.045),p["wood"])
    for z in (1.72,2.03):
        for i in range(3):
            sphere("Pastry in case",(-1.31+i*.26,1.83,z),(.19,.24,.12),p["pastry" if i!=1 else "choc"])
    for i in range(4):
        cylinder("Counter stack of paper cups",(-2.65+i*.12,2.13,1.55),.065,.30,p["cream"],top=.09)
    for i in range(3):
        cylinder("Coffee jar",(-2.65+i*.29,2.24,2.75),.105,.30,p["choc"])
        cylinder("Coffee jar lid",(-2.65+i*.29,2.24,2.91),.112,.04,p["gold"])
    # Legible original menu boards and framed graphic prints.
    for x,heading,items in [(-2.75,"COFFEE",("Espresso  3","Latte  5","Mocha  5")),(-1.62,"BAKERY",("Cake  6","Croissant  4","Cookie  3"))]:
        cube("Menu walnut frame",(x,2.42,3.58),(1.01,.10,.94),p["wood"])
        cube("Menu chalkboard",(x,2.35,3.58),(.91,.045,.84),p["board"])
        text("Menu heading",heading,(x,2.319,3.84),.12,p["chalk"])
        for i,line in enumerate(items):
            text("Menu item",line,(x,2.318,3.60-i*.15),.073,p["chalk"])
    for x,z in [(-.49,3.8),(-.49,3.18),(3.3,3.0)]:
        cube("Wall art frame",(x,2.41,z),(.48,.08,.43),p["wood"])
        cube("Art paper",(x,2.35,z),(.40,.03,.35),p["cream"])
        sphere("Wall art sun",(x+.06,2.32,z+.04),(.13,.025,.13),p["rust"])
        cube("Wall art abstract stripe",(x,2.31,z-.09),(.29,.02,.07),p["teal"])
    # Additional tables behind and to the side of the hero table.
    for label,x,y in [("Window table",2.45,1.30),("Side table",-2.35,.55)]:
        cylinder(label+" top",(x,y,1.12),.49,.12,p["oak"])
        cylinder(label+" pedestal",(x,y,.56),.075,1.05,p["black"])
        cylinder(label+" foot",(x,y,.05),.27,.09,p["black"])
        for i,(dx,dy,ang) in enumerate([(-.66,.38,-.6),(.64,.39,.6)]):
            chair(label+" chair "+str(i),x+dx,y+dy,ang,p)
        cup(label+" drink",(x+.12,y-.05,1.18),p)
        plant(label+" bud vase",(x-.18,y+.09,1.18),.43,p)
    # Geometric rug under the foreground table, plus a banquette.
    rug=material("Rug red wool",(.26,.045,.021))
    rugborder=material("Rug ochre weave",(.62,.31,.075))
    cube("Woven rug",(0,-.26,.012),(2.72,2.50,.025),rug,bevel=.006)
    for x in (-1.28,1.28):
        cube("Rug border",(x,-.26,.027),(.055,2.38,.006),rugborder,bevel=0)
    for y in (-1.42,.90):
        cube("Rug border",(0,y,.027),(2.58,.055,.006),rugborder,bevel=0)
    for x in (-1.0,-.5,0,.5,1.0):
        for y in (-1.18,.69):
            o=cube("Rug diamond",(x,y,.031),(.12,.12,.006),rugborder,bevel=0);o.rotation_euler.z=math.pi/4
    cube("Window banquette seat",(2.81,2.05,.48),(1.62,.64,.24),p["rust"],bevel=.065)
    cube("Window banquette back",(2.81,2.38,.89),(1.62,.20,.64),p["rust"],bevel=.065)
    plant("Floor plant left",(-3.28,1.52,0),1.5,p)
    plant("Floor plant right",(3.35,.25,0),1.65,p)
    pendant("Window pendant",2.45,1.30,p);pendant("Side pendant",-2.35,.55,p)
    # Drop old even fill; directional warm key and controlled cool window rim.
    for name in ("Window / warm soft key","Soft fill","Rim through window","Pendant pool"):
        ob=bpy.data.objects.get(name)
        if ob:ob.hide_render=True
    light("Hero warm key",(-2.6,-3.1,3.95),(-.3,.0,1.8),540,2.5,(1,.86,.71))
    light("Gentle bounce fill",(2.8,-3.5,2.85),(0,0,1.65),92,3.4,(.83,.91,1))
    light("Window daylight rim",(1.55,2.05,3.65),(0,-.4,1.55),480,1.9,(.76,.87,1))
    light("Hero pendant contact pool",(.04,-.03,3.48),(.04,-.03,1),75,.46,(1,.65,.30))
    light("Counter warm accent",(-2.0,.9,3.60),(-1.8,2,1.8),85,1.0,(1,.69,.40))
    return table_cup,held
