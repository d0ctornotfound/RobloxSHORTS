"""Declarative native actor/prop tracks for scene adapters.

Story data supplies all marks, objects, poses, keys, labels and timing.
No trajectory is warped to a destination; socket residuals are measured and
reported separately from mesh collision/physical-contact validation.
"""
import math
import bpy
from mathutils import Vector,Matrix,Euler
from render_demo import cube,empty,material
from library_props import build as build_library_prop
from film_walk_to_mark import construct
from r6_imported_cycles import Retarget

def aim_world(actor,index,target):
    shoulder=(actor.armature.matrix_world@actor.arms[index].matrix).translation
    direction=actor.root.matrix_world.to_3x3().inverted()@(Vector(target)-shoulder)
    actor.aim_arm(index,direction)
    bpy.context.view_layer.update()
    return (actor.grips[index].matrix_world.translation-Vector(target)).length

def keys_at(keys,u):
    if not keys:raise ValueError("empty track")
    if any(a[0]>=b[0] for a,b in zip(keys,keys[1:])):raise ValueError("non-increasing track")
    if u<=keys[0][0]:return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if u<=b:
            t=(u-a)/(b-a)
            if isinstance(x,(list,tuple)):return [i+(j-i)*t for i,j in zip(x,y)]
            return x+(y-x)*t
    return keys[-1][1]

def object_by_name(name):
    ob=bpy.data.objects.get(name)
    if ob is None:raise ValueError("missing declared prop "+name)
    return ob

def parent_keep_world(child,parent):
    m=child.matrix_world.copy();child.parent=parent;child.matrix_world=m

def create_prop(spec):
    name=spec["name"]
    if bpy.data.objects.get(name):raise ValueError("prop name already exists "+name)
    if spec["kind"]!="custom":
        root=build_library_prop(spec["kind"],name=name,pos=spec.get("position",[0,0,0]),scale=spec.get("scale",1),**spec.get("params",{}))
    else:
        root=empty(name,spec.get("position",[0,0,0]))
        mats={}
        for k,rgb in spec["materials"].items():mats[k]=material(name+" / "+k,tuple(rgb))
        nodes={"root":root}
        for part in spec.get("parts",[]):
            par=nodes[part.get("parent","root")]
            if part["type"]=="pivot":
                ob=empty(name+" / "+part["id"],part["position"],par)
            elif part["type"]=="box":
                ob=cube(name+" / "+part["id"],part["position"],part["dimensions"],mats[part["material"]],par,bevel=part.get("bevel",.005))
            elif part["type"]=="text":
                data=bpy.data.curves.new(name+" / "+part["id"],"FONT");data.body=part["text"]
                data.align_x="CENTER";data.align_y="CENTER";data.size=part["size"]
                ob=bpy.data.objects.new(name+" / "+part["id"],data);bpy.context.scene.collection.objects.link(ob)
                ob.parent=par;ob.location=part["position"];data.materials.append(mats[part["material"]])
            else:raise ValueError("unknown custom part "+part["type"])
            if "rotation_deg" in part:ob.rotation_euler=tuple(math.radians(x) for x in part["rotation_deg"])
            nodes[part["id"]]=ob
    if "rotation_deg" in spec:root.rotation_euler=tuple(math.radians(x) for x in spec["rotation_deg"])
    bpy.context.view_layer.update()
    return root

