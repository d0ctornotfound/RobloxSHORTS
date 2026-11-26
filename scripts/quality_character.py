"""Hero R6 builder, a versioned replacement for look development.

Keeps the public expression, shoulder/wrist/grip and mesh interfaces of
Stage A. The historic Stage A/B/C sources stay frozen until visual approval.
"""
import math
import bpy
from mathutils import Vector
from render_demo import cube,empty,material
from stage_a_character import Character as LegacyCharacter
from quality_textures import face_material,illustrated_material


def skin_material(name,color):
    m=material(name,color)
    ns,ls=m.node_tree.nodes,m.node_tree.links
    bs=ns.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.47
    noise=ns.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=19
    ramp=ns.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value=.43
    ramp.inputs["To Max"].default_value=.57
    ls.new(noise.outputs["Fac"],ramp.inputs["Value"])
    ls.new(ramp.outputs["Result"],bs.inputs["Roughness"])
    return m


def palette():
    p={k:illustrated_material(k) for k in ("sweater","sleeve","tee","tee_sleeve","denim","hat")}
    p.update({"skin":skin_material("Honey skin",(.55,.29,.105)),
              "skin2":skin_material("Peach skin",(.73,.43,.20)),
              "hair":material("Espresso molded hair",(.028,.012,.005)),
              "shoe":material("Black canvas shoes",(.023,.027,.031)),
              "sole":material("Cream rubber",(.72,.67,.52)),
              "faces":{k:face_material(k) for k in ("neutral","happy","shocked","sad")}})
    ns,ls=p["hair"].node_tree.nodes,p["hair"].node_tree.links
    bs=ns.get("Principled BSDF");bs.inputs["Roughness"].default_value=.48
    wave=ns.new("ShaderNodeTexWave");wave.bands_direction="X";wave.inputs["Scale"].default_value=18;wave.inputs["Distortion"].default_value=2.2
    bump=ns.new("ShaderNodeBump");bump.inputs["Strength"].default_value=.14;bump.inputs["Distance"].default_value=.009
    ls.new(wave.outputs["Color"],bump.inputs["Height"]);ls.new(bump.outputs[0],bs.inputs["Normal"])
    return p


def block_uv(obj):
    """Face-local illustrated panel UVs; every panel is complete, not stretched atlas fragments."""
    mesh=obj.data
    uv=mesh.uv_layers.active or mesh.uv_layers.new(name="Clothing panels")
    lo=[min(v.co[i] for v in mesh.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in mesh.vertices) for i in range(3)]
    for poly in mesh.polygons:
        axis=max(range(3),key=lambda i:abs(poly.normal[i]))
        u,v=(0,2) if axis==1 else ((1,2) if axis==0 else (0,1))
        for li in poly.loop_indices:
            co=mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv=((co[u]-lo[u])/max(hi[u]-lo[u],1e-5),(co[v]-lo[v])/max(hi[v]-lo[v],1e-5))


def hair_mass(name,root,mat):
    """One molded swept shell, with an open underside and deliberate hairline.
    The lower rings lie outside the head's maximum half-width/depth, so the
    sculpt cannot be clipped into a jagged silhouette by the head."""
    verts=[]; faces=[]
    N=96
    # Keep two closely spaced boundary rings outside the head, then curve
    # upward over the crown before tapering to a softly rounded top.
    rings=[(1.0,1.0,0),(1.005,1.005,.025),(1.025,1.025,.10),
           (1.005,1.005,.23),(.94,.95,.35),(.68,.72,.42),(.32,.36,.46)]
    for ri,(sx,sy,lift) in enumerate(rings):
        for j in range(N):
            theta=math.tau*j/N
            co,si=math.cos(theta),math.sin(theta)
            x=.505*sx*math.copysign(abs(co)**.52,co)
            y=.451*sy*math.copysign(abs(si)**.52,si)
            front=max(0,-si);back=max(0,si)
            # A smooth asymmetric sweep, high on the right and lower at the
            # left temple, with sideburns and a low nape.
            bottom=2.055+.205*front**3+.075*front**3*co-.13*back**2
            crown=2.52+.085*(-co)+.045*front
            if ri<=3:
                z=bottom+lift
                if ri==3:z=max(z,2.405)
            else:
                z=crown+(lift-.42)*.85
            verts.append((x-.035*(ri/6)**2,y+.025*(ri/6),z))
    for r in range(len(rings)-1):
        for j in range(N):
            a=r*N+j;b=r*N+(j+1)%N
            faces.append((a,b,b+N,a+N))
    top=len(verts);verts.append((-.055,.025,2.61))
    for j in range(N):faces.append(((len(rings)-1)*N+j,(len(rings)-1)*N+(j+1)%N,top))
    mesh=bpy.data.meshes.new(name+" / continuous swept shell")
    mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name+" / sculpted hair",mesh)
    bpy.context.collection.objects.link(obj);obj.parent=root
    obj.data.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    sub=obj.modifiers.new("Smooth molded silhouette","SUBSURF");sub.levels=2;sub.render_levels=2
    shell=obj.modifiers.new("Hair edge thickness","SOLIDIFY");shell.thickness=.016
    return obj


