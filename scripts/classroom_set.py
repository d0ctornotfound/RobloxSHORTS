"""Original classroom set and teacher variant; locked quality rig."""
import math
import bpy
from render_demo import cube,empty,material
from quality_character import Character
from quality_textures import Canvas,illustrated_material
from quality_cafe import sphere,text,chair
from stage_a_cafe import wood,light,emission

def teacher_palette(p):
    for key,base in (("teacher_shirt","tee"),("teacher_sleeve","tee_sleeve"),("teacher_pants","denim")):
        m=illustrated_material(base)
        c=Canvas(1024,(135,68,105,255) if key!="teacher_pants" else (86,100,117,255))
        for y in range(0,100,4):
            c.rect(0,y/100,1,y/100+.005,(155,87,122,255) if key!="teacher_pants" else (101,115,131,255))
        c.rect(0,0,1,.055,(78,40,68,255))
        if key=="teacher_shirt":
            c.polygon([(.30,1),(.5,.76),(.7,1)],(248,226,194,255))
            c.line([(.50,.77),(.50,.06)],.018,(78,40,68,255))
            for y in (.18,.34,.50,.66):c.ellipse(.5,y,.022,.022,(241,200,137,255))
        next(n for n in m.node_tree.nodes if n.type=="TEX_IMAGE").image=c.image(key)
        p[key]=m
    return p

class Teacher(Character):
    def __init__(self,p):
        super().__init__("teacher",p,False,role="teacher",wardrobe=("teacher_shirt","teacher_sleeve","teacher_pants"))
        for ob in list(self.meshes):
            if "spiky hair" in ob.name:
                self.meshes.remove(ob);bpy.data.objects.remove(ob,do_unlink=True)
        def hair(label,loc,dims):
            ob=sphere("teacher / hair "+label,loc,dims,p["hair2"])
            ob.parent=self.root;self.meshes.append(ob);return ob
        hair("scalp",(0,.035,2.23),(1.12,.87,.36))
        hair("nape",(0,.30,2.07),(.91,.34,.49))
        self.bun=hair("bun",(0,.27,2.56),(.59,.60,.57))
        rim=material("Teacher burgundy glasses",(.21,.045,.07))
        for x in (-.105,.105):
            for z in (1.949,2.057):
                self.meshes.append(cube("teacher / head glasses",(x,-.408,z),(.19,.025,.018),rim,self.root,.007))
            for dx in (-.09,.09):
                self.meshes.append(cube("teacher / head glasses",(x+dx,-.408,2.003),(.018,.025,.12),rim,self.root,.006))
        self.meshes.append(cube("teacher / head glasses bridge",(0,-.41,2.01),(.045,.025,.018),rim,self.root,.006))

def build():
    p={"oak":wood("Classroom honey oak",(.29,.14,.05),(.62,.39,.17)),
       "wood":wood("Classroom walnut",(.20,.09,.035),(.43,.24,.11)),
       "rust":material("Chair terracotta",(.48,.15,.07)),
       "wall":material("Warm ivory plaster",(.76,.66,.48)),
       "trim":material("Sage wainscot",(.28,.45,.36)),
       "floor":wood("Maple floor",(.35,.24,.13),(.65,.49,.30)),
       "steel":material("Desk blue steel",(.12,.25,.32)),
       "board":material("Green chalkboard",(.085,.20,.14)),
       "chalk":material("Chalk",(.92,.91,.77)),
       "sky":emission("Daylight window",(.53,.76,.95),1.0),
       "paper":material("Ivory paper",(.94,.91,.79))}
    cube("Floor",(0,0,-.1),(11,15,.2),p["floor"],bevel=0)
    cube("Front classroom wall",(0,-7.4,3.2),(11,.2,6.4),p["wall"],bevel=0)
    cube("Back classroom wall",(0,7.4,3.2),(11,.2,6.4),p["wall"],bevel=0)
    for x in (-5.4,5.4):
        cube("Side wall",(x,0,3.2),(.2,15,6.4),p["wall"],bevel=0)
        cube("Side wainscot",(x*.98,0,.55),(.12,15,1.1),p["trim"],bevel=0)
    cube("Ceiling",(0,0,6.4),(11,15,.15),p["wall"],bevel=0)
    cube("Board frame",(0,-7.22,2.65),(6.6,.18,2.45),p["wood"])
    cube("Chalkboard",(0,-7.10,2.65),(6.35,.075,2.2),p["board"])
    # text faces +Y, toward the class.
    for body,x,z,size in [("MATHEMATICS",0,3.44,.28),("2x + 5 = 17",-1.4,2.78,.36),("x = 6",-1.4,2.24,.36),("a² + b² = c²",1.3,2.78,.32)]:
        ob=text("Board chalk",body,(x,-7.045,z),size,p["chalk"]);ob.rotation_euler.z=math.pi
    cube("Chalk tray",(0,-6.99,1.43),(6.4,.22,.12),p["wood"])
    for y in (-4.4,-.4,3.6):
        cube("Window light",(-5.27,y,3.25),(.035,2.6,2.5),p["sky"])
        for yy in (y-1.31,y,y+1.31):cube("Window mullion",(-5.23,yy,3.25),(.10,.075,2.65),p["wood"])
        for z in (2,3.25,4.5):cube("Window rail",(-5.23,y,z),(.10,2.7,.075),p["wood"])
    def desk(name,x,y,w=1.65,d=.85,h=1.15):
        cube(name+" top",(x,y,h),(w,d,.11),p["oak"])
        for dx in (-w*.41,w*.41):
            for dy in (-d*.37,d*.37):
                cube(name+" leg",(x+dx,y+dy,h/2),(.085,.085,h),p["steel"])
        cube(name+" apron",(x,y-d*.4,h-.19),(w*.87,.09,.23),p["wood"])
    for y in (1.0,3.2,5.4):
        for x in (-3.2,-1.05,1.05,3.2):
            desk("Student desk",x,y)
            chair("Student chair",x,y+.79,0,p)
            cube("Exercise book",(x+.46,y,1.22),(.35,.45,.04),p["paper"])
    desk("Teacher desk",3.35,-5.65,2.6,1.0,1.35)
    for x in (-3.5,0,3.5):
        for y in (-5,0,5):
            light("Soft classroom overhead",(x,y,5.9),(x,y,1),370,3,(1,.94,.84))
    light("Window daylight",(-4.9,-.5,3.9),(1,0,1.5),900,4,(.81,.91,1))
    return p
