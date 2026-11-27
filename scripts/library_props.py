"""Parametric original props: roots at floor/base, units normalized to 2.28 R6 height."""
import math
import bpy
from render_demo import cube,empty,material
from stage_a_cafe import wood,cylinder,emission
from quality_cafe import sphere
from mathutils import Vector

NAMES=("table","chair","desk","bed","door","window","lamp","bookshelf","tree","plant","car","cake","food","plate","cup","book","phone","paper_plane","umbrella","ball","gift_box")
def palette():
    return {"wood":wood("Library oak",(.16,.075,.025),(.52,.28,.09)),"dark":material("Ink",(.035,.045,.06)),"cream":material("Cream",(.86,.78,.61)),"red":material("Brick red",(.62,.045,.035)),"blue":material("Ocean blue",(.035,.22,.52)),"leaf":material("Leaf",(.06,.32,.10)),"green":material("Spring leaf",(.18,.52,.13)),"metal":material("Steel",(.22,.26,.30)),"pink":material("Rose frosting",(.86,.22,.29)),"yellow":material("Gold",(.92,.55,.025)),"glass":material("Stylized glass",(.26,.58,.76)),"glow":emission("Warm lamp",(.98,.71,.32),1.4)}

def build(kind,name=None,pos=(0,0,0),scale=1,p=None,**params):
    if kind not in NAMES:raise ValueError(kind)
    p=p or palette();r=empty(name or kind,pos)
    def c(label,xyz,dims,col,bev=.018):return cube(r.name+" / "+label,xyz,dims,p[col],r,bevel=bev)
    def cy(label,xyz,radius,depth,col,top=None):return cylinder(r.name+" / "+label,xyz,radius,depth,p[col],r,top)
    def sp(label,xyz,dims,col):
        ob=sphere(r.name+" / "+label,xyz,dims,p[col]);ob.parent=r;return ob
    w=params.get("width",1.5);d=params.get("depth",.9);h=params.get("height",1.18)
    if kind in ("table","desk"):
        c("top",(0,0,h-.055),(w,d,.11),"wood")
        for x in (-w/2+.09,w/2-.09):
            for y in (-d/2+.09,d/2-.09):c("leg",(x,y,h/2-.055),(.10,.10,h-.11),"wood" if kind=="table" else "metal")
        if kind=="desk":c("drawer",(w*.23,.08,h-.25),(w*.44,d*.75,.25),"wood");c("pull",(w*.23,-d*.30,h-.24),(.17,.045,.035),"metal")
    elif kind=="chair":
        c("seat",(0,0,.62),(.70,.68,.10),"wood")
        for x in (-.28,.28):
            for y in (-.27,.27):c("leg",(x,y,.31),(.085,.085,.62),"wood")
            c("back post",(x,.28,1.02),(.09,.09,.76),"wood")
        c("back",(0,.29,1.18),(.67,.12,.34),"blue")
    elif kind=="bed":
        w=params.get("width",1.55);d=params.get("depth",2.9)
        c("frame",(0,0,.26),(w,d,.30),"wood");c("mattress",(0,0,.51),(w-.06,d-.05,.24),"cream",.065)
        c("headboard",(0,d/2-.045,.75),(w,.12,1.46),"wood")
        c("blanket",(0,-.34,.67),(w-.04,d*.66,.14),"blue",.055)
        c("pillow",(0,d*.33,.70),(w*.70,.46,.19),"cream",.085)
    elif kind=="door":
        w=params.get("width",1.25);h=params.get("height",2.6)
        c("panel",(0,0,h/2),(w,.12,h),"wood")
        for z in (h*.28,h*.72):c("inset",(0,-.074,z),(w*.79,.035,h*.34),"wood")
        sp("knob",(w*.36,-.14,h*.47),(.11,.11,.11),"yellow")
    elif kind=="window":
        w=params.get("width",1.65);h=params.get("height",1.4)
        if params.get("pane",True):c("pane",(0,0,h/2),(w,.045,h),"glass")
        for x in (-w/2,0,w/2):c("mullion",(x,-.04,h/2),(.07,.12,h+.06),"cream")
        for z in (0,h/2,h):c("rail",(0,-.04,z),(w+.10,.12,.07),"cream")
        c("sill",(0,-.065,-.055),(w+.2,.26,.08),"wood")
    elif kind=="lamp":
        cy("base",(0,0,.035),.23,.07,"dark");cy("stem",(0,0,.78),.045,1.5,"metal")
        cy("shade",(0,0,1.56),.28,.38,"cream",.15);cy("diffuser",(0,0,1.36),.25,.025,"glow")
    elif kind=="bookshelf":
        w=params.get("width",1.35);h=params.get("height",2.3)
        c("back",(0,.20,h/2),(w,.08,h),"wood")
        for x in (-w/2,w/2):c("side",(x,0,h/2),(.085,.48,h),"wood")
        for i in range(4):
            z=.08+i*(h-.16)/3;c("shelf",(0,0,z),(w,.48,.075),"wood")
            if i<3:
                for j in range(6):
                    hh=.25+.05*(j%3);c("book",( -w*.39+j*w*.15,-.025,z+.04+hh/2),(w*.13,.31,hh),("red","blue","yellow","green")[j%4])
    elif kind=="tree":
        cy("trunk",(0,0,1.1),.15,2.2,"wood")
        for x,y,z,s in ((0,0,2.5,1.6),(-.55,.1,2.12,1.1),(.54,.1,2.2,1.2),(0,-.4,2.22,1.1)):
            sp("canopy",(x,y,z),(s,s,s),"leaf" if x<0 else "green")
    elif kind=="plant":
        cy("pot",(0,0,.18),.18,.36,"red",.24)
        for i in range(7):
            a=i*2.4;ob=sp("leaf",(.19*math.cos(a),.19*math.sin(a),.46+.04*(i%3)),(.18,.10,.48),"leaf" if i%2 else "green");ob.rotation_euler.y=.7*math.cos(a);ob.rotation_euler.x=-.7*math.sin(a)
    elif kind=="car":
        c("body",(0,0,.46),(1.62,3.05,.60),"red",.10);c("cabin",(0,.12,.99),(1.39,1.65,.60),"glass",.08)
        c("roof",(0,.12,1.30),(1.45,1.65,.09),"red",.04)
        for x in (-.86,.86):
            for y in (-.96,.96):
                ob=cy("tire",(x,y,.33),.33,.19,"dark");ob.rotation_euler.y=math.pi/2
                ob=cy("hub",(x*1.08,y,.33),.15,.025,"metal");ob.rotation_euler.y=math.pi/2
        for x in (-.52,.52):
            c("headlamp",(x,-1.54,.54),(.35,.055,.19),"glow");c("tail light",(x,1.54,.54),(.28,.05,.15),"pink")
    elif kind=="cake":
        for i in range(3):cy("sponge",(0,0,.05+i*.095),.27,.09,"yellow");cy("frosting",(0,0,.10+i*.095),.28,.025,"pink")
        sp("berry",(0,0,.32),(.11,.11,.11),"red")
    elif kind=="food":
        sp("bun bottom",(0,0,.07),(.48,.43,.14),"yellow");sp("patty",(0,0,.14),(.47,.43,.08),"wood")
        sp("lettuce",(0,0,.19),(.50,.45,.06),"green");sp("bun top",(0,0,.25),(.48,.43,.17),"yellow")
    elif kind=="plate":cy("plate",(0,0,.028),.29,.055,"cream")
    elif kind=="cup":
        cy("cup",(0,0,.17),.105,.34,"cream",.135);cy("sleeve",(0,0,.16),.114,.16,"wood",.13);cy("lid",(0,0,.35),.14,.035,"blue")
    elif kind=="book":
        c("pages",(0,0,.055),(.37,.52,.10),"cream");c("front cover",(0,0,.114),(.40,.55,.025),"red");c("back cover",(0,0,.009),(.40,.55,.025),"red");c("spine",(-.19,0,.062),(.045,.55,.13),"red")
    elif kind=="phone":
        c("body",(0,0,.025),(.25,.46,.05),"dark",.035);c("screen",(0,0,.053),(.218,.409,.009),"glass",.026);c("speaker",(0,.17,.060),(.055,.012,.005),"dark")
    elif kind=="paper_plane":
        me=bpy.data.meshes.new("Folded plane");me.from_pydata([(0,-.55,.08),(-.36,.34,.04),(0,.16,0),(.36,.34,.04),(0,.34,.07)],[],[(0,1,2),(0,2,3),(1,4,2),(2,4,3)]);me.update()
        ob=bpy.data.objects.new(r.name+" / folded wings",me);bpy.context.collection.objects.link(ob);ob.parent=r;ob.data.materials.append(p["cream"]);ob.modifiers.new("Paper thickness","SOLIDIFY").thickness=.009
    elif kind=="umbrella":
        cy("shaft",(0,0,.66),.025,1.32,"metal")
        cy("canopy",(0,0,1.34),.72,.28,"blue",.04);cy("handle",(0,0,.10),.045,.20,"dark")
    elif kind=="ball":sp("ball",(0,0,.23),(.46,.46,.46),"red")
    elif kind=="gift_box":
        c("box",(0,0,.25),(.52,.52,.5),"blue");c("lid",(0,0,.51),(.56,.56,.08),"red")
        c("ribbon x",(0,0,.56),(.57,.09,.02),"yellow");c("ribbon y",(0,0,.56),(.09,.57,.02),"yellow")
        for x in (-.09,.09):sp("bow",(x,0,.62),(.19,.09,.12),"yellow")
    r.scale=(scale,)*3;bpy.context.view_layer.update()
    return r
