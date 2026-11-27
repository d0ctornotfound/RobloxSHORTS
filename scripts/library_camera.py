"""Reusable portrait camera paths, with explicit composition metrics.
All positions are world scene units, lens in mm, angles in degrees.
No implicit lens widening, collision avoidance or occlusion waiver."""
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import point_at
from r6_character import mesh_points

MOVES=("static","push_in","pull_back","pan","tracking_follow","orbit","over_shoulder","pov","close_up_punch_in")
def ease(t):
    t=max(0,min(1,t));return t*t*(3-2*t)
def V(x):return Vector(x)
def create(scene,name="Library camera",lens=48):
    data=bpy.data.cameras.new(name);data.sensor_fit="HORIZONTAL";data.lens=lens
    cam=bpy.data.objects.new(name,data);scene.collection.objects.link(cam);scene.camera=cam
    return cam
def apply(cam,kind,t,position,target,lens=48,distance=.9,angle=35,end_target=None,
          subject_start=None,subject_now=None,shoulder=None,eye=None,look=None,punch_lens=68,frame=None):
    """Evaluate one absolute sample. t in [0,1]; fixed lens except punch-in.
    For tracking supply actual subject positions. OTS/POV require world anchors."""
    if kind not in MOVES:raise ValueError(kind)
    p,q=V(position),V(target);u=ease(t);offset=p-q
    if kind in ("push_in","pull_back"):
        delta=offset.normalized()*distance*u
        p=p-delta if kind=="push_in" else p+delta
    elif kind=="pan":
        if end_target is None:raise ValueError("pan needs end_target")
        q=q.lerp(V(end_target),u)
    elif kind=="tracking_follow":
        if subject_start is None or subject_now is None:raise ValueError("tracking needs positions")
        d=V(subject_now)-V(subject_start);p+=d;q+=d
    elif kind=="orbit":
        a=math.radians(angle)*u;x,y=offset.x,offset.y
        p=q+V((math.cos(a)*x-math.sin(a)*y,math.sin(a)*x+math.cos(a)*y,offset.z))
    elif kind=="over_shoulder":
        if shoulder is None:raise ValueError("OTS needs shoulder anchor")
        p=V(shoulder)+offset
    elif kind=="pov":
        if eye is None or look is None:raise ValueError("POV needs eye and look")
        p=V(eye);q=V(look)
    elif kind=="close_up_punch_in":
        # Fast smooth change across first 25% of the beat, then hold.
        lens=lens+(punch_lens-lens)*ease(min(1,t*4))
    if (p-q).length<.01:raise ValueError("degenerate camera")
    cam.location=p;cam.data.lens=lens;point_at(cam,q)
    if frame is not None:
        cam.keyframe_insert("location",frame=frame);cam.keyframe_insert("rotation_euler",frame=frame)
        cam.data.keyframe_insert("lens",frame=frame)
    bpy.context.view_layer.update()
    return {"move":kind,"t":t,"position":list(p),"target":list(q),"lens":lens}
def points(actor,head=False):
    objs=[o for o in actor.meshes if o.type=="MESH" and o!=actor.face and (not head or "head" in o.name.lower())]
    return [v for o in objs for v in mesh_points(o)]
def project(scene,cam,verts):
    p=[world_to_camera_view(scene,cam,v) for v in verts]
    if not p:raise ValueError("empty projection")
    return (min(v.x for v in p),max(v.x for v in p),min(v.y for v in p),max(v.y for v in p),min(v.z for v in p))
def metrics(scene,cam,actors,margin=.035):
    rows=[]
    for a in actors:
        b=project(scene,cam,points(a));h=project(scene,cam,points(a,True))
        face=project(scene,cam,mesh_points(a.face))
        rows.append({"name":a.root.name,"bounds":list(b),"head_bounds":list(h),
           "coverage":max(0,min(1,b[3])-max(0,b[2])),
           "body_safe":b[4]>0 and margin<=b[0]<=b[1]<=1-margin and margin<=b[2]<=b[3]<=1-margin,
           "head_safe":h[4]>0 and margin<=h[0]<=h[1]<=1-margin and margin<=h[2]<=h[3]<=1-margin,
           "face_center":[(face[0]+face[1])/2,(face[2]+face[3])/2]})
    return rows
def fit_two_shot(scene,cam,actors,target=None,minimum=.45,margin=.035,allowed=None):
    """Search position/lens, preserving 45%+ for BOTH, with safe heads.
    Stagger actors in depth when necessary; do not relax threshold.
    Caller can reject positions via allowed(position,target). Actual visibility
    must still be checked by object-ID render; projection is not occlusion."""
    if len(actors)!=2:raise ValueError("two actors required")
    q=V(target) if target is not None else sum((a.root.location for a in actors),V((0,0,0)))/2+V((0,0,1.38))
    cache=[(a,points(a),points(a,True),mesh_points(a.face)) for a in actors]
    best=None
    for angle in (0,-8,8,-15,15,-22,22,-30,30,-40,40):
        a=math.radians(angle)
        for d in (3.4,3.8,4.2,4.6,5.0):
            for z in (1.75,2.1,2.45):
                p=q+V((d*math.sin(a),-d*math.cos(a),z-q.z))
                if allowed is not None and not allowed(p,q):continue
                for lens in (34,38,42,46,50,54,58,62,66):
                    apply(cam,"static",0,p,q,lens)
                    rows=[]
                    for actor,body,heads,face in cache:
                        b=project(scene,cam,body);h=project(scene,cam,heads);f=project(scene,cam,face)
                        rows.append((b,h,f))
                    coverage=[max(0,min(1,b[3])-max(0,b[2])) for b,h,f in rows]
                    safe=all(h[4]>0 and margin<=h[0]<=h[1]<=1-margin and margin<=h[2]<=h[3]<=1-margin for b,h,f in rows)
                    # Preserve faces, avoid a compressed overlap; permit intentional
                    # partial lower-body crop, not a clipped head.
                    separation=abs(sum(rows[0][2][:2])/2-sum(rows[1][2][:2])/2)
                    full_safe=all(b[4]>0 and margin<=b[0]<=b[1]<=1-margin and margin<=b[2]<=b[3]<=1-margin for b,h,f in rows)
                    if safe and full_safe and separation>=.20 and min(coverage)>=minimum:
                        # Prefer frontal composition and balanced screen size.
                        score=min(coverage)-.4*abs(coverage[0]-coverage[1])-.0015*abs(angle)
                        if best is None or score>best[0]:best=(score,p.copy(),q.copy(),lens)
    if best is None:raise RuntimeError("No safe >=45% two-shot; reblock depth/spacing rather than lower target")
    _,p,q,lens=best
    apply(cam,"static",0,p,q,lens)
    return {"position":list(p),"target":list(q),"lens":lens,"subjects":metrics(scene,cam,actors,margin)}
