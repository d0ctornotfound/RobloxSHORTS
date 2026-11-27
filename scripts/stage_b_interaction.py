"""Reusable wrist attachment, gravity release and expression animation."""
import math
import bpy
from mathutils import Vector


def smoothstep(x):
    x=min(1.0,max(0.0,x))
    return x*x*(3.0-2.0*x)


def blend_direction(a,b,t):
    return Vector(a).lerp(Vector(b),smoothstep(t)).normalized()


def aim_arm(actor,index,direction):
    """Aim the R6 shoulder's local -Z axis at a direction in actor space."""
    arm=actor.arms[index]
    arm.rotation_mode="QUATERNION"
    arm.rotation_quaternion=Vector(direction).normalized().to_track_quat("-Z","Y")
    return actor.upright_grip(index)


def key_arm(actor,index,frame,closed=False):
    actor.grip_closed(index,closed)
    actor.arms[index].keyframe_insert("rotation_quaternion",frame=frame)
    actor.wrists[index].keyframe_insert("rotation_quaternion",frame=frame)
    for finger in actor.fingers[index]:
        finger.keyframe_insert("location",frame=frame)
        finger.keyframe_insert("rotation_euler",frame=frame)


class GripAttachment:
    """An animated parent relationship implemented by a world-space constraint.

    The grip socket is a real child of the hand at a defined offset. A prop
    follows that socket exactly while bound. On release, its last evaluated
    world pose is retained, then its independent trajectory is keyed.
    """
    def __init__(self,prop,socket):
        self.prop=prop
        self.socket=socket
        self.constraint=prop.constraints.new("COPY_TRANSFORMS")
        self.constraint.name="Hand grip / animated parent"
        self.constraint.target=socket
        self.constraint.target_space="WORLD"
        self.constraint.owner_space="WORLD"
        self.constraint.influence=0
        self.last_world=None

    def bind(self,frame):
        self.constraint.influence=1
        self.constraint.keyframe_insert("influence",frame=frame)
        bpy.context.view_layer.update()
        self.last_world=self.prop.matrix_world.copy()
        error=(self.last_world.translation-self.socket.matrix_world.translation).length
        if error>1e-5:
            raise RuntimeError("Grip attachment failed: "+str(error))
        return error

    def independent(self,frame,position,rotation=(0,0,0)):
        self.constraint.influence=0
        self.constraint.keyframe_insert("influence",frame=frame)
        self.prop.location=position
        self.prop.rotation_euler=rotation
        self.prop.keyframe_insert("location",frame=frame)
        self.prop.keyframe_insert("rotation_euler",frame=frame)
        bpy.context.view_layer.update()

    def release(self):
        if self.last_world is None:
            raise RuntimeError("Cannot release an unbound prop")
        return self.last_world.translation.copy()

    def constant_switches(self):
        action=self.prop.animation_data.action
        for curve in action.fcurves:
            if curve.data_path.endswith(".influence"):
                for k in curve.keyframe_points:
                    k.interpolation="CONSTANT"
            else:
                for k in curve.keyframe_points:
                    k.interpolation="LINEAR"


class GravityDrop:
    """Analytic upright drop with one damped bounce and a supported rest.

    Positions are measured at the prop's bottom origin. For a round table,
    its radius must contain the full prop footprint at every sample.
    """
    def __init__(self,origin,support_z,center=None,radius=None,
                 footprint=.151,gravity=9.81,restitution=.20):
        self.origin=Vector(origin)
        self.z=support_z
        self.g=gravity
        self.e=restitution
        if origin.z<support_z:
            raise ValueError("Release below support surface")
        if center is not None:
            d=math.hypot(origin.x-center[0],origin.y-center[1])
            if d+footprint>radius:
                raise ValueError("Cup footprint outside support")
        self.impact=math.sqrt(2*(origin.z-support_z)/gravity)
        self.up_speed=gravity*self.impact*restitution
        self.settle=self.impact+2*self.up_speed/gravity

    def at(self,t):
        t=max(0,t)
        if t<self.impact:
            z=self.origin.z-.5*self.g*t*t
        elif t<self.settle:
            dt=t-self.impact
            z=self.z+self.up_speed*dt-.5*self.g*dt*dt
        else:
            z=self.z
        return Vector((self.origin.x,self.origin.y,max(z,self.z)))


class ExpressionTrack:
    """Actual image decals with deterministic blink override and paired reactions."""
    MAJOR_REACTIONS={
        "shocked":((-.22,0,.035),(-.14,0,-.035)),
        "surprised":((-.24,0,.045),(-.15,0,-.04)),
        "laughing":((-.17,0,.075),(-.11,0,.035)),
        "happy":((-.075,0,.045),(-.045,0,.02)),
        "embarrassed":((.18,0,-.055),(.095,0,-.035)),
        "angry":((-.075,0,.06),(-.065,0,.015)),
        "worried":((.12,0,-.035),(.06,0,-.02)),
        "sad":((.16,0,.015),(.085,0,.005)),
        "smug":((-.045,0,.13),(-.035,0,.035)),
    }
    def __init__(self,actor):
        self.actor=actor
        self.decals={}
        self.expression_keys={}
        self._reaction_expression="neutral"
        self._reaction_start_frame=None
        for expression,mat in actor.face_materials.items():
            obj=actor.face.copy()
            obj.data=actor.face.data.copy()
            obj.name=actor.root.name+" / animated face "+expression
            bpy.context.collection.objects.link(obj)
            obj.data.materials[0]=mat
            self.decals[expression]=obj
        actor.face.hide_render=True
        if not hasattr(actor,"_expression_tracks"):actor._expression_tracks=[]
        actor._expression_tracks.append(self)

    def expression_at(self,frame):
        eligible=[f for f in self.expression_keys if f<=frame]
        return self.expression_keys[max(eligible)] if eligible else "neutral"

    def reaction(self,frame,expression,fps):
        """Return short head/torso recoil when a major decal changes."""
        if expression!=self._reaction_expression:
            self._reaction_expression=expression
            self._reaction_start_frame=frame if expression in self.MAJOR_REACTIONS else None
        if self._reaction_start_frame is None or expression not in self.MAJOR_REACTIONS:
            return {"head":(0,0,0),"torso":(0,0,0),"expression":expression,"weight":0.0}
        elapsed=max(0.0,(frame-self._reaction_start_frame)/max(1.0,float(fps)))
        weight=smoothstep(elapsed/.12)*(1-smoothstep(max(0.0,(elapsed-.16)/.38)))
        head,torso=self.MAJOR_REACTIONS[expression]
        return {"head":tuple(v*weight for v in head),
                "torso":tuple(v*weight for v in torso),
                "expression":expression,"weight":weight}

    def key(self,frame,expression):
        if expression not in self.decals:raise KeyError("Missing expression decal: "+expression)
        self.expression_keys[int(frame)]=expression
        self.actor.current_expression=expression
        for name,obj in self.decals.items():
            obj.hide_render=name!=expression
            obj.keyframe_insert("hide_render",frame=frame)
        from facial_expressions import refresh_expression
        refresh_expression(self.actor)

    def constant_switches(self):
        for obj in self.decals.values():
            if obj.animation_data and obj.animation_data.action:
                for curve in obj.animation_data.action.fcurves:
                    for k in curve.keyframe_points:
                        k.interpolation="CONSTANT"
