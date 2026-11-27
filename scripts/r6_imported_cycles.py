"""Convert RBXM R6 poses into the supplied GLB's actual joint rest bases.
Uses both source Motor6D bind rotations, original translations, source times.
Target bone pivots and proportions are deliberately preserved, not reauthored.
"""
import bisect,math,statistics
from pathlib import Path
import bpy
from mathutils import Matrix,Vector,Quaternion
from r6_character import mesh_points,dominant_group
from rbxm_animation import parse

SOURCE=Path(__file__).resolve().parents[1]/"assets"/"animations"/"run_walk_roblox.bin"
MAPPING={"Torso":"torso","Head":"head","Left Arm":"left_arm","Right Arm":"right_arm","Left Leg":"left_leg","Right Leg":"right_leg"}
# Roblox right +X, up +Y, forward -Z -> this actor's anatomical right -X,
# up +Z, front -Y. This is a proper rotation (determinant +1).
B=Matrix(((-1,0,0),(0,0,1),(0,1,0)))

def mat(r):return Matrix((r[:3],r[3:6],r[6:9]))
def load():return parse(SOURCE.read_bytes())
class Retarget:
    def __init__(self,actor,data=None):
        self.actor=actor;self.data=data or load()
        actor.armature.animation_data_clear();actor.root.location=(0,0,0);actor.root.rotation_euler=(0,0,0);actor.reset()
        bpy.context.view_layer.update()
        r=actor.armature.matrix_world@actor.bones["right_arm"].head;l=actor.armature.matrix_world@actor.bones["left_arm"].head
        assert r.x<l.x,("source/target handedness mismatch",list(r),list(l))
        self.map={};self.full={}
        for part,key in MAPPING.items():
            pb=actor.bones[key];motor=self.data["motors"][part]
            c0,c1=mat(motor["C0"]["r"]),mat(motor["C1"]["r"])
            assert max(abs(c0[i][j]-c1[i][j]) for i in range(3) for j in range(3))<1e-5,"different neutral part axes"
            A=(actor.armature.matrix_world@pb.matrix).to_3x3()
            Q=A.normalized().inverted()@B@c1
            assert abs(Q.determinant()-1)<1e-4
            self.map[part]=(pb,Q,A.inverted()@B@c1*actor.scale)
        self.clips={}
        for name,c in self.data["clips"].items():
            keys=[];last={}
            for f in c["keyframes"]:
                row={}
                for part,(pb,Q,T) in self.map.items():
                    source=f["poses"][part];rot=(Q@mat(source["r"])@Q.inverted()).to_quaternion();rot.normalize()
                    if part in last and rot.dot(last[part])<0:rot.negate()
                    last[part]=rot.copy()
                    translation=T@Vector(source["t"])
                    row[part]=(translation,rot)
                keys.append(row)
            self.clips[name]={"keys":keys,"times":[f["time"] for f in c["keyframes"]],"duration":c["duration"],"source":c}
        self.actor.reset()
    def sample(self,name,seconds,loop=True):
        c=self.clips[name];d=c["duration"];t=seconds%d if loop else min(d,max(0,seconds))
        times=c["times"];i=min(len(times)-2,max(0,bisect.bisect_right(times,t)-1))
        u=(t-times[i])/(times[i+1]-times[i]);a,b=c["keys"][i],c["keys"][i+1]
        return {part:(a[part][0].lerp(b[part][0],u),a[part][1].slerp(b[part][1],u)) for part in MAPPING}
    def apply(self,pose):
        for part,(pb,Q,T) in self.map.items():
            loc,rot=pose[part];pb.rotation_mode="QUATERNION"
            pb.matrix_basis=self.actor.bind_basis[pb.name]@Matrix.Translation(loc)@rot.to_matrix().to_4x4()
        bpy.context.view_layer.update()
    def at(self,name,seconds,loop=True):self.apply(self.sample(name,seconds,loop))
    def actions(self):
        """Named, fake-user Actions at original 60 Hz. Endpoints preserved.
        For a different output fps use sample/at or remap action time in NLA.
        """
        rig=self.actor.armature;rig.animation_data_create();created={}
        for name,c in self.clips.items():
            action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data.action=action
            for t,row in zip(c["times"],c["keys"]):
                self.apply(row);f=1+t*60
                for pb,Q,T in self.map.values():
                    pb.keyframe_insert("location",frame=f,group=pb.name)
                    pb.keyframe_insert("rotation_quaternion",frame=f,group=pb.name)
            for curve in action.fcurves:
                for k in curve.keyframe_points:k.interpolation="LINEAR"
                curve.modifiers.new("CYCLES")
            action["source_sha256"]=self.data["source_sha256"];action["source_name"]=c["source"]["source_name"];action["duration_seconds"]=c["duration"];action["source_fps"]=60
            created[name]=action
        rig.animation_data.action=None;self.actor.reset()
        return created
    def verify(self):
        """Round-trip every imported target bone basis back to source CFrame."""
        max_r=max_t=0;count=0
        for c in self.clips.values():
            for row,original in zip(c["keys"],c["source"]["keyframes"]):
                self.apply(row)
                for part,(pb,Q,T) in self.map.items():
                    d=self.actor.bind_basis[pb.name].inverted()@pb.matrix_basis
                    source_r=Q.inverted()@d.to_3x3().normalized()@Q
                    source_t=T.inverted()@d.translation
                    ref=original["poses"][part];r=mat(ref["r"])
                    max_r=max(max_r,max(abs(source_r[i][j]-r[i][j]) for i in range(3) for j in range(3)))
                    max_t=max(max_t,(source_t-Vector(ref["t"])).length);count+=1
        assert count==510 and max_r<2e-4 and max_t<2e-4,(count,max_r,max_t)
        self.actor.reset()
        return {"body_poses":count,"max_rotation_matrix_element_error":max_r,"max_translation_studs_error":max_t}
    def calibrate(self,name):
        """Estimate stride speed from back-sweeping low sole points.
        This is an explicit root-motion calibration, not authored root motion.
        No IK, stance lock, or alteration of the source bone trajectories.
        """
        a=self.actor;a.reset();bpy.context.view_layer.update();rest=mesh_points(a.body)
        soles=[]
        for bone in a.legs:
            ids=[v.index for v in a.body.data.vertices if dominant_group(a.body,v)==bone.name]
            low=min(rest[i].z for i in ids);soles.append([i for i in ids if rest[i].z<=low+.025])
        tracks=[]
        c=self.clips[name]
        for row in c["keys"]:
            self.apply(row);pts=mesh_points(a.body)
            tracks.append([sum((pts[i] for i in ids),Vector())/len(ids) for ids in soles])
        velocities=[]
        for j,(p,q) in enumerate(zip(tracks,tracks[1:])):
            dt=c["times"][j+1]-c["times"][j];minz=min(v.z for v in p)
            for i in range(2):
                dy=(q[i].y-p[i].y)/dt
                if p[i].z<minz+.035 and q[i].z<min(v.z for v in q)+.035 and dy>.05:velocities.append(dy)
        assert len(velocities)>=4,("could not calibrate stance",name,velocities)
        speed=statistics.median(velocities);assert .15<speed<12,(name,speed)
        residual=math.sqrt(sum((v-speed)**2 for v in velocities)/len(velocities))
        a.reset()
        return {"speed_scene_units_per_second":speed,"stride_scene_units":speed*c["duration"],"stance_samples":len(velocities),"estimated_stance_slip_rms_units_per_second":residual}
