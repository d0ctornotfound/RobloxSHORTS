"""Opt-in articulated studio pose adapter, derived from exact R6 garment mesh.
Never edits the source GLB, original skeleton or imported animation. The
runtime duplicate splits selected rigid limbs at mid-length, retaining
source material and interpolated garment UVs. Only round-two tests use it."""
import math,bmesh,bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from r6_character import mesh_points,dominant_group,bounds,group_points
from character_motion import soles as native_soles

DOWN=Vector((0,0,-1))
def clip(poly,z,above):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        ina=a[0].z>=z if above else a[0].z<=z
        inb=b[0].z>=z if above else b[0].z<=z
        if ina:result.append(a)
        if ina!=inb:
            t=(z-a[0].z)/(b[0].z-a[0].z)
            result.append((a[0].lerp(b[0],t),a[1].lerp(b[1],t)))
    return result

def make_piece(name,polys,origin,materials,cut,above):
    verts=[];faces=[];uv=[];mi=[];smooth=[]
    cutpoints=[]
    for points,mat,sm in polys:
        part=clip(points,cut,above)
        if len(part)<3:continue
        indices=[]
        for v,t in part:
            indices.append(len(verts));verts.append(v-origin);uv.append(t)
            if abs(v.z-cut)<1e-5:cutpoints.append((v.copy(),t.copy()))
        faces.append(indices);mi.append(mat);smooth.append(sm)
    assert verts and faces and cutpoints,name
    # Close the actual clipped cross-section, not an invented external shell.
    # R6 limbs are convex box-like parts; sort unique planar section samples.
    uniq={}
    for v,t in cutpoints:uniq[tuple(round(float(x),5) for x in v)]=(v,t)
    pts=list(uniq.values());c=sum((v for v,t in pts),Vector())/len(pts)
    pts.sort(key=lambda p:math.atan2(p[0].y-c.y,p[0].x-c.x),reverse=above)
    if len(pts)>=3:
        indices=[]
        for v,t in pts:indices.append(len(verts));verts.append(v-origin);uv.append(t)
        faces.append(indices);mi.append(mi[0]);smooth.append(False)
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    for mat in materials:me.materials.append(mat)
    layer=me.uv_layers.new(name="Source garment UV");layer.active_render=True
    for p,m,sm in zip(me.polygons,mi,smooth):
        p.material_index=m;p.use_smooth=sm
        for li in p.loop_indices:layer.data[li].uv=uv[me.loops[li].vertex_index]
    ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
    return ob

class Limb:
    def __init__(self,actor,bone,polys):
        self.actor=actor;self.bone=bone
        pts=[v for poly,_,_ in polys for v,t in poly];lo,hi=bounds(pts)
        self.top=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,hi.z))
        self.end=Vector((self.top.x,self.top.y,lo.z))
        self.mid=self.top.lerp(self.end,.48)
        self.a=(self.mid-self.top).length;self.b=(self.end-self.mid).length
        self.bind=(actor.armature.matrix_world@bone.matrix).inverted()
        materials=list(actor.body.data.materials)
        overlap=min(.025,self.a*.06)
        self.upper=make_piece(actor.root.name+" / "+bone.name+" upper",polys,self.top,materials,self.mid.z-overlap,True)
        self.lower=make_piece(actor.root.name+" / "+bone.name+" lower",polys,self.mid,materials,self.mid.z+overlap,False)
        self.objects=[self.upper,self.lower];actor.meshes.extend(self.objects);actor.skinned.extend(self.objects)
        self.stretch=0
    def transform(self):return self.actor.armature.matrix_world@self.bone.matrix@self.bind
    def joint(self):return self.transform()@self.top
    def rigid(self):
        t=self.transform()
        self.upper.matrix_world=t@Matrix.Translation(self.top)
        self.lower.matrix_world=t@Matrix.Translation(self.mid)
        self.stretch=0
    def place(self,ob,start,end,length,rot):
        vec=end-start;d=vec.length
        if d<1e-7:vec=rot@DOWN;d=1e-7
        q=(rot@DOWN).rotation_difference(vec.normalized()).to_matrix()
        # Explicit, measured minor axial adjustment to keep joint ends joined
        # under body lean. Never scale the flat planted lower leg.
        ob.matrix_world=Matrix.Translation(start)@q.to_4x4()@rot.to_4x4()@Matrix.Diagonal((1,1,d/length,1))
        return abs(d/length-1)
    def ground(self,foot,rot):
        knee=foot+Vector((0,0,self.b))
        self.stretch=self.place(self.upper,self.joint(),knee,self.a,rot)
        self.lower.matrix_world=Matrix.Translation(knee)@rot.to_4x4()
    def solve(self,target,pole,rot):
        start=self.joint();delta=target-start;distance=delta.length
        axis=delta.normalized() if distance>1e-7 else rot@DOWN
        d=min(self.a+self.b-.0005,max(abs(self.a-self.b)+.0005,distance))
        x=(self.a*self.a-self.b*self.b+d*d)/(2*d)
        perpendicular=pole-axis*pole.dot(axis)
        if perpendicular.length<1e-5:perpendicular=axis.cross(Vector((0,0,1)))
        if perpendicular.length<1e-5:perpendicular=axis.cross(Vector((1,0,0)))
        elbow=start+axis*x+perpendicular.normalized()*math.sqrt(max(0,self.a*self.a-x*x))
        end=start+axis*d
        self.stretch=max(self.place(self.upper,start,elbow,self.a,rot),self.place(self.lower,elbow,end,self.b,rot))
        return end
    def sole(self):
        pts=mesh_points(self.lower);z=min(v.z for v in pts);p=[v for v in pts if v.z<=z+.025]
        return Vector((sum(v.x for v in p)/len(p),sum(v.y for v in p)/len(p),z))
    def tilt(self):
        v=(self.lower.matrix_world.to_3x3()@DOWN).normalized()
        return math.degrees(math.acos(max(-1,min(1,-v.z))))

