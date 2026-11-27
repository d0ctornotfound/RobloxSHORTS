"""Approval-only detailed appearance layer over the exact R6 source rig.
Do not change body geometry, weights, bones or the production renderer."""
import math,random
from pathlib import Path
import bpy
from mathutils import Vector
from r6_character import R6Character,ROLE_COLORS,matte,face_material,mesh_points,group_points,bounds,dominant_group
from render_demo import cube

ROOT=Path(__file__).resolve().parents[1]/"assets"/"r6_variants"
EXPRESSIONS=("neutral","happy","smug","tired","worried","laughing","shocked","sad","unimpressed")
SKINS={"honey":(.83,.54,.27),"warm_tan":(.60,.32,.13),"peach":(.93,.66,.39),"dad_tan":(.68,.40,.19)}
ROLE_COLORS["dad"]=(SKINS["dad_tan"],(.50,.31,.15),(.025,.027,.035))
GARMENTS={"lead":("hoodie","jeans","warm_tan","young"),"friend":("tee","yellow_denim","peach","friend"),"teacher":("cardigan","teacher_trousers","honey","teacher"),"dad":("jacket","stripe_pants","dad_tan","dad")}

def texture_mat(name,path):
    mat=matte(name,(.5,.5,.5));nt=mat.node_tree;bs=nt.nodes.get("Principled BSDF")
    tex=nt.nodes.new("ShaderNodeTexImage");tex.image=bpy.data.images.load(str(path),check_existing=True);tex.image.pack();tex.extension="EXTEND"
    nt.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
    return mat

def fiber_mat(name,color,knit=False):
    m=matte(name,color);nt=m.node_tree;bs=nt.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.90 if knit else .83
    bs.inputs["Specular IOR Level"].default_value=.015
    tex=nt.nodes.new("ShaderNodeTexCoord");scale=nt.nodes.new("ShaderNodeVectorMath");scale.operation="MULTIPLY"
    scale.inputs[1].default_value=(28,13,42) if knit else (58,3,1)
    nt.links.new(tex.outputs["Generated" if knit else "UV"],scale.inputs[0])
    noise=nt.nodes.new("ShaderNodeTexNoise");noise.inputs["Scale"].default_value=2.8
    nt.links.new(scale.outputs[0],noise.inputs["Vector"])
    ramp=nt.nodes.new("ShaderNodeValToRGB");ramp.color_ramp.elements[0].position=.20;ramp.color_ramp.elements[0].color=(*[v*.52 for v in color],1)
    ramp.color_ramp.elements[1].position=.82;ramp.color_ramp.elements[1].color=(*[min(1,v*1.55) for v in color],1)
    nt.links.new(noise.outputs["Fac"],ramp.inputs[0]);nt.links.new(ramp.outputs[0],bs.inputs["Base Color"])
    bump=nt.nodes.new("ShaderNodeBump");bump.inputs["Strength"].default_value=.25;bump.inputs["Distance"].default_value=.009
    nt.links.new(noise.outputs["Fac"],bump.inputs["Height"]);nt.links.new(bump.outputs[0],bs.inputs["Normal"])
    return m

