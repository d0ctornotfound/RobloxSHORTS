"""Story-local original square built from the approved primitive set kit.
Candidate scene, not an approved render; external Itlay model not imported.
"""
from render_demo import cube,empty,material
from stage_a_cafe import cylinder
from library_props import build,palette
from mathutils import Vector
import math

def build_square(stage):
    root=empty("Saying Hi persistent square",(0,0,0));p=palette()
    stone=material("plaza pale limestone",(.58,.48,.34));trim=material("warm trim",(.75,.62,.43))
    water=material("well blue water",(.06,.30,.38));brick=material("terracotta",(.42,.15,.09))
    wood=material("seat timber",(.30,.15,.065))
    cube("plaza paving",(0,1,-.12),(22,24,.24),stone,root,bevel=0)
    for x in range(-10,11):
        for y in range(-10,13):
            if (x+y)%2==0:
                cube("paving tile",(x,y,.004),(.97,.97,.008),trim,root,bevel=.003)
    # Well built as a ring of separate stone blocks; interior remains visible.
    for layer in range(3):
        for i in range(18):
            t=2*math.pi*(i+.5*(layer%2))/18
            ob=cube("well stone",(1.20*math.cos(t),1.20*math.sin(t),.20+layer*.36),(.41,.42,.35),stone,root,bevel=.025)
            ob.rotation_euler.z=t
    cylinder("water surface",(0,0,.54),1.02,.025,water,root)
    for x in (-1.35,1.35):
        cube("well roof post",(x,0,1.65),(.15,.15,2.7),wood,root,bevel=.01)
    for s in (-1,1):
        ob=cube("well roof",(0,s*.57,3.12),(3.12,1.42,.12),brick,root,bevel=.02);ob.rotation_euler.x=s*.32
    # Wall and individual seats follow stable stage marks.
    h=stage["marks"]["wall_narrator"]["seat_height"]
    cube("tally wall",(0,8.27,h/2),(8.5,.66,h),stone,root,bevel=.02)
    cube("wall cap",(0,8.27,h-.035),(8.65,.72,.07),trim,root,bevel=.01)
    for cid in stage["layouts"]["initial"]["well"]:
        m=stage["marks"]["well_"+cid];x,y,_=m["xyz"];h=m["seat_height"]
        ob=cube("seat "+cid,(x,y,h-.055),(.70,.58,.11),wood,root,bevel=.02);ob.rotation_euler.z=math.radians(m["yaw_deg"])
        cube("pedestal "+cid,(x,y,(h-.11)/2),(.40,.37,h-.11),stone,root,bevel=.01)
    # Scene-local candidate architectural dressing from the same primitive kit.
    for side in (-1,1):
        for j,y in enumerate((-7,-2,3,8)):
            x=side*9.6
            cube("plaza facade",(x,y,2.4),(1.2,4.7,4.8),brick if j%2 else trim,root,bevel=.03)
            cube("facade cornice",(x,y,4.7),(1.6,4.85,.20),stone,root,bevel=.02)
            for off in (-1.25,1.25):
                cube("window inset",(x-side*.61,y+off,3.0),(.09,.92,1.10),wood,root,bevel=.01)
            build("tree",pos=(side*7.6,y+1.2,0),scale=1.1,p=p)
    return root
