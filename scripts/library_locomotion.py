"""Contact-corrected playback layer over immutable imported R6 source keys.
Sequential samples in actor-local axes, actual evaluated sole geometry.
No claim of two-foot IK: a rigid R6 has one dominant support foot at a time."""
import math,statistics
import bpy
from mathutils import Vector,Matrix,Euler
from r6_character import mesh_points,dominant_group

class StrideLock:
    def __init__(self,retarget,name="walk_cycle",fps=30,rate=1.0,start=(0,0,0),yaw=0):
        self.ret=retarget;self.actor=retarget.actor;self.name=name;self.fps=fps;self.rate=rate
        self.start=Vector(start);self.yaw=yaw;self.rot=Matrix.Rotation(yaw,3,"Z")
        self.actor.reset();self.actor.root.location=(0,0,0);self.actor.root.rotation_euler=(0,0,0)
        bpy.context.view_layer.update();pts=mesh_points(self.actor.body);self.soles=[]
        for bone in self.actor.legs:
            ids=[v.index for v in self.actor.body.data.vertices if dominant_group(self.actor.body,v)==bone.name]
            low=min(pts[i].z for i in ids)
            self.soles.append([i for i in ids if pts[i].z<=low+.025])
        self.pos=self.start.copy();self.prev=None;self.last=None;self.support=None;self.records=[]
    def sample_local(self,t,settle=0):
        a=self.actor;a.root.location=(0,0,0);a.root.rotation_euler=(0,0,0)
        c=self.ret.clips[self.name];phase=t*self.rate/c["duration"]
        data=self.ret.sample(self.name,t*self.rate)
        if settle:
            for part,(loc,rot) in data.items():
                from mathutils import Quaternion
                data[part]=(loc*(1-settle),rot.slerp(Quaternion((1,0,0,0)),settle))
        self.ret.apply(data)
        # Additive upper-body weight shift; evaluated BEFORE the lock.
        pb=a.bones["torso"];bob=(1-settle)
        pb.matrix_basis=pb.matrix_basis@Euler((.018*math.sin(math.tau*phase),.025*math.sin(math.tau*phase),.018*math.cos(math.tau*phase))).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        verts=mesh_points(a.body)
        # Horizontal mean of the actual sole vertices; vertical contact is the
        # lowest point on each sole. This is an evaluated support-point proxy,
        # not a fixed material vertex or guarantee of zero rolling/slip.
        return [Vector((sum(verts[i].x for i in ids)/len(ids),sum(verts[i].y for i in ids)/len(ids),min(verts[i].z for i in ids))) for ids in self.soles]
    def step(self,t,settle=0,yaw=None):
        if self.last is not None and abs(t-self.last-1/self.fps)>1e-5:raise ValueError("StrideLock requires consecutive fixed-fps samples")
        local=self.sample_local(t,settle);low=min(p.z for p in local)
        old_rot=self.rot.copy()
        if yaw is not None:self.yaw=yaw;self.rot=Matrix.Rotation(yaw,3,"Z")
        if self.prev is None:
            support=min(range(2),key=lambda i:local[i].z);delta=Vector((0,0,0));speed=0
        else:
            eligible=[i for i in range(2) if local[i].z<=low+.018]
            # Prefer actual backward foot sweep in the low phase, with
            # hysteresis when support is still viable.
            def score(i):
                sweep=(local[i].y-self.prev[i].y)*self.fps
                return sweep+(0.12 if i==self.support else 0)
            support=max(eligible,key=score)
            delta=old_rot@self.prev[support]-self.rot@local[support];delta.z=0
            self.pos+=delta
            speed=-((self.rot.inverted()@delta).y)*self.fps
        self.pos.z=self.start.z-low
        a=self.actor;a.root.location=self.pos;a.root.rotation_euler.z=self.yaw
        bpy.context.view_layer.update()
        pts=mesh_points(a.body)
        actual=[Vector((sum(pts[i].x for i in ids)/len(ids),sum(pts[i].y for i in ids)/len(ids),min(pts[i].z for i in ids))) for ids in self.soles]
        old_world=None if self.prev is None else self.prev_world[support]
        velocity=0 if old_world is None else (actual[support]-old_world).length*self.fps
        continuing=self.support==support and self.prev is not None
        floor=min(p.z for p in actual)-self.start.z
        gap=actual[support].z-self.start.z
        row={"time":t,"support":support,"continuing":continuing,"contact_world":list(actual[support]),"velocity":velocity,"floor_error":floor,"contact_gap":gap,"forward_speed":speed,"root":list(self.pos),"settle":settle}
        self.records.append(row);self.prev=local;self.prev_world=actual;self.support=support;self.last=t
        return row
    def report(self):
        stance=[x for x in self.records if x["continuing"] and x["settle"]==0]
        moving=[x for x in self.records[1:] if x["settle"]==0]
        assert stance and moving
        speed=sum(x["forward_speed"] for x in moving)/len(moving)
        rms=math.sqrt(sum(x["velocity"]**2 for x in stance)/len(stance))
        gap=max(abs(x["contact_gap"]) for x in self.records)
        floor=max(abs(x["floor_error"]) for x in self.records)
        # Threshold is a 3D support-proxy velocity, not toe-point velocity.
        return {"cycle":self.name,"fps":self.fps,"rate":self.rate,"mean_forward_speed":speed,"derived_stride":speed*self.ret.clips[self.name]["duration"]/self.rate,"stance_samples":len(stance),"stance_velocity_rms":rms,"max_continuing_velocity":max(x["velocity"] for x in stance),"max_contact_gap":gap,"max_floor_error":floor,"pass":speed>.15 and rms<=.18 and gap<=.02 and floor<=.002,"records":self.records}