def apply_garments(actor,shirt,pants):
    body=actor.body;verts=mesh_points(body)
    groups={g:bounds(group_points(body,g)) for g in ("Torso_00","Left Arm_02","Right Arm_03","Left Leg_04","Right Leg_05")}
    mats={k:texture_mat(actor.role+" / "+k,ROOT/(v+".png")) for k,v in (("shirt",shirt),("pants",pants),("sleeve",actor.role+"_sleeve"))}
    indices={}
    for k,m in mats.items():indices[k]=len(body.data.materials);body.data.materials.append(m)
    uv=body.data.uv_layers.new(name="R6 garment atlas")
    body.data.uv_layers.active=uv;uv.active_render=True
    for poly in body.data.polygons:
        g=dominant_group(body,body.data.vertices[poly.vertices[0]])
        if g not in groups:continue
        k="shirt" if g=="Torso_00" else "pants" if "Leg_" in g else "sleeve"
        poly.material_index=indices[k]
        lo,hi=groups[g];extent=hi-lo
        points=[verts[i] for i in poly.vertices]
        avg=sum(points,Vector())/len(points)
        # Assign panels from nearest axis-aligned surface; mirrored side UVs
        # are acceptable because garments have no text/logos.
        distances=[(abs(avg[i]-lo[i]),i,-1) for i in range(3)]+[(abs(avg[i]-hi[i]),i,1) for i in range(3)]
        _,axis,sign=min(distances)
        panel=0 if axis==1 and sign<0 else 1 if axis==1 else 2 if axis==0 else 3
        horizontal=0 if axis!=0 else 1
        vertical=2 if axis!=2 else 1
        for li in poly.loop_indices:
            v=verts[body.data.loops[li].vertex_index]
            u=(v[horizontal]-lo[horizontal])/max(extent[horizontal],1e-6)
            z=(v[vertical]-lo[vertical])/max(extent[vertical],1e-6)
            if axis==1 and sign>0:u=1-u
            uv.data[li].uv=((panel%2)*.5+.003+.494*u,1-(panel//2)*.5-.497+.494*z)
    return {"shirt":shirt,"pants":pants,"sleeves":actor.role+"_sleeve","atlas_resolution":[1024,1024]}

def hair_style(actor,style):
    c=sum(actor.head_bounds,Vector())/2;s=actor.scale
    rng=random.Random(81 if style=="lead" else 97 if style=="teacher" else 52)
    color=(.019,.010,.006) if style=="lead" else (.018,.009,.005) if style=="teacher" else (.009,.008,.007)
    mats=[fiber_mat(actor.role+" / directional strands "+str(i),tuple(v*f for v in color)) for i,f in enumerate((.70,.90,1.12,1.35))]
    # A low fitted cap, not a large spherical puff: cuboid-like cross-section
    # curves around the back, ears and upper forehead.
    v=[];f=[];uvs=[];N=24
    for j,(rx,ry,z) in enumerate(((.63,.62,.26),(.65,.63,.53),(.54,.52,.69),(.27,.30,.78))):
        for i in range(N):
            t=math.tau*i/N;co,si=math.cos(t),math.sin(t)
            zz=z+.18*max(0,-si)**4 if j==0 else z
            v.append((rx*math.copysign(abs(co)**.58,co),ry*math.copysign(abs(si)**.58,si),zz))
            uvs.append((i/N,j/3))
    for j in range(3):
        for i in range(N):a=j*N+i;b=j*N+(i+1)%N;f.append((a,b,b+N,a+N))
    f.append(tuple(range(3*N,4*N)))
    def mesh(label,vs,fs,uv,mat,smooth):
        me=bpy.data.meshes.new(actor.role+" / "+label);me.from_pydata([tuple(c+s*Vector(a)) for a in vs],[],fs);me.update()
        ob=bpy.data.objects.new(actor.root.name+" / head "+label,me);bpy.context.collection.objects.link(ob);ob.data.materials.append(mat)
        layer=me.uv_layers.new(name="Strand flow")
        for p in me.polygons:
            p.use_smooth=smooth
            for l in p.loop_indices:layer.data[l].uv=uv[me.loops[l].vertex_index]
        actor.attach_mesh(ob,"head");return ob
    mesh("fitted hair cap",v,f,uvs,mats[0],True)
    def lock(start,control,end,width,depth,idx):
        start,control,end=map(Vector,(start,control,end));vs=[];fs=[];uv=[];steps=7;sides=8
        for j in range(steps):
            t=j/(steps-1);pos=(1-t)**2*start+2*t*(1-t)*control+t*t*end
            tangent=(2*(1-t)*(control-start)+2*t*(end-control)).normalized()
            cross=tangent.cross(Vector((0,1,0)))
            if cross.length<.1:cross=tangent.cross(Vector((0,0,1)))
            cross.normalize();other=tangent.cross(cross).normalized();taper=max(.025,(1-t)**.70)
            for k in range(sides):
                a=math.tau*k/sides
                vs.append(tuple(pos+cross*(math.cos(a)*width*taper)+other*(math.sin(a)*depth*taper)))
                uv.append((k/sides,t))
        for j in range(steps-1):
            for k in range(sides):a=j*sides+k;b=j*sides+(k+1)%sides;fs.append((a,b,b+sides,a+sides))
        fs.extend((tuple(reversed(range(sides))),tuple(range((steps-1)*sides,steps*sides))))
        mesh("strand lock %02d"%idx,vs,fs,uv,mats[idx%len(mats)],True)
    idx=0
    # Layered crown and side silhouette with tapered points. Dad's hair is
    # swept sideways and shorter; lead has deliberately irregular spiky fringe.
    for row in range(3):
        yy=.28-row*.23
        for j in range(8):
            x=-.54+j*.154+rng.uniform(-.025,.025)
            if style=="lead":
                tip=(x+rng.uniform(-.26,.26),yy+.03+rng.uniform(-.20,.20),.86+rng.uniform(-.05,.20))
                mid=(x-.10,yy-.035,.91+rng.uniform(0,.12))
            elif style=="teacher":
                tip=(x+.22,yy+.24,.72+rng.uniform(-.035,.05));mid=(x+.10,yy+.10,.83)
            else:
                tip=(x-.18,yy-.22,.72+rng.uniform(-.04,.13));mid=(x-.04,yy-.04,.89)
            lock((x,yy,.56),mid,tip,.115,.105,idx);idx+=1
    for j in range(9):
        x=-.56+j*.14
        if style=="lead":tip=(x+rng.uniform(-.09,.07),-.695,.12+rng.uniform(.04,.23));control=(x-.08,-.67,.63)
        elif style=="teacher":tip=(x+.21,-.64,.42+rng.uniform(-.02,.08));control=(x+.08,-.65,.68)
        else:tip=(x-.17,-.67,.35+rng.uniform(-.05,.14));control=(x+.05,-.73,.70)
        lock((x,-.21,.70),control,tip,.117,.090,idx);idx+=1
    for sign in (-1,1):
        for j in range(4):
            yy=-.36+j*.24
            tip=(sign*.64,yy+.16,.25+rng.uniform(0,.12)) if style=="teacher" else (sign*(.68+rng.uniform(0,.10)),yy-.06,.12+rng.uniform(-.05,.25))
            lock((sign*.46,yy,.65),(sign*.68,yy,.48),tip,.105,.10,idx);idx+=1

def accessory_mesh(actor,label,vertices,faces,uv,mat,bone="head"):
    me=bpy.data.meshes.new(actor.role+" / "+label)
    me.from_pydata(vertices,[],faces);me.update()
    ob=bpy.data.objects.new(actor.root.name+" / "+label,me);bpy.context.collection.objects.link(ob);ob.data.materials.append(mat)
    layer=me.uv_layers.new(name="Directional fibers")
    for p in me.polygons:
        p.use_smooth=True
        for l in p.loop_indices:layer.data[l].uv=uv[me.loops[l].vertex_index]
    return actor.attach_mesh(ob,bone)

def remove_accessories(actor,tokens):
    for ob in list(actor.accessories):
        if any(k in ob.name for k in tokens):
            actor.accessories.remove(ob);actor.meshes.remove(ob);bpy.data.objects.remove(ob,do_unlink=True)

def knit_material(name,color):
    m=matte(name,color);nt=m.node_tree;bs=nt.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.96
    uv=nt.nodes.new("ShaderNodeTexCoord")
    sep=nt.nodes.new("ShaderNodeSeparateXYZ");nt.links.new(uv.outputs["UV"],sep.inputs[0])
    # Alternating ribs in U, tighter crosswise stitches in V. Both feed bump.
    def mathnode(op,a,b):
        node=nt.nodes.new("ShaderNodeMath");node.operation=op
        for i,x in enumerate((a,b)):
            if isinstance(x,(float,int)):node.inputs[i].default_value=x
            else:nt.links.new(x,node.inputs[i])
        return node.outputs[0]
    u=mathnode("MULTIPLY",sep.outputs["X"],math.tau*44)
    vv=mathnode("MULTIPLY",sep.outputs["Y"],math.tau*24)
    ribs=mathnode("MULTIPLY",mathnode("ADD",mathnode("SINE",u,0),1),.5)
    cross=mathnode("MULTIPLY",mathnode("ADD",mathnode("SINE",vv,0),1),.5)
    fac=mathnode("ADD",mathnode("MULTIPLY",ribs,.75),mathnode("MULTIPLY",cross,.25))
    ramp=nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color=(*[v*.47 for v in color],1);ramp.color_ramp.elements[1].color=(*[v*1.30 for v in color],1)
    nt.links.new(fac,ramp.inputs[0]);nt.links.new(ramp.outputs[0],bs.inputs["Base Color"])
    bump=nt.nodes.new("ShaderNodeBump");bump.inputs["Strength"].default_value=.45;bump.inputs["Distance"].default_value=.008
    nt.links.new(fac,bump.inputs["Height"]);nt.links.new(bump.outputs[0],bs.inputs["Normal"])
    return m

def knitted_beanie(actor):
    remove_accessories(actor,("beanie",))
    c=sum(actor.head_bounds,Vector())/2;s=actor.scale
    crown=knit_material("Ochre wool crown",(.37,.105,.010))
    brim=knit_material("Folded ribbed wool cuff",(.31,.079,.008))
    def rings(label,profiles,mat,cap=False):
        N=132;vs=[];fs=[];uv=[]
        for j,(rx,ry,z,offset) in enumerate(profiles):
            for i in range(N):
                a=math.tau*i/N
                # Raised physical ribs and soft squarish fit over cube head.
                rib=1+.018*math.cos(44*a)
                x=rx*math.copysign(abs(math.cos(a))**.66,math.cos(a))*rib
                y=ry*math.copysign(abs(math.sin(a))**.66,math.sin(a))*rib+offset
                vs.append(tuple(c+s*Vector((x,y,z+.015*math.sin(3*a)))))
                uv.append((i/N,j/(len(profiles)-1)))
        for j in range(len(profiles)-1):
            for i in range(N):a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
        if cap:fs.append(tuple(range((len(profiles)-1)*N,len(profiles)*N)))
        return accessory_mesh(actor,"head "+label,vs,fs,uv,mat)
    rings("knitted beanie crown",[(.64,.64,.43,0),(.66,.66,.60,.015),(.62,.61,.76,.09),(.48,.49,.91,.20),(.28,.32,1.0,.27),(.055,.065,1.01,.29)],crown,True)
    rings("knitted beanie folded brim",[(.65,.65,.36,0),(.69,.68,.39,0),(.69,.68,.55,0),(.66,.65,.58,0)],brim)

def teacher_accessories(actor):
    remove_accessories(actor,("head hair","head block bun","head glasses"))
    # Swept layered locks, then an actual rounded coiled bun.
    hair_style(actor,"teacher")
    c=sum(actor.head_bounds,Vector())/2;s=actor.scale
    mat=fiber_mat("Teacher swept espresso bun",(.018,.009,.005))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=tuple(c+s*Vector((0,.54,.86))))
    bun=bpy.context.object;bun.name=actor.root.name+" / head rounded swept bun";bun.scale=(.38*s,.34*s,.39*s);bun.data.materials.append(mat)
    for p in bun.data.polygons:p.use_smooth=True
    bpy.context.view_layer.update();actor.bun=actor.attach_mesh(bun,"head")
    rim=matte("Teacher fine burgundy frame",(.095,.009,.025))
    lens=bpy.data.materials.new("Teacher clear optical lenses");lens.use_nodes=True
    nt=lens.node_tree;nt.nodes.clear();out=nt.nodes.new("ShaderNodeOutputMaterial")
    mix=nt.nodes.new("ShaderNodeMixShader");mix.inputs[0].default_value=.065
    clear=nt.nodes.new("ShaderNodeBsdfTransparent");gloss=nt.nodes.new("ShaderNodeBsdfGlossy");gloss.inputs["Roughness"].default_value=.12
    nt.links.new(clear.outputs[0],mix.inputs[1]);nt.links.new(gloss.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs[0])
    lens.blend_method="HASHED";lens.shadow_method="NONE"
    def bar(label,x,y,z,dx,dy,dz,m):
        ob=cube(actor.root.name+" / head "+label,tuple(c+s*Vector((x,y,z))),(dx*s,dy*s,dz*s),m,bevel=.006*s)
        bpy.context.view_layer.update();return actor.attach_mesh(ob,"head")
    for x in (-.18,.18):
        for z in (.004,.230):bar("glasses fine rim",x,-.624,z,.31,.038,.020,rim)
        for dx in (-.146,.146):bar("glasses fine rim",x+dx,-.624,.117,.020,.038,.225,rim)
        # Thin clear panes rather than solid opaque blocks.
        vs=[tuple(c+s*Vector((x+dx,-.632,z))) for dx,z in ((-.135,.02),(.135,.02),(.135,.216),(-.135,.216))]
        accessory_mesh(actor,"head clear lens",vs,[(0,1,2,3)],[(0,0),(1,0),(1,1),(0,1)],lens)
    bar("glasses bridge",0,-.624,.135,.055,.035,.023,rim)
    for x in (-.335,.335):bar("glasses temple",x,-.41,.135,.025,.42,.025,rim)

def cardigan_details(actor):
    lo,hi=actor.torso_bounds;c=(lo+hi)/2;s=actor.scale
    knit=knit_material("Teacher deep rose rib-knit trim",(.27,.025,.075))
    button=matte("Teacher pearl buttons",(.68,.36,.23))
    placket=cube(actor.root.name+" / cardigan raised placket",(c.x,lo.y-.012,c.z-.03*s),(.12*s,.04*s,1.60*s),knit,bevel=.006*s)
    actor.attach_mesh(placket,"torso")
    for side in (-1,1):
        ob=cube(actor.root.name+" / cardigan raised collar",(c.x+side*.27*s,lo.y-.016,hi.z-.26*s),(.14*s,.055*s,.55*s),knit,bevel=.008*s)
        ob.rotation_euler.y=side*.51;bpy.context.view_layer.update();actor.attach_mesh(ob,"torso")
    for z in (.51,.15,-.21,-.57):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.062*s,depth=.035*s,location=(c.x,lo.y-.033,c.z+z*s),rotation=(math.pi/2,0,0))
        ob=bpy.context.object;ob.name=actor.root.name+" / raised cardigan button";ob.data.materials.append(button)
        bpy.context.view_layer.update();actor.attach_mesh(ob,"torso")

