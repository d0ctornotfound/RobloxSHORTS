"""Authoritative R6 avatar: import the supplied skinned GLB, never rebuild its body.
The only added meshes are accessories and a transparent classic face decal.
Original asset CC BY 4.0 (hopewell664); see assets/R6_ATTRIBUTION.md.
"""
import hashlib
import math
from pathlib import Path
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
from render_demo import cube,empty,material

ASSET=Path(__file__).resolve().parents[1]/"assets"/"r6_rigged.glb"
SOURCE_SHA256="3a0f310faf09cf161f7036a4c0df1a20202b967683700badc4440309c0a7d95a"
FACE_DIR=ASSET.parent/"r6_faces"
BONES={"root":"_rootJoint","torso":"Torso_00","head":"Head_01",
       "left_arm":"Left Arm_02","right_arm":"Right Arm_03",
       "left_leg":"Left Leg_04","right_leg":"Right Leg_05"}
EXPRESSIONS=("neutral","happy","shocked","sad","unimpressed","laughing")
# Keep the native dimensions, scale uniformly only to fit the existing sets.
SCENE_HEIGHT=2.28
ROLE_COLORS={
    "lead":((.84,.60,.29),(.008,.23,.15),(.005,.045,.32)),
    "friend":((.93,.69,.43),(.88,.79,.61),(.95,.48,.001)),
    "teacher":((.88,.64,.42),(.46,.025,.15),(.17,.19,.24)),
    "patron_green":((.86,.58,.33),(.015,.31,.04),(.012,.07,.36)),
    "patron_blue":((.92,.70,.48),(.01,.10,.58),(.96,.50,.002)),
}

def matte(name,color):
    m=material(name,color);bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=1.0
    bs.inputs["Specular IOR Level"].default_value=0
    return m

def face_material(expr,face_dir):
    path=Path(face_dir)/(expr+".png")
    if not path.is_file():raise FileNotFoundError(str(path)+"; generate via scripts/r6_faces.py")
    image=bpy.data.images.load(str(path),check_existing=True)
    assert tuple(image.size)==(1024,1024)
    image.pack()
    mat=bpy.data.materials.new("R6 decal / "+expr);mat.use_nodes=True
    mat.blend_method="HASHED";mat.shadow_method="NONE"
    nt=mat.node_tree;ns=nt.nodes;ns.clear()
    out=ns.new("ShaderNodeOutputMaterial");mix=ns.new("ShaderNodeMixShader")
    transparent=ns.new("ShaderNodeBsdfTransparent");ink=ns.new("ShaderNodeBsdfDiffuse")
    tex=ns.new("ShaderNodeTexImage");tex.image=image;tex.extension="CLIP"
    nt.links.new(tex.outputs["Alpha"],mix.inputs[0])
    nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(ink.outputs[0],mix.inputs[2])
    nt.links.new(tex.outputs["Color"],ink.inputs["Color"]);nt.links.new(mix.outputs[0],out.inputs["Surface"])
    return mat

def bounds(points):
    points=list(points)
    return Vector(tuple(min(v[i] for v in points) for i in range(3))),Vector(tuple(max(v[i] for v in points) for i in range(3)))

def dominant_group(ob,vertex):
    g=max(vertex.groups,key=lambda g:g.weight)
    assert g.weight>.99,("non-rigid R6 skin",ob.name,vertex.index,g.weight)
    return ob.vertex_groups[g.group].name

