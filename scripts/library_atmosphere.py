"""Art-directed atmosphere presets (not astronomical simulation).
Sun elevation/azimuth degrees, RGB linear, sun strength, world strength, exposure."""
import math,random
import bpy
from mathutils import Vector
from render_demo import point_at
from stage_a_cafe import light,emission
from quality_cafe import sphere
PRESETS={
"morning":(25,-45,(1,.78,.53),2.0,(.46,.67,.91),.42,0),
"midday":(62,-35,(1,.95,.82),2.8,(.38,.65,.94),.48,0),
"golden_hour":(12,-60,(1,.49,.20),2.5,(.83,.42,.23),.34,.10),
"dusk":(4,-70,(.75,.40,.40),.55,(.21,.26,.48),.28,.10),
"night":(32,40,(.34,.49,1),.38,(.035,.075,.22),.25,.25),
"overcast":(55,-35,(.82,.90,1),.35,(.46,.53,.62),.65,0),
"rain":(38,-35,(.67,.78,1),.22,(.25,.34,.49),.45,.05)}
class Atmosphere:
    def __init__(self,scene,windows=(),target=(0,0,1.2)):
        self.scene=scene;self.windows=windows
        bpy.ops.object.light_add(type="SUN");self.sun=bpy.context.object;self.sun.name="Library sun/moon";self.sun.data.angle=.18
        self.fill=light("Library motivated front fill",(0,-5,5),target,210,5,(.78,.85,1))
        self.moon=sphere("Moon disc",(5,22,10),(.80,.18,.80),emission("Moon disc glow",(.85,.91,1),2.5))
        rng=random.Random(43);self.stars=[]
        mat=emission("Stars",(.72,.84,1),2)
        for i in range(38):
            x=rng.uniform(-19,19);z=rng.uniform(7.0,15)
            self.stars.append(sphere("Star",(x,23,z),(.045,.025,.045),mat,ico=True))
    def apply(self,name,other=None,mix=0,frame=None):
        a=PRESETS[name];b=PRESETS[other or name];u=min(1,max(0,mix))
        def blend(x,y):return tuple(blend(i,j) for i,j in zip(x,y)) if isinstance(x,tuple) else x+(y-x)*u
        elev,az,col,energy,sky,world,expo=[blend(x,y) for x,y in zip(a,b)]
        e,z=math.radians(elev),math.radians(az);direction=Vector((math.cos(e)*math.sin(z),-math.cos(e)*math.cos(z),math.sin(e)))
        self.sun.rotation_euler=(-direction).to_track_quat("-Z","Y").to_euler();self.sun.data.color=col;self.sun.data.energy=energy
        bg=self.scene.world.node_tree.nodes.get("Background");bg.inputs[0].default_value=(*sky,1);bg.inputs[1].default_value=world
        self.scene.view_settings.exposure=expo
        night=(1-u if name=="night" else 0)+(u if other=="night" else 0)
        self.fill.data.energy=180+130*night;self.fill.data.color=blend((1,.92,.81),(.48,.62,1)) if other=="night" else ((.48,.62,1) if name=="night" else (1,.92,.81))
        for ob in [self.moon]+self.stars:ob.hide_render=night<.48
        for ob in self.windows:
            bs=ob.data.materials[0].node_tree.nodes.get("Principled BSDF");bs.inputs["Emission Strength"].default_value=.12+2.2*night
        if frame is not None:
            self.sun.keyframe_insert("rotation_euler",frame=frame)
            for prop in ("color","energy"):self.sun.data.keyframe_insert(prop,frame=frame);self.fill.data.keyframe_insert(prop,frame=frame)
            for i in (0,1):bg.inputs[i].keyframe_insert("default_value",frame=frame)
            self.scene.view_settings.keyframe_insert("exposure",frame=frame)
            for ob in [self.moon]+self.stars:ob.keyframe_insert("hide_render",frame=frame)
            for ob in self.windows:ob.data.materials[0].node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].keyframe_insert("default_value",frame=frame)
        return {"preset":name,"other":other,"mix":u,"sun_energy":energy,"sky":sky,"night":night}
