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
SKINS={"honey":(.83,.54,.27),"warm_tan":(.68,.38,.18),"peach":(.93,.66,.39),"dad_tan":(.79,.51,.28)}
ROLE_COLORS["dad"]=(SKINS["dad_tan"],(.50,.31,.15),(.025,.027,.035))
GARMENTS={"lead":("hoodie","jeans","warm_tan","young"),"friend":("tee","yellow_denim","peach","friend"),"teacher":("cardigan","stripe_pants","honey","teacher"),"dad":("jacket","stripe_pants","dad_tan","dad")}

def texture_mat(name,path):
    mat=matte(name,(.5,.5,.5));nt=mat.node_tree;bs=nt.nodes.get("Principled BSDF")
    tex=nt.nodes.new("ShaderNodeTexImage");tex.image=bpy.data.images.load(str(path),check_existing=True);tex.image.pack();tex.extension="EXTEND"
    nt.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
    return mat

def fiber_mat(name,color,knit=False):
    m=matte(name,color);nt=m.node_tree;bs=nt.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.86 if knit else .74
    bs.inputs["Specular IOR Level"].default_value=.025
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
    rng=random.Random(81 if style=="lead" else 52)
    color=(.075,.040,.024) if style=="lead" else (.028,.025,.023)
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
                tip=(x+rng.uniform(-.22,.22),yy-.11+rng.uniform(-.10,.10),.88+rng.uniform(-.08,.20))
                mid=(x-.10,yy-.035,.91+rng.uniform(0,.12))
            else:
                tip=(x-.18,yy-.22,.72+rng.uniform(-.04,.13));mid=(x-.04,yy-.04,.89)
            lock((x,yy,.56),mid,tip,.115,.105,idx);idx+=1
    for j in range(9):
        x=-.56+j*.14
        if style=="lead":tip=(x+rng.uniform(-.09,.07),-.695,.12+rng.uniform(.04,.23));control=(x-.08,-.67,.63)
        else:tip=(x-.17,-.67,.35+rng.uniform(-.05,.14));control=(x+.05,-.73,.70)
        lock((x,-.21,.70),control,tip,.117,.090,idx);idx+=1
    for sign in (-1,1):
        for j in range(4):
            yy=-.36+j*.24
            tip=(sign*(.68+rng.uniform(0,.10)),yy-.06,.12+rng.uniform(-.05,.25))
            lock((sign*.46,yy,.65),(sign*.68,yy,.48),tip,.105,.10,idx);idx+=1

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
        self.pose("neutral")

    def _accessories(self):
        super()._accessories()
        if self.role in ("lead","dad"):
            for ob in list(self.accessories):
                if "head hair" in ob.name or "head fringe" in ob.name or "head short block hair" in ob.name:
                    self.accessories.remove(ob);self.meshes.remove(ob);bpy.data.objects.remove(ob,do_unlink=True)
            hair_style(self,self.role)
        elif self.role=="friend":
            m=fiber_mat("Ochre rib-knit beanie",(.60,.23,.035),True)
            cuff=fiber_mat("Dark rib-knit cuff",(.42,.12,.018),True)
            for ob in self.accessories:
                if "beanie" in ob.name:ob.data.materials[0]=cuff if "cuff" in ob.name else m
        elif self.role=="teacher":
            m=fiber_mat("Teacher dark strand hair",(.049,.026,.016))
            for ob in self.accessories:
                if "hair" in ob.name or "bun" in ob.name:ob.data.materials[0]=m
