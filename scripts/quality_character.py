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
    p.update({"skin":skin_material("Honey skin",(.70,.40,.18)),
              "skin2":skin_material("Peach skin",(.85,.56,.30)),
              "hair":material("Espresso molded hair",(.045,.019,.008)),
              "shoe":material("Black canvas shoes",(.023,.027,.031)),
              "sole":material("Cream rubber",(.72,.67,.52)),
              "faces":{k:face_material(k) for k in ("neutral","happy","shocked","sad")}})
    p["hair"].node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value=.39
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
    # Single closed, smooth molded shell with an asymmetric hairline.
    # Rounded-superellipse rings wrap around a squared head, sweeping into
    # a single curved front fringe instead of individual rectangular tufts.
    verts=[]; faces=[]
    N=64
    rings=[(1.00,1.00,0),(1.05,1.04,.10),(1.01,1.01,.25),(.82,.85,.39),(.44,.47,.46)]
    for ri,(sx,sy,dz) in enumerate(rings):
        for j in range(N):
            theta=math.tau*j/N
            co,si=math.cos(theta),math.sin(theta)
            x=.46*sx*math.copysign(abs(co)**.57,co)
            y=.405*sy*math.copysign(abs(si)**.57,si)
            front=max(0,-si)
            back=max(0,si)
            # Front hairline higher than sides/back, swept down at one temple.
            fringe=front**3*(.18+.095*math.sin(2*theta+.7))
            z=2.02+fringe-.12*back+dz
            if ri>=2:
                z=(1-(ri-1)/4)*z+((ri-1)/4)*(2.37+dz*.27)
            verts.append((x,y,z))
    for r in range(len(rings)-1):
        for j in range(N):
            a=r*N+j;b=r*N+(j+1)%N
            faces.append((a,b,b+N,a+N))
    faces.append(tuple(reversed(range(N))))
    faces.append(tuple(range((len(rings)-1)*N,len(rings)*N)))
    mesh=bpy.data.meshes.new(name+" / continuous hair mesh")
    mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name+" / sculpted hair",mesh)
    bpy.context.collection.objects.link(obj);obj.parent=root
    obj.data.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    sub=obj.modifiers.new("Smooth molded silhouette","SUBSURF");sub.levels=2;sub.render_levels=2
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
            box("beanie crown",(0,.015,2.32),(.96,.86,.30),p["hat"],bevel=.14,uv=True)
            box("beanie cuff",(0,.01,2.20),(.99,.88,.14),p["hat"],bevel=.045,uv=True)
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