class ActionTracks:
    def __init__(self,driver,spec,task):
        self.driver=driver;self.spec=spec;self.task=task;self.walks={}
        self.frames=task["unit_end"]-task["unit_start"]
        for p in spec.get("build_props",[]):create_prop(p)
        for p in spec.get("parent_props",[]):parent_keep_world(object_by_name(p["child"]),object_by_name(p["parent"]))
        for cid,w in spec.get("walk_tracks",{}).items():
            if cid not in driver.actors:raise ValueError("missing actor in walk track "+cid)
            start=w["start"];direction=Vector(w["toward"])-Vector(start)
            first=w.get("first",0);last=w.get("last",self.frames)
            if not 0<=first<last<=self.frames or last-first<12:raise ValueError("bad walk window "+cid)
            lock,solve=construct(Retarget(driver.actors[cid]),start,direction,last-first,cycles=w.get("cycles",1))
            self.walks[cid]={"lock":lock,"solve":solve,"first":first,"last":last,"expression":w.get("expression","neutral")}
        self.initial={x["object"]:object_by_name(x["object"]).location.copy() for x in spec.get("prop_tracks",[])}
        self.follow_origins={x["object"]:object_by_name(x["object"]).matrix_world.translation.copy() for x in spec.get("follow_tracks",[])}
        self.actor_origins={x["actor"]:driver.actors[x["actor"]].root.matrix_world.translation.copy() for x in spec.get("follow_tracks",[])}
        # Walk construction evaluates the imported cycle; use its declared
        # start for the prop's initial follow anchor, not the final probe pose.
        for cid,w in spec.get("walk_tracks",{}).items():
            if cid in self.actor_origins:self.actor_origins[cid]=Vector(w["start"])
        self.socket_scales={x["object"]:object_by_name(x["object"]).matrix_world.to_scale().copy() for x in spec.get("socket_tracks",[])}
    def before_performance(self,index):
        result={}
        for cid,w in self.walks.items():
            if index<w["first"] or index>=w["last"]:continue
            lock=w["lock"];k=index-w["first"]
            row=lock.step(w["solve"]["offset_seconds"]+k/30,settle=0)
            self.driver.actors[cid].pose(w["expression"])
            result[cid]=row
        return result
    def after_performance(self,index):
        u=index/max(1,self.frames-1);out={}
        for p in self.spec.get("prop_tracks",[]):
            ob=object_by_name(p["object"])
            if "position_keys" in p:
                pos=Vector(keys_at(p["position_keys"],u))
                ob.location=pos+(self.initial[p["object"]] if p.get("relative",False) else Vector((0,0,0)))
            if "rotation_deg_keys" in p:ob.rotation_euler=tuple(math.radians(x) for x in keys_at(p["rotation_deg_keys"],u))
        for p in self.spec.get("follow_tracks",[]):
            ob=object_by_name(p["object"]);actor=self.driver.actors[p["actor"]]
            delta=actor.root.matrix_world.translation-self.actor_origins[p["actor"]]
            if p.get("grounded",True):delta.z=0
            ob.location=self.follow_origins[p["object"]]+delta
            if p.get("wheel"):
                wheel=object_by_name(p["wheel"]);wheel.rotation_euler.x=delta.length/p["wheel_radius"]
        bpy.context.view_layer.update()
        for p in self.spec.get("aim_tracks",[]):
            first,last=p.get("window",[0,1])
            if not first<=u<=last:continue
            ob=object_by_name(p["object"]);a=self.driver.actors[p["actor"]]
            local=keys_at(p["offset_keys"],u) if "offset_keys" in p else p.get("offset",[0,0,0])
            target=ob.matrix_world@Vector(local)
            residual=aim_world(a,int(p["socket"]),target)
            out[p["actor"]+" aim "+p["object"]]={"target_world":list(target),"hand_target_residual":float(residual)}
        for p in self.spec.get("socket_tracks",[]):
            first,last=p.get("window",[0,1])
            if not first<=u<=last:continue
            ob=object_by_name(p["object"]);actor=self.driver.actors[p["actor"]]
            socket=actor.grips[int(p["socket"])]
            offset=Vector(p.get("offset",[0,0,0]))
            anchor=socket.matrix_world@offset
            orient=Euler(tuple(math.radians(x) for x in p.get("rotation_deg",[0,0,0]))).to_matrix().to_4x4()
            # Preserve prop physical scale instead of inheriting rig scale.
            rotation=socket.matrix_world.to_quaternion().to_matrix().to_4x4()
            scale=Matrix.Diagonal((*self.socket_scales[p["object"]],1))
            ob.matrix_world=Matrix.Translation(anchor)@rotation@orient@scale
            bpy.context.view_layer.update()
            out[p["object"]]={"actor":p["actor"],"socket":p["socket"],"socket_anchor_error":float((ob.matrix_world.translation-anchor).length)}
        return out
    def report(self):
        return {cid:{"solve":w["solve"],"metrics":{k:v for k,v in w["lock"].report().items() if k!="records"}} for cid,w in self.walks.items() if w["lock"].records}
