"""Deterministic simple geometric effects. No external simulation or textures."""
import random,math
import bpy
from mathutils import Vector
from render_demo import cube,empty
from stage_a_cafe import emission
from quality_cafe import sphere

def particles(kind,center=(0,-.4,1.8),extent=(6,3,4),count=100,seed=19):
    """Create reusable mesh instances with seeded origins. Move via update."""
    if kind not in ("rain","snow","sparkles","confetti","dust"):raise ValueError(kind)
    r=random.Random(seed);root=empty("FX "+kind,center);items=[]
    colors={"rain":(.32,.61,.92),"snow":(.88,.94,1),"sparkles":(1,.72,.16),"confetti":(.95,.12,.27),"dust":(.82,.70,.45)}
    mats=[emission(kind,colors[kind],.65)]
    if kind=="confetti":mats += [emission("confetti blue",(.15,.5,1),.6),emission("confetti yellow",(1,.75,.13),.6)]
    for i in range(count):
        pos=Vector(tuple(r.uniform(-e/2,e/2) for e in extent))
        if kind=="rain":
            ob=cube("Rain streak",pos,(.012,.012,r.uniform(.20,.42)),mats[0],root,bevel=0);ob.rotation_euler.y=.17
        elif kind=="confetti":
            ob=cube("Confetti paper",pos,(.08,.045,.009),mats[i%3],root,bevel=0);ob.rotation_euler=(r.random(),r.random(),r.random())
        else:
            size={"snow":.055,"sparkles":.055,"dust":.024}[kind]*r.uniform(.7,1.4)
            ob=sphere(kind,pos,(size,size,size),mats[0],ico=True);ob.parent=root
        items.append((ob,pos.copy()))
    return {"kind":kind,"root":root,"items":items,"extent":extent}

def update(effect,time,frame=None):
    speed={"rain":4.7,"snow":.50,"confetti":.70,"sparkles":.12,"dust":.08}[effect["kind"]]
    ez=effect["extent"][2]
    for i,(ob,base) in enumerate(effect["items"]):
        ob.location=(base.x+.08*math.sin(time*2+i),base.y,((base.z+ez/2-speed*time)%ez)-ez/2)
        if frame is not None:ob.keyframe_insert("location",frame=frame)
def shake(camera,base,time,amplitude=.025,frequency=17,frame=None):
    camera.location=Vector(base)+Vector((math.sin(time*frequency)*amplitude,0,math.sin(time*frequency*1.7)*amplitude*.6))
    if frame is not None:camera.keyframe_insert("location",frame=frame)
    return (camera.location-Vector(base)).length