def mesh_points(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me=ev.to_mesh()
    try:return [ev.matrix_world@v.co for v in me.vertices]
    finally:ev.to_mesh_clear()

def group_points(ob,name):
    points=mesh_points(ob)
    assert len(points)==len(ob.data.vertices)
    return [points[v.index] for v in ob.data.vertices if dominant_group(ob,v)==name]

class R6Character:
    """One independently imported armature and its original skinned meshes.
    All actor positions in scene units; the uniform normalization is isolated
    in rig_space. Props and accessories follow real bones via bone parenting.
    """
    def __init__(self,name,role="lead",height=SCENE_HEIGHT,skin=None,shirt=None,pants=None,
                 face_dir=FACE_DIR):
        if role not in ROLE_COLORS:raise ValueError("Unknown role "+role)
        raw=ASSET.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA256,"wrong GLB bytes"
        self.role=role;self.root=empty(name,(0,0,0))
        self.rig_space=empty(name+" / uniform rig normalization",(0,0,0),self.root)
        before=set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(ASSET))
        imported=[ob for ob in bpy.data.objects if ob not in before]
        rigs=[o for o in imported if o.type=="ARMATURE"]
        assert len(rigs)==1,len(rigs)
        self.armature=rigs[0];self.armature.name=name+" / R6 armature"
        self.skinned=[o for o in imported if o.type=="MESH" and any(m.type=="ARMATURE" and m.object==self.armature for m in o.modifiers)]
        assert len(self.skinned)==2,[(o.name,o.type,[(m.name,m.type) for m in o.modifiers]) for o in imported]
        # The glTF importer may add an unskinned custom-shape display mesh.
        for ob in imported:
            if ob.type=="MESH" and ob not in self.skinned:ob.hide_render=True;ob.hide_viewport=True
        for ob in imported:
            if ob.parent is None:
                world=ob.matrix_world.copy();ob.parent=self.rig_space;ob.matrix_world=world
        bpy.context.view_layer.update()
        assert set(BONES.values()).issubset(self.armature.pose.bones.keys()),list(self.armature.pose.bones.keys())
        assert all(any(m.type=="ARMATURE" and m.object==self.armature for m in o.modifiers) for o in self.skinned)
        self.head=next(o for o in self.skinned if "Head_01" in o.vertex_groups and len(group_points(o,"Head_01"))==len(o.data.vertices))
        self.body=next(o for o in self.skinned if o!=self.head)
        self.head.name=name+" / head skinned";self.body.name=name+" / body skinned"
        # Measure native evaluated rest geometry, not object dimensions alone.
        lo,hi=bounds(v for ob in self.skinned for v in mesh_points(ob))
        hlo,hhi=bounds(mesh_points(self.head));tlo,thi=bounds(group_points(self.body,"Torso_00"))
        native=hi.z-lo.z
        self.measurements={"native_height":native,"native_head":list(hhi-hlo),
            "native_torso":list(thi-tlo),"head_torso_width":(hhi.x-hlo.x)/(thi.x-tlo.x)}
        assert abs(native-5.10125)<.035,self.measurements
        assert all(abs(x-1.2)<.035 for x in hhi-hlo),self.measurements
        assert all(abs(x-y)<.035 for x,y in zip(thi-tlo,(2,1,2))),self.measurements
        assert abs(self.measurements["head_torso_width"]-.6)<.015
        self.scale=height/native
        self.rig_space.scale=(self.scale,)*3
        self.rig_space.location=(-(lo.x+hi.x)*self.scale/2,-(lo.y+hi.y)*self.scale/2,-lo.z*self.scale)
        bpy.context.view_layer.update()
        self.meshes=list(self.skinned);self.accessories=[]
        colors=ROLE_COLORS[role]
        skin=matte(name+" / matte skin",skin or colors[0])
        shirt=matte(name+" / shirt",shirt or colors[1])
        pants=matte(name+" / trousers",pants or colors[2])
        self.head.data.materials.clear();self.head.data.materials.append(skin)
        for poly in self.head.data.polygons:poly.material_index=0
        self.body.data.materials.clear()
        for m in (skin,shirt,pants):self.body.data.materials.append(m)
        for poly in self.body.data.polygons:
            groups={dominant_group(self.body,self.body.data.vertices[i]) for i in poly.vertices}
            assert len(groups)==1,groups
            g=next(iter(groups))
            poly.material_index=1 if g=="Torso_00" else 2 if "Leg_" in g else 0
        self.head_bounds=bounds(mesh_points(self.head))
        self.torso_bounds=bounds(group_points(self.body,"Torso_00"))
        self.bones={k:self.armature.pose.bones[v] for k,v in BONES.items()}
        self.bind_basis={pb.name:pb.matrix_basis.copy() for pb in self.armature.pose.bones}
        self.arms=[self.bones["right_arm"],self.bones["left_arm"]]
        self.legs=[self.bones["right_leg"],self.bones["left_leg"]]
        self.grips=[];self.arm_axes=[]
        for i,pb in enumerate(self.arms):
            blo,bhi=bounds(group_points(self.body,pb.name))
            center=(blo+bhi)/2;end=Vector((center.x,center.y,blo.z+.04*self.scale))
            joint=self.armature.matrix_world@pb.head
            axis=(self.armature.matrix_world@pb.matrix).to_3x3().inverted()@(end-joint)
            self.arm_axes.append(axis.normalized())
            self.grips.append(self.attach_at(name+" / "+pb.name+" grip",pb,end))
        self.leg_axes=[]
        for pb in self.legs:
            blo,bhi=bounds(group_points(self.body,pb.name))
            center=(blo+bhi)/2;end=Vector((center.x,center.y,blo.z+.04*self.scale))
            joint=self.armature.matrix_world@pb.head
            axis=(self.armature.matrix_world@pb.matrix).to_3x3().inverted()@(end-joint)
            self.leg_axes.append(axis.normalized())
        self.face_materials={e:face_material(e,face_dir) for e in EXPRESSIONS}
        self.face=self._decal()
        self._accessories()
        self.pose("neutral")

    def attach_at(self,name,bone,position,rotation=(0,0,0)):
        """Make an unscaled socket bone-parented at an actor-local scene point.
        A COPY_TRANSFORMS constraint on a prop can target this real socket.
        """
        pb=self.bones.get(bone,bone) if isinstance(bone,str) else bone
        if isinstance(pb,str):pb=self.armature.pose.bones[pb]
        ob=empty(name,(0,0,0))
        ob.parent=self.armature;ob.parent_type="BONE";ob.parent_bone=pb.name
        bpy.context.view_layer.update()
        ob.matrix_world=self.root.matrix_world@Matrix.Translation(Vector(position))@Euler(rotation).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        return ob

    def attach_mesh(self,ob,bone):
        world=ob.matrix_world.copy()
        pb=self.bones[bone];ob.parent=self.armature;ob.parent_type="BONE";ob.parent_bone=pb.name
        bpy.context.view_layer.update();ob.matrix_world=world
        self.meshes.append(ob);self.accessories.append(ob)
        return ob

    def _decal(self):
        lo,hi=self.head_bounds;center=(lo+hi)/2
        # A flat front decal covers the central region of the rounded cube.
        # Transparent margins avoid a visible sheet; no body/head geometry edits.
        x=(hi.x-lo.x)*.445;z=(hi.z-lo.z)*.445;y=lo.y-.002
        v=[(center.x-x,y,center.z-z),(center.x+x,y,center.z-z),
           (center.x+x,y,center.z+z),(center.x-x,y,center.z+z)]
        me=bpy.data.meshes.new(self.root.name+" / face decal UV")
        me.from_pydata(v,[],[(0,1,2,3)]);me.update()
        uv=me.uv_layers.new(name="Classic face UV")
        for loop in me.loops:uv.data[loop.index].uv=[(0,0),(1,0),(1,1),(0,1)][loop.vertex_index]
        ob=bpy.data.objects.new(self.root.name+" / face decal",me);bpy.context.collection.objects.link(ob)
        ob.data.materials.append(self.face_materials["neutral"])
        return self.attach_mesh(ob,"head")

    def _accessories(self):
        lo,hi=self.head_bounds;c=(lo+hi)/2;s=self.scale
        def block(label,x,y,z,dx,dy,dz,m,bone="head",angle=0):
            # Coordinates relative to head centre in native rig units.
            pos=(c.x+x*s,c.y+y*s,c.z+z*s)
            ob=cube(self.root.name+" / "+label,pos,(dx*s,dy*s,dz*s),m,bevel=.006*s)
            ob.rotation_euler.y=angle
            bpy.context.view_layer.update()
            return self.attach_mesh(ob,bone)
        hair=matte(self.root.name+" / block hair",(.055,.025,.013))
        if self.role=="lead":
            block("head hair cap",0,.04,.53,1.27,1.18,.24,hair)
            block("head hair back",0,.48,.21,1.22,.31,.55,hair)
            for x,z,a in [(-.43,.73,-.30),(-.13,.83,-.25),(.17,.78,-.22),(.43,.69,-.20)]:
                block("head hair rectangular lock",x,-.13,z,.31,.76,.30,hair,angle=a)
            block("head fringe",-.35,-.51,.40,.43,.20,.26,hair,angle=-.15)
            # Oversized saturated red signature star, torso-bone parented.
            tlo,thi=self.torso_bounds;tc=(tlo+thi)/2
            red=matte(self.root.name+" / saturated red star",(.84,.004,.006));base=matte(self.root.name+" / dark red pin backing",(.19,.006,.009))
            x=tc.x-.29*s;y=tlo.y-.012;z=tc.z+.42*s
            pin=cube(self.root.name+" / signature red pin",(x,y,z),(.39*s,.07*s,.39*s),base,bevel=.005*s)
            self.attach_mesh(pin,"torso")
            verts=[]
            for i in range(10):
                a=math.pi/2+i*math.pi/5;r=(.207 if i%2==0 else .091)*s
                verts.append((x+r*math.cos(a),y-.019,z+r*math.sin(a)))
            me=bpy.data.meshes.new("R6 star");me.from_pydata(verts,[],[tuple(range(10))]);me.update()
            star=bpy.data.objects.new(self.root.name+" / signature red star",me);bpy.context.collection.objects.link(star);star.data.materials.append(red)
            self.attach_mesh(star,"torso")
        elif self.role=="friend":
            hat=matte(self.root.name+" / ochre block beanie",(.78,.29,.045));cuff=matte(self.root.name+" / folded beanie cuff",(.57,.16,.025))
            block("head beanie crown",0,.035,.63,1.30,1.25,.34,hat)
            block("head beanie front cuff",0,-.58,.42,1.32,.15,.22,cuff)
            block("head beanie back cuff",0,.58,.32,1.32,.15,.37,cuff)
            for x in (-.60,.60):block("head beanie side cuff",x,0,.32,.17,1.17,.38,cuff)
        elif self.role=="teacher":
            block("head hair cap",0,.03,.53,1.25,1.18,.25,hair)
            block("head hair back",0,.50,.13,1.23,.28,.80,hair)
            for x in (-.52,.52):block("head hair side",x,.07,.22,.20,1.0,.61,hair)
            self.bun=block("head block bun",0,.43,.83,.58,.58,.52,hair)
            rim=matte(self.root.name+" / burgundy glasses",(.16,.025,.045))
            # Open rectangular frames; eyes remain visible.
            for x in (-.18,.18):
                for z in (-.008,.228):block("head glasses rim",x,-.618,z,.29,.052,.035,rim)
                for dx in (-.13,.13):block("head glasses rim",x+dx,-.618,.11,.035,.052,.23,rim)
            block("head glasses bridge",0,-.618,.13,.09,.05,.035,rim)
            for x in (-.33,.33):block("head glasses temple",x,-.42,.11,.035,.40,.035,rim)
        else:
            block("head short block hair",0,.05,.53,1.24,1.19,.24,hair)

    def pose(self,expression):
        self.face.data.materials[0]=self.face_materials[expression]

    def set_bone(self,bone,rotation,frame=None):
        pb=self.bones[bone];pb.rotation_mode="XYZ"
        pb.matrix_basis=self.bind_basis[pb.name]@Euler(rotation).to_matrix().to_4x4()
        if frame is not None:pb.keyframe_insert("rotation_euler",frame=frame)
        bpy.context.view_layer.update()

    def _aim(self,pb,axis,direction,frame=None):
        """Aim rigid R6 pose bone. Direction in actor axes."""
        pb.rotation_mode="QUATERNION"
        parent=pb.parent
        base=parent.matrix@parent.bone.matrix_local.inverted()@pb.bone.matrix_local if parent else pb.bone.matrix_local
        world=self.root.matrix_world.to_3x3()@Vector(direction)
        armspace=self.armature.matrix_world.to_3x3().inverted()@world
        base=base@self.bind_basis[pb.name]
        local=base.to_3x3().inverted()@armspace
        delta=axis.rotation_difference(local.normalized())
        pb.matrix_basis=self.bind_basis[pb.name]@delta.to_matrix().to_4x4()
        if frame is not None:pb.keyframe_insert("rotation_quaternion",frame=frame)
        bpy.context.view_layer.update()
    def aim_arm(self,index,direction,frame=None):
        self._aim(self.arms[index],self.arm_axes[index],direction,frame)
        return self.grips[index]

    def aim_leg(self,index,direction,frame=None):
        self._aim(self.legs[index],self.leg_axes[index],direction,frame)

    def reset(self):
        for pb in self.armature.pose.bones:pb.matrix_basis=self.bind_basis[pb.name].copy()
        bpy.context.view_layer.update()
