"""Room construction with physical openings, plus modular café/classroom/street."""
from render_demo import cube,material
from stage_a_cafe import wood,emission
from library_props import build,palette
import bpy

def wall_sections(name,y,width,height,wall,openings=()):
    """Physical wall panels around nonoverlapping x,width,bottom,height openings."""
    cuts=[(-width/2,width/2,0,height)]
    for x,w,bottom,h in openings:
        a,b=x-w/2,x+w/2;top=bottom+h
        assert -width/2<a<b<width/2 and top<height
        nxt=[]
        for l,r,z0,z1 in cuts:
            if r<=a or l>=b or z1<=bottom or z0>=top:nxt.append((l,r,z0,z1));continue
            for rect in ((l,min(r,a),z0,z1),(max(l,b),r,z0,z1),(max(l,a),min(r,b),z0,min(z1,bottom)),(max(l,a),min(r,b),max(z0,top),z1)):
                if rect[1]-rect[0]>.001 and rect[3]-rect[2]>.001:nxt.append(rect)
        cuts=nxt
    return [cube(name+" panel "+str(i),((l+r)/2,y,(z0+z1)/2),(r-l,.16,z1-z0),wall,bevel=0) for i,(l,r,z0,z1) in enumerate(cuts)]

def room(name,width=8,depth=8,height=4,window=(1.7,1.7,1.45),door=(-2.3,1.15,2.55),front=False):
    """Back wall + two side walls, optional front. Openings: x,width,height
    (window sill fixed at 1.25; door base 0). Camera stays inside envelope."""
    p=palette();wall=material(name+" plaster",(.58,.48,.34));trim=material(name+" trim",(.12,.22,.25))
    floor=wood(name+" plank floor",(.15,.07,.025),(.39,.21,.09));y=depth/2
    cube(name+" floor",(0,0,-.10),(width,depth,.2),floor,bevel=0)
    for x in (-width/2,width/2):
        cube(name+" side wall",(x,0,height/2),(.16,depth,height),wall,bevel=0)
        cube(name+" base trim",(x*.98,0,.12),(.12,depth,.24),trim,bevel=0)
    openings=[]
    for opening,kind in ((window,"window"),(door,"door")):
        if opening is None:continue
        x,w,h=opening;bottom=1.25 if kind=="window" else 0
        openings.append((x,w,bottom,h))
        build(kind,name+" opening "+str(x),(x,y-.08,bottom),p=p,width=w,height=h,pane=False)
    wall_sections(name+" rear wall",y,width,height,wall,openings)
    if front:cube(name+" front wall",(0,-y,height/2),(width,.16,height),wall,bevel=0)
    return p

def cafe():
    p=room("Modular cafe",8,8,4.3)
    for x,y in ((-2,0),(2,0),(0,2.0)):
        build("table",pos=(x,y,0),p=p,width=1.6,depth=.9)
        for s in (-1,1):
            ob=build("chair",pos=(x,y+s*.82,0),p=p);ob.rotation_euler.z=0 if s>0 else 3.14159
        build("cup",pos=(x-.28,y,1.18),p=p);build("cake",pos=(x+.25,y,1.18),p=p)
    build("bookshelf",pos=(-3.1,3.55,0),p=p);build("plant",pos=(3.2,3.3,0),scale=1.5,p=p)
    return p

def classroom():
    p=room("Modular classroom",9,9,4.4)
    for x in (-2.2,0,2.2):
        for y in (-.5,1.5):
            build("desk",pos=(x,y,0),p=p,width=1.65);build("chair",pos=(x,y+.87,0),p=p);build("book",pos=(x,y,1.18),p=p)
    board=material("Chalkboard",(.055,.22,.14));cube("Classroom board",(0,4.34,2.55),(3.6,.1,1.35),board)
    build("bookshelf",pos=(3.4,3.9,0),p=p);return p

def street():
    """New exterior: dressed sidewalk, row houses, road, park trees."""
    p=palette();asphalt=material("Asphalt",(.105,.12,.14));walk=material("Concrete sidewalk",(.43,.44,.40))
    grass=material("Lawn",(.11,.29,.085));brick=material("Warm brick",(.42,.18,.10));roof=material("Roof slate",(.11,.16,.22))
    cube("Road",(0,-3.2,-.15),(34,5.2,.26),asphalt,bevel=0)
    cube("Sidewalk",(0,.15,-.10),(34,2.15,.20),walk,bevel=0)
    cube("Lawn",(0,4.8,-.14),(34,7.1,.26),grass,bevel=0)
    for x in range(-16,17,2):cube("Road dash",(x,-3.2,-.009),(.75,.08,.018),p["cream"],bevel=0)
    for x in range(-16,17):cube("Paving joint",(x,.15,.002),(.018,2.1,.004),asphalt,bevel=0)
    windows=[]
    for i,x in enumerate((-9,-3,3,9)):
        col=(brick,material("Blue siding",(.19,.35,.46)),material("Ochre siding",(.55,.37,.17)),brick)[i]
        # Build façade from the same opening/panel kit as rooms; windows
        # and door cover actual openings rather than decals on a solid cube.
        for ob in wall_sections("House facade",3.2,4.8,3.3,col,((-.9,1.15,0,2.35),(.88,1.1,1.45,1.0))):
            ob.location.x+=x
        cube("House rear",(x,6.2,1.65),(4.8,.16,3.3),col,bevel=0)
        for side in (-1,1):cube("House side",(x+side*2.32,4.7,1.65),(.16,3.0,3.3),col,bevel=0)
        for side in (-1,1):
            ob=cube("Sloping roof",(x+side*1.28,4.7,3.59),(2.85,3.4,.14),roof);ob.rotation_euler.y=side*.32
        build("door",pos=(x-.9,3.12,0),scale=.9,p=p)
        for dx in (.88,):
            z=1.45
            wp=emission("House window light",(.98,.72,.34),.18)
            pane=cube("Window luminous glass",(x+dx,3.10,z+.48),(1.0,.035,.96),wp,bevel=0)
            windows.append(pane);build("window",pos=(x+dx,3.06,z),scale=.68,p=p,pane=False)
        for j in range(3):build("plant",pos=(x-1.6+j*.5,2.7,0),scale=.72,p=p)
    for x in (-6,6,13):build("tree",pos=(x,2.25,0),scale=1.15,p=p)
    build("car",pos=(7,-3,0),p=p)
    for x in (-4,4):build("lamp",pos=(x,1.02,0),scale=1.6,p=p)
    return {"palette":p,"windows":windows}