class VariantCharacter(R6Character):
    def __init__(self,name,role="lead",skin_tone=None,facial_hair=None,flat=False):
        shirt,pants,default_skin,identity=GARMENTS[role]
        self.variant_skin=skin_tone or default_skin
        super().__init__(name,role,skin=SKINS[self.variant_skin],face_dir=ROOT/identity)
        self.face_materials.update({e:face_material(e,ROOT/identity) for e in EXPRESSIONS if e not in self.face_materials})
        self.variant_garment=apply_garments(self,shirt,pants) if not flat else {"fallback":True}
        self.facial_hair=None
        kind=facial_hair if facial_hair is not None else ("stubble" if role=="dad" else None)
        if kind:
            assert kind in ("stubble","beard")
            # Separate transparent UV plane, same head bone, slightly in front
            # of the expression. ExpressionTrack can swap the underlying face.
            ob=self.face.copy();ob.data=self.face.data.copy();ob.name=name+" / head "+kind+" overlay"
            bpy.context.collection.objects.link(ob)
            ob.data.materials[0]=face_material(kind,ROOT)
            world=ob.matrix_world.copy();world.translation.y-=.0015;ob.matrix_world=world
            self.meshes.append(ob);self.accessories.append(ob);self.facial_hair=kind
        if role=="teacher":cardigan_details(self)
        self.pose("neutral")

    def _accessories(self):
        super()._accessories()
        if self.role=="lead":
            # Remove redundant backing slab, which was visibly detached at
            # the feet in imported-cycle renders. Retain the red star decal.
            remove_accessories(self,("signature red pin",))
        if self.role in ("lead","dad"):
            for ob in list(self.accessories):
                if "head hair" in ob.name or "head fringe" in ob.name or "head short block hair" in ob.name:
                    self.accessories.remove(ob);self.meshes.remove(ob);bpy.data.objects.remove(ob,do_unlink=True)
            hair_style(self,self.role)
        elif self.role=="friend":
            knitted_beanie(self)
        elif self.role=="teacher":
            teacher_accessories(self)
