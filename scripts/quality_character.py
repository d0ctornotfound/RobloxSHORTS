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
    bs.inputs["Roughness"].default_value=.91
    bs.inputs["Specular IOR Level"].default_value=.04
    noise=ns.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=19
    ramp=ns.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value=.87
    ramp.inputs["To Max"].default_value=.96
    ls.new(noise.outputs["Fac"],ramp.inputs["Value"])
    ls.new(ramp.outputs["Result"],bs.inputs["Roughness"])
    return m


def palette():
    p={k:illustrated_material(k) for k in ("sweater","sleeve","tee","tee_sleeve","denim","hat","green_tee","green_sleeve","yellow_denim","blue_tee","blue_sleeve")}
    p.update({"skin":skin_material("Honey skin",(.55,.29,.105)),
              "skin2":skin_material("Peach skin",(.73,.43,.20)),
              "hair":material("Espresso molded hair",(.028,.012,.005)),
              "hair2":material("Patron auburn hair",(.17,.049,.013)),
              "badge":material("Signature red enamel pin",(.62,.022,.012)),
              "badge_center":material("Signature cream star",(.94,.76,.37)),
              "shoe":material("Black canvas shoes",(.023,.027,.031)),
              "sole":material("Cream rubber",(.72,.67,.52)),
              "faces":{k:face_material(k) for k in ("neutral","happy","smug","tired","worried","laughing","shocked","surprised","sad","unimpressed","embarrassed","angry","sleep_closed")}})
    ns,ls=p["hair"].node_tree.nodes,p["hair"].node_tree.links
    bs=ns.get("Principled BSDF");bs.inputs["Roughness"].default_value=.91;bs.inputs["Specular IOR Level"].default_value=.035
    p["hair2"].node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value=.92
    p["hair2"].node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value=.035
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


def hair_mass(name,root,mat,variant="swept"):
    """Closed sculpted base plus curved tapered locks, joined into one mesh.
    Hair is explicitly NOT a hat, and never uses a textile material.
    """
    parts=[]
    # Wide low head: top z=2.28, half width .532, depth .39.
    # Base follows the forehead and wraps the ears/nape.
    N=64;verts=[];faces=[]
    for ri,(sx,sy,lift) in enumerate([(1,1,0),(1.03,1.02,.09),(.95,.95,.21),(.62,.65,.30)]):
        for j in range(N):
            t=math.tau*j/N;co,si=math.cos(t),math.sin(t)
            x=.575*sx*math.copysign(abs(co)**.54,co)
            y=.435*sy*math.copysign(abs(si)**.54,si)
            z=2.00+.19*max(0,-si)**4-.10*max(0,si)**2+lift
            if ri>=2:z=max(z,2.30+(ri-2)*.08)
            verts.append((x,y,z))
    for r in range(3):
        for j in range(N):
            a=r*N+j;b=r*N+(j+1)%N;faces.append((a,b,b+N,a+N))
    faces.append(tuple(reversed(range(N))))
    faces.append(tuple(range(3*N,4*N)))
    def obj_from(v,f,label):
        me=bpy.data.meshes.new(label);me.from_pydata(v,[],f);me.update()
        ob=bpy.data.objects.new(label,me);bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)
        for poly in me.polygons:poly.use_smooth=True
        return ob
    base=obj_from(verts,faces,name+" / hair base");parts.append(base)
    def lock(start,mid,end,width,depth,label):
        # Swept lock is an elliptical tube tapering to a pointed tip.
        start,mid,end=map(Vector,(start,mid,end));v=[];f=[];sides=9
        for i in range(9):
            t=i/8;center=(1-t)**2*start+2*t*(1-t)*mid+t*t*end
            tangent=(2*(1-t)*(mid-start)+2*t*(end-mid)).normalized()
            cross=tangent.cross(Vector((0,1,0))).normalized()
            if cross.length<.01:cross=Vector((1,0,0))
            other=tangent.cross(cross).normalized()
            taper=(1-t)**.47*.95+.035
            for j in range(sides):
                ang=math.tau*j/sides
                v.append(tuple(center+cross*(width*taper*math.cos(ang))+other*(depth*taper*math.sin(ang))))
        for i in range(8):
            for j in range(sides):
                a=i*sides+j;b=i*sides+(j+1)%sides;f.append((a,b,b+sides,a+sides))
        f.append(tuple(reversed(range(sides))));f.append(tuple(range(8*sides,9*sides)))
        parts.append(obj_from(v,f,name+" / "+label))
    # Thick swept silhouette and overlapping tapered front fringe; no slabs.
    if variant=="swept":
        for i,(x,y,tipx,tipy,tipz) in enumerate([
            (-.40,-.08,-.76,-.12,2.49),(-.29,-.09,-.66,-.18,2.76),
            (-.10,-.04,-.36,-.10,2.91),(.12,.02,-.04,-.03,2.86),
            (.33,.06,.20,.07,2.75),(.45,.08,.62,.06,2.58),
            (-.32,.20,-.64,.30,2.58),(.03,.24,-.18,.40,2.72),
            (.34,.24,.49,.43,2.56)]):
            lock((x,y,2.27),(x-.13,y-.03,2.65),(tipx,tipy,tipz) ,.26,.235,"crown lock "+str(i))
        for i,(x,tx,tz) in enumerate([(-.41,-.58,2.07),(-.23,-.43,2.11),(-.04,-.20,2.16),(.15,.02,2.21),(.34,.22,2.22),(.46,.47,2.15)]):
            lock((x,-.31,2.40),(x-.08,-.52,2.39),(tx,-.49,tz) ,.205,.15,"fringe lock "+str(i))
    else:
        for i in range(7):
            t=math.tau*i/7;x=.39*math.cos(t);y=.28*math.sin(t)
            lock((x,y,2.25),(x*1.2,y*1.25,2.49),(x*1.46,y*1.36,2.46),.19,.17,"short lock "+str(i))
    bpy.ops.object.select_all(action="DESELECT")
    for ob in parts:ob.select_set(True)
    bpy.context.view_layer.objects.active=base
    bpy.ops.object.join()
    base.name=name+" / swept spiky hair";base.parent=root
    return base


