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
"dusk":(4,-70,(1,.52,.30),.85,(.28,.34,.55),.45,.18),
"night":(32,40,(.34,.49,1),.38,(.035,.075,.22),.25,.25),
"overcast":(55,-35,(.82,.90,1),.35,(.46,.53,.62),.65,0),
"rain":(38,-35,(.67,.78,1),.22,(.25,.34,.49),.45,.05)}
class Atmosphere:
    def __init__(self,scene,windows=(),target=(0,0,1.2),lamps=()):
        self.scene=scene;self.windows=windows;self.lamps=lamps
        # Separate camera sky from diffuse illumination, preserving other presets.
        nt=scene.world.node_tree;n=nt.nodes;l=nt.links
        bg=n.get("Background");out=next(o for o in n if o.type=="OUTPUT_WORLD")
        ray=n.new("ShaderNodeLightPath");coord=n.new("ShaderNodeTexCoord")
        sep=n.new("ShaderNodeSeparateXYZ");l.new(coord.outputs["Normal"],sep.inputs[0])
        ab=n.new("ShaderNodeMath");ab.operation="ABSOLUTE";l.new(sep.outputs["Z"],ab.inputs[0])
        ramp=n.new("ShaderNodeValToRGB");l.new(ab.outputs[0],ramp.inputs[0])
        cr=ramp.color_ramp;cr.interpolation="EASE"
        cr.elements[0].position=.04;cr.elements[0].color=(1,.28,.075,1)
        cr.elements[1].position=.38;cr.elements[1].color=(.025,.065,.22,1)
        cr.elements.new(.17).color=(.48,.17,.22,1)
        self.sky_mix=n.new("ShaderNodeMixRGB");self.sky_mix.blend_type="MIX"
        l.new(ramp.outputs["Color"],self.sky_mix.inputs[2])
        self.camera_bg=n.new("ShaderNodeBackground");l.new(self.sky_mix.outputs[0],self.camera_bg.inputs[0])
        mixshader=n.new("ShaderNodeMixShader");l.new(ray.outputs["Is Camera Ray"],mixshader.inputs[0]);l.new(bg.outputs[0],mixshader.inputs[1]);l.new(self.camera_bg.outputs[0],mixshader.inputs[2]);l.new(mixshader.outputs[0],out.inputs["Surface"])
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
        dusk=(1-u if name=="dusk" else 0)+(u if other=="dusk" else 0)
        self.sky_mix.inputs[0].default_value=dusk;self.sky_mix.inputs[1].default_value=(*sky,1)
        self.camera_bg.inputs[1].default_value=world+(1-world)*dusk
        lamp_weight=min(1,dusk+night)
        for lamp,mat in self.lamps:
            lamp.data.energy=85*lamp_weight
            mat.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value=.05+3.5*lamp_weight
        self.fill.data.energy=180+130*night+85*dusk;self.fill.data.color=blend((1,.92,.81),(.48,.62,1)) if other=="night" else ((.48,.62,1) if name=="night" else (1,.92,.81))
        for ob in [self.moon]+self.stars:ob.hide_render=night<.48
        for ob in self.windows:
            bs=ob.data.materials[0].node_tree.nodes.get("Principled BSDF");bs.inputs["Emission Strength"].default_value=.12+2.2*night+.65*dusk
        if frame is not None:
            self.sun.keyframe_insert("rotation_euler",frame=frame)
            for prop in ("color","energy"):self.sun.data.keyframe_insert(prop,frame=frame);self.fill.data.keyframe_insert(prop,frame=frame)
            for i in (0,1):bg.inputs[i].keyframe_insert("default_value",frame=frame)
            self.scene.view_settings.keyframe_insert("exposure",frame=frame)
            for i in (0,1):self.sky_mix.inputs[i].keyframe_insert("default_value",frame=frame)
            self.camera_bg.inputs[1].keyframe_insert("default_value",frame=frame)
            for lamp,mat in self.lamps:
                lamp.data.keyframe_insert("energy",frame=frame)
                mat.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].keyframe_insert("default_value",frame=frame)
            for ob in [self.moon]+self.stars:ob.keyframe_insert("hide_render",frame=frame)
            for ob in self.windows:ob.data.materials[0].node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].keyframe_insert("default_value",frame=frame)
        return {"preset":name,"other":other,"mix":u,"sun_energy":energy,"sky":sky,"night":night,"dusk":dusk,"lamp_energy":85*lamp_weight,"camera_gradient_weight":dusk}