class Character(LegacyCharacter):
    """Six chunky primary body parts, legacy-compatible wrist and decal controls."""
    PROPORTIONS={"head":[.90,.80,.80],"torso":[1.12,.61,.80],"arm":[.56,.59,.80],"leg":[.55,.60,.80]}
    def __init__(self,name,p,lead=True):
        self.root=empty(name,(0,0,0))
        self.meshes=[];self.arms=[];self.wrists=[];self.grips=[];self.fingers=[]
        self.face_materials=p["faces"]
        skin=p["skin" if lead else "skin2"]
        shirt=p["sweater" if lead else "tee"]
        sleeve=p["sleeve" if lead else "tee_sleeve"]
        def box(label,loc,dims,mat,parent=None,bevel=.025,uv=False):
            obj=cube(name+" / "+label,loc,dims,mat,parent or self.root,bevel)
            self.meshes.append(obj)
            if uv:block_uv(obj)
            return obj
        box("torso",(0,0,1.20),self.PROPORTIONS["torso"],shirt,bevel=.035,uv=True)
        self.head=box("head",(0,0,2.00),self.PROPORTIONS["head"],skin,bevel=.095)
        self.head.modifiers.get("Soft edges").segments=8
        verts=[(-.385,-.402,1.68),(.385,-.402,1.68),(.385,-.402,2.32),(-.385,-.402,2.32)]
        mesh=bpy.data.meshes.new(name+" face UV");mesh.from_pydata(verts,[],[(0,1,2,3)]);mesh.update()
        uv=mesh.uv_layers.new(name="Face UV")
        for loop in mesh.loops:uv.data[loop.index].uv=[(0,0),(1,0),(1,1),(0,1)][loop.vertex_index]
        self.face=bpy.data.objects.new(name+" / expression decal",mesh)
        bpy.context.collection.objects.link(self.face);self.face.parent=self.root
        self.meshes.append(self.face);self.face.data.materials.append(p["faces"]["neutral"])
        if lead:
            self.meshes.append(hair_mass(name,self.root,p["hair"]))
        else:
            # One rounded crown and a knitted folded cuff.
            crown=box("beanie crown",(0,.015,2.37),(.96,.86,.36),p["hat"],bevel=.15,uv=True)
            crown.modifiers.get("Soft edges").segments=8
            cuff=box("beanie cuff",(0,.01,2.20),(.99,.88,.16),p["hat"],bevel=.065,uv=True)
            cuff.modifiers.get("Soft edges").segments=6
        for side in (-1,1):
            arm=empty(name+" / shoulder",(side*.84,0,1.60),self.root)
            if lead:
                box("sleeve",(0,0,-.26),(.56,.59,.52),sleeve,arm,bevel=.035,uv=True)
            else:
                box("short sleeve",(0,0,-.13),(.56,.59,.26),sleeve,arm,bevel=.035,uv=True)
                box("bare forearm",(0,0,-.39),(.55,.57,.28),skin,arm,bevel=.035)
            wrist=empty(name+" / wrist",(0,0,-.65),arm)
            box("palm",(0,.075,0),(.53,.22,.27),skin,wrist,bevel=.045)
            digits=[]
            for sign in (-1,1):
                digit=box("grip finger",(sign*.155,-.095,0),(.17,.26,.19),skin,wrist,bevel=.038)
                digits.append(digit)
            socket=empty(name+" / cup grip",(0,-.137,-.145),wrist)
            self.arms.append(arm);self.wrists.append(wrist);self.grips.append(socket);self.fingers.append(digits)
            leg=empty(name+" / hip",(side*.28,0,.80),self.root)
            box("denim leg",(0,0,-.32),(.55,.60,.64),p["denim"],leg,bevel=.032,uv=True)
            box("sneaker",(0,-.065,-.71),(.56,.69,.13),p["shoe"],leg,bevel=.025)
            box("rubber sole",(0,-.065,-.775),(.57,.70,.05),p["sole"],leg,bevel=.012)