class Articulation:
    def __init__(self,actor,legs=False,arms=False):
        self.actor=actor;actor.reset();actor.root.location=(0,0,0);actor.root.rotation_euler=(0,0,0);bpy.context.view_layer.update()
        selected=(list(actor.legs) if legs else [])+(list(actor.arms) if arms else [])
        names={b.name for b in selected};ob=actor.body;pts=mesh_points(ob);mesh=ob.data
        uv=mesh.uv_layers.active
        groups={v.index:dominant_group(ob,v) for v in mesh.vertices}
        polys={n:[] for n in names}
        for p in mesh.polygons:
            g=groups[p.vertices[0]]
            if g not in names:continue
            assert all(groups[i]==g for i in p.vertices)
            polys[g].append(([(pts[mesh.loops[l].vertex_index].copy(),uv.data[l].uv.copy()) for l in p.loop_indices],p.material_index,p.use_smooth))
        self.limbs={b.name:Limb(actor,b,polys[b.name]) for b in selected}
        self.legs=[self.limbs[b.name] for b in actor.legs] if legs else []
        self.arms=[self.limbs[b.name] for b in actor.arms] if arms else []
        # Remove original selected limb polygons from this actor's disposable
        # runtime mesh only. Skin groups/UVs for remaining body stay intact.
        ob.data=mesh.copy();bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if groups[v.index] in names],context="VERTS")
        bm.to_mesh(ob.data);bm.free();ob.data.update()
        self.rigid()
    def rigid(self):
        for l in self.limbs.values():l.rigid()
        bpy.context.view_layer.update()
    def shift(self,d):
        self.actor.root.location+=d
        for l in self.limbs.values():
            for ob in l.objects:ob.location+=d
        bpy.context.view_layer.update()
    def soles(self):return [l.sole() for l in self.legs] if self.legs else native_soles(self.actor)
    def rot(self,yaw):return Matrix.Rotation(yaw,3,"Z")
    def planted(self,feet,yaw,bend):
        rot=self.rot(yaw);back=rot@Vector((0,1,0))
        hips=[f+Vector((0,0,l.b+l.a*math.cos(bend)))+back*l.a*math.sin(bend) for f,l in zip(feet,self.legs)]
        delta=sum((h-l.joint() for h,l in zip(hips,self.legs)),Vector())/2
        self.shift(delta)
        for l,f in zip(self.legs,feet):l.ground(f,rot)
        bpy.context.view_layer.update()
    def arm_target(self,index,target,pole,yaw):
        result=self.arms[index].solve(target,pole,self.rot(yaw));bpy.context.view_layer.update();return result

def tree_for_object(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
    try:return BVHTree.FromPolygons([ev.matrix_world@v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons])
    finally:ev.to_mesh_clear()

def group_tree(actor,bone):
    ob=actor.body;pts=mesh_points(ob);g=bone.name
    faces=[tuple(p.vertices) for p in ob.data.polygons if dominant_group(ob,ob.data.vertices[p.vertices[0]])==g]
    return BVHTree.FromPolygons(pts,faces) if faces else None

def hug_overlap(a,b):
    # Cross-actor surface intersections, including shoulders/head, torso,
    # and other arm. Not an inference from bounding boxes.
    aa=[group_tree(a,x) for x in a.arms];bb=[group_tree(b,x) for x in b.arms]
    at=[group_tree(a,a.bones["torso"]),tree_for_object(a.head)]
    bt=[group_tree(b,b.bones["torso"]),tree_for_object(b.head)]
    return sum(len(x.overlap(y)) for x,y in [(x,y) for x in aa for y in bb+bt]+[(x,y) for x in bb for y in at]+[(x,y) for x in at for y in bt] if x and y)

def face_grid(actor):
    pts=[actor.face.matrix_world@v.co for v in actor.face.data.vertices]
    c=sum(pts,Vector())/len(pts);dx=(pts[1]-pts[0])*.5;dz=(pts[3]-pts[0])*.5
    return c,dx,dz

def face_hits(cam,actor,blockers):
    c,dx,dz=face_grid(actor);direction=(cam.matrix_world.to_3x3()@DOWN).normalized()
    trees=[tree_for_object(o) for o in blockers]
    count=0
    for x in (-.55,-.275,0,.275,.55):
        for z in (-.52,-.26,0,.26,.52):
            target=c+dx*x+dz*z
            if any(t.ray_cast(target-direction*20,direction,19.999)[0] is not None for t in trees):count+=1
    return count
