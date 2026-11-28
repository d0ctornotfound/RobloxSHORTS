"""Opt-in native world diagram scene. All formations, identities, links,
marks and timings come from the caller's story data, never this module."""
import importlib, math
import bpy
from mathutils import Vector
from r6_character import mesh_points
from library_camera import project
from film_world_diagram import build, evaluate
from character_motion_correction import apply_corrected
from facial_expressions import enable_blinking

def resolve(path):
    module,name=path.split(":")
    return getattr(importlib.import_module(module),name)

def light(name,location,target,energy,color,size):
    data=bpy.data.lights.new(name,"AREA")
    data.energy=energy;data.color=color;data.shape="DISK";data.size=size
    ob=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(ob)
    ob.location=location;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat("-Z","Y").to_euler()
    return ob

def lerp_keys(keys,u):
    if u<=keys[0][0]:return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if u<=b:return x+(y-x)*(u-a)/(b-a)
    return keys[-1][1]

class DiagramDriver:
    """Actual actor factory plus declared ground graphics and overhead camera.
    No paper, portrait stand-ins, or screen-space labels."""
    def __init__(self,scene,cam,cast,spec,conf,task):
        self.scene=scene;self.cam=cam;self.spec=spec["diagram"];self.actors={}
        self.cast=cast;self.factory=resolve(conf["actor_factory"])
        self.unit_frames=task["unit_end"]-task["unit_start"]
        self.reveal=self.spec.get("progress_keys",[[0,0],[1,1]])
        assert self.unit_frames>0 and len(self.reveal)>=2
        assert all(0<=t<=1 and 0<=v<=1 for t,v in self.reveal)
        assert all(a[0]<b[0] for a,b in zip(self.reveal,self.reveal[1:]))
        floor=self.spec["ground"]
        bpy.ops.mesh.primitive_plane_add(size=1,location=floor.get("center",[0,0,-.025]))
        ground=bpy.context.object;ground.name="World diagram ground";ground.scale=(*floor["size"],1)
        m=bpy.data.materials.new("Diagram ground material");m.use_nodes=True
        rgb=floor.get("color",[.55,.49,.39])
        m.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value=(*rgb,1)
        m.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value=.88
        ground.data.materials.append(m)
        scene.world.use_nodes=True
        bg=scene.world.node_tree.nodes.get("Background")
        bg.inputs[0].default_value=(.55,.61,.68,1);bg.inputs[1].default_value=.48
        light("Diagram daylight",(-4,-5,12),(0,0,0),2400,(1,.88,.72),10)
        light("Diagram bounce",(5,4,8),(0,0,0),900,(.82,.89,1),8)
        self.diagram=build(self.spec,self.place)
        camera=self.spec["camera"];cam.location=camera["position"]
        cam.rotation_euler=(Vector(camera["target"])-cam.location).to_track_quat("-Z","Y").to_euler()
        cam.data.type="ORTHO";cam.data.ortho_scale=camera["ortho_scale"];scene.camera=cam
        bpy.context.view_layer.update()
        if camera.get("fit_all",True):
            # Fit once using evaluated actual cast and ground graphics, not
            # assumed portrait/landscape ortho-scale semantics.
            pts=[p for a in self.actors.values() for o in a.root.children_recursive if o.type=="MESH" and not o.hide_render for p in mesh_points(o)]
            for ob in self.diagram["root"].children_recursive:
                if ob.type in ("CURVE","FONT","MESH"):
                    pts.extend(ob.matrix_world@Vector(v) for v in ob.bound_box)
            if not pts:raise ValueError("empty diagram framing")
            b=project(scene,cam,pts)
            ratio=max(abs(v-.5) for v in b[:4])/camera.get("fit_half_extent",.45)
            cam.data.ortho_scale*=max(.1,ratio)
            bpy.context.view_layer.update()
            self.diagram_bounds=list(project(scene,cam,pts))
        else:self.diagram_bounds=None
    def place(self,cid,xyz,yaw):
        if cid in self.actors:raise ValueError("duplicate actual cast actor "+cid)
        actor=self.factory(cid,self.cast["actors"][cid]);self.actors[cid]=actor
        apply_corrected(actor,"idle",.5,.5,xyz,math.radians(yaw))
        actor.pose("neutral")
        enable_blinking(self.scene,actor,seed=sum(ord(ch) for ch in cid))
    def update(self,n,u,t,index,after_name=True):
        phase=index/max(1,self.unit_frames-1)
        report=evaluate(self.diagram,lerp_keys(self.reveal,phase))
        report["actual_cast_ids"]=list(self.actors)
        report["phase"]=phase
        report["framing_bounds"]=self.diagram_bounds
        report["expected_actor_count"]=sum(len(g["actors"]) for g in self.spec["formations"])
        report["expected_link_count"]=len(self.spec["links"])
        report["expected_reveal"]=lerp_keys(self.reveal,phase)
        return {"world_diagram":report}