def signature_pin(name,root,p):
    # Recurring red enamel star on the lead's left chest, leaves hair exposed.
    from stage_a_cafe import cylinder
    disk=cylinder(name+" / signature red pin",(-.34,-.336,1.58),.083,.028,p["badge"],root)
    disk.rotation_euler.x=math.pi/2
    v=[]
    for i in range(10):
        a=math.pi/2+i*math.pi/5;r=.061 if i%2==0 else .027
        v.append((-.34+r*math.cos(a),-.353,1.58+r*math.sin(a)))
    me=bpy.data.meshes.new(name+" star");me.from_pydata(v,[],[tuple(range(10))]);me.update()
    ob=bpy.data.objects.new(name+" / signature gold star",me);bpy.context.collection.objects.link(ob);ob.parent=root
    ob.data.materials.append(p["badge_center"])
    return [disk,ob]


class Character(LegacyCharacter):
    """Six chunky primary body parts, legacy-compatible wrist and decal controls."""
    PROPORTIONS={"head":[1.064,.78,.502],"torso":[1.12,.65,.889],"arm":[.56,.65,1.26],"leg":[.56,.64,.889]}
    BODY_HEIGHT=2.28
    def __init__(self,name,p,lead=True,role=None,wardrobe=None):
        role=role or ("lead" if lead else "friend")
        self.role=role
        self.legs=[]
        self.root=empty(name,(0,0,0))
        self.meshes=[];self.arms=[];self.wrists=[];self.grips=[];self.fingers=[]
        self.face_materials=p["faces"]
        self.current_expression="neutral";self._expression_tracks=[]
        skin=p["skin" if lead else "skin2"]
        default={"lead":("sweater","sleeve","denim"),"friend":("tee","tee_sleeve","yellow_denim"),"patron_green":("green_tee","green_sleeve","denim"),"patron_blue":("blue_tee","blue_sleeve","yellow_denim")}
        self.wardrobe=wardrobe or default[role]
        shirt,sleeve,pants=(p[k] for k in self.wardrobe)
        def box(label,loc,dims,mat,parent=None,bevel=.025,uv=False):
            obj=cube(name+" / "+label,loc,dims,mat,parent or self.root,bevel)
            self.meshes.append(obj)
            if uv:block_uv(obj)
            return obj
        box("torso",(0,0,1.3335),self.PROPORTIONS["torso"],shirt,bevel=.035,uv=True)
        self.head=box("head",(0,0,2.029),self.PROPORTIONS["head"],skin,bevel=.065)
        self.head.modifiers.get("Soft edges").segments=8
        verts=[(-.46,-.392,1.82),(.46,-.392,1.82),(.46,-.392,2.24),(-.46,-.392,2.24)]
        mesh=bpy.data.meshes.new(name+" face UV");mesh.from_pydata(verts,[],[(0,1,2,3)]);mesh.update()
        uv=mesh.uv_layers.new(name="Face UV")
        for loop in mesh.loops:uv.data[loop.index].uv=[(0,0),(1,0),(1,1),(0,1)][loop.vertex_index]
        self.face=bpy.data.objects.new(name+" / expression decal",mesh)
        bpy.context.collection.objects.link(self.face);self.face.parent=self.root
        bpy.context.view_layer.update()
        face_world=self.face.matrix_world.copy()
        self.face.parent=self.head
        self.face.matrix_world=face_world
        self.meshes.append(self.face);self.face.data.materials.append(p["faces"]["neutral"])
        if role=="lead":
            self.meshes.append(hair_mass(name,self.root,p["hair"],"swept"))
            self.meshes.extend(signature_pin(name,self.root,p))
        elif role=="friend":
            # One rounded crown and a knitted folded cuff.
            # Continuous rounded cap with a fitted lower edge, wrapping temples
            # and nape while leaving the low face ink unobstructed.
            v=[];f=[];N=64
            for i,(sx,sy,lift) in enumerate([(1,1,0),(1.025,1.025,.045),(1.02,1.02,.12),(.98,.98,.25),(.75,.78,.36),(.35,.38,.405)]):
                for j in range(N):
                    a=math.tau*j/N;co,si=math.cos(a),math.sin(a)
                    bottom=1.99+.18*max(0,-si)**4-.065*max(0,si)**2
                    z=bottom+lift if i<3 else max(bottom+lift,2.31+(i-3)*.075)
                    v.append((.56*sx*math.copysign(abs(co)**.55,co),.422*sy*math.copysign(abs(si)**.55,si),z))
            for i in range(5):
                for j in range(N):
                    a=i*N+j;b=i*N+(j+1)%N;f.append((a,b,b+N,a+N))
            f.append(tuple(range(5*N,6*N)))
            mesh=bpy.data.meshes.new(name+" fitted knit");mesh.from_pydata(v,[],f);mesh.update()
            uv=mesh.uv_layers.new(name="Knitted wrap")
            for poly in mesh.polygons:
                poly.use_smooth=True
                for li in poly.loop_indices:
                    idx=mesh.loops[li].vertex_index
                    uv.data[li].uv=((idx%N)/N,(idx//N)/5)
            cap=bpy.data.objects.new(name+" / wrapped beanie",mesh);bpy.context.collection.objects.link(cap);cap.parent=self.root
            cap.data.materials.append(p["hat"]);self.meshes.append(cap)
            sub=cap.modifiers.new("Rounded knit","SUBSURF");sub.levels=1;sub.render_levels=1
            shell=cap.modifiers.new("Knit thickness","SOLIDIFY");shell.thickness=.022
        else:
            self.meshes.append(hair_mass(name,self.root,p["hair2" if role=="patron_green" else "hair"],"short"))
        for side in (-1,1):
            arm=empty(name+" / shoulder",(side*.84,0,1.778),self.root)
            if role=="lead":
                box("sleeve",(0,0,-.49),(.56,.65,.98),sleeve,arm,bevel=.035,uv=True)
            else:
                box("short sleeve",(0,0,-.19),(.56,.65,.38),sleeve,arm,bevel=.035,uv=True)
                box("bare forearm",(0,0,-.68),(.55,.63,.60),skin,arm,bevel=.035)
            wrist=empty(name+" / wrist",(0,0,-1.115),arm)
            box("palm",(0,.075,0),(.53,.22,.27),skin,wrist,bevel=.045)
            digits=[]
            for sign in (-1,1):
                digit=box("grip finger",(sign*.155,-.095,0),(.17,.26,.19),skin,wrist,bevel=.038)
                digits.append(digit)
            socket=empty(name+" / cup grip",(0,-.137,-.145),wrist)
            self.arms.append(arm);self.wrists.append(wrist);self.grips.append(socket);self.fingers.append(digits)
            leg=empty(name+" / hip",(side*.28,0,.889),self.root)
            self.legs.append(leg)
            box("denim leg",(0,0,-.38),(.56,.64,.76),pants,leg,bevel=.032,uv=True)
            box("sneaker",(0,-.065,-.80),(.57,.72,.13),p["shoe"],leg,bevel=.025)
            box("rubber sole",(0,-.065,-.864),(.58,.73,.05),p["sole"],leg,bevel=.012)
        from facial_expressions import enable_blinking
        enable_blinking(bpy.context.scene,[self])
