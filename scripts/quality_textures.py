"""Original high-resolution illustrated UV textures. No external art or fonts."""
from array import array
import math
import bpy


def linear(v):
    v=v/255
    return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4


class Canvas:
    def __init__(self,n=1024,color=(0,0,0,0)):
        self.n=n
        self.data=bytearray(bytes(color)*(n*n))

    def rect(self,x0,y0,x1,y1,c):
        n=self.n
        a,b=max(0,int(x0*n)),min(n,math.ceil(x1*n))
        row=bytes(c)*max(0,b-a)
        for y in range(max(0,int(y0*n)),min(n,math.ceil(y1*n))):
            self.data[(y*n+a)*4:(y*n+b)*4]=row

    def ellipse(self,cx,cy,rx,ry,c):
        n=self.n
        for y in range(max(0,int((cy-ry)*n)),min(n,math.ceil((cy+ry)*n))):
            h=1-((y/n-cy)/ry)**2
            if h>=0:
                w=rx*math.sqrt(h)
                self.rect(cx-w,y/n,cx+w,(y+1)/n,c)

    def line(self,pts,width,c):
        for (a,b),(d,e) in zip(pts,pts[1:]):
            steps=max(1,math.ceil(math.hypot(d-a,e-b)*self.n/3))
            for i in range(steps+1):
                f=i/steps
                self.ellipse(a+(d-a)*f,b+(e-b)*f,width/2,width/2,c)

    def polygon(self,pts,c):
        n=self.n
        for iy in range(max(0,int(min(y for x,y in pts)*n)),min(n,math.ceil(max(y for x,y in pts)*n))):
            y=(iy+.5)/n
            xs=[]
            for (a,b),(d,e) in zip(pts,pts[1:]+pts[:1]):
                if min(b,e)<=y<max(b,e):
                    xs.append(a+(y-b)*(d-a)/(e-b))
            xs.sort()
            for x0,x1 in zip(xs[::2],xs[1::2]):
                self.rect(x0,iy/n,x1,(iy+1)/n,c)

    def image(self,name):
        # Blender generated images store linear RGB; explicitly convert the
        # illustrated sRGB palette and preserve straight alpha.
        lut=[linear(i) for i in range(256)]
        pixels=array("f")
        for r,g,b,a in zip(self.data[0::4],self.data[1::4],self.data[2::4],self.data[3::4]):
            pixels.extend((lut[r],lut[g],lut[b],a/255))
        im=bpy.data.images.new(name,width=self.n,height=self.n,alpha=True)
        im.pixels.foreach_set(pixels)
        im.update()
        return im


def face_canvas(expression):
    c=Canvas(1024)
    ink=(22,16,13,255);white=(255,248,231,255);blush=(205,83,91,105)
    def curve(a,b,d,width=.035,color=ink):
        pts=[]
        for n in range(41):
            t=n/40
            pts.append(((1-t)**2*a[0]+2*t*(1-t)*b[0]+t*t*d[0],
                        (1-t)**2*a[1]+2*t*(1-t)*b[1]+t*t*d[1]))
        c.line(pts,width,color)
    for idx,x in enumerate((.32,.68)):
        sign=-1 if idx==0 else 1
        if expression=="sleep_closed":
            curve((x-.075,.65),(x,.70),(x+.075,.65),.026)
        elif expression=="laughing":
            curve((x-.075,.66),(x,.52),(x+.075,.66),.034)
        elif expression in ("tired","unimpressed"):
            c.ellipse(x+(.018 if expression=="tired" else 0),.65,.038,.047,ink)
            curve((x-.08,.60),(x,.585),(x+.08,.60),.026)
        elif expression=="smug":
            c.ellipse(x+.02,.65,.034,.046,ink)
            curve((x-.08,.60),(x,.57),(x+.08,.60),.024)
        elif expression=="embarrassed":
            c.ellipse(x-.018*sign,.675,.034,.045,ink)
            curve((x-.075,.60),(x,.585),(x+.075,.60),.024)
        elif expression=="angry":
            c.ellipse(x,.65,.038,.045,ink)
            if idx==0:curve((x-.09,.52),(x,.55),(x+.09,.60),.035)
            else:curve((x-.09,.60),(x,.55),(x+.09,.52),.035)
        elif expression in ("shocked","surprised"):
            c.ellipse(x,.65,.045,.085,ink)
            c.ellipse(x-.01,.635,.012,.018,white)
            curve((x-.085,.54),(x,.51),(x+.085,.54),.024)
        else:
            c.ellipse(x,.65,.039,.058,ink)
            if expression in ("worried","sad"):
                if idx==0:curve((x-.085,.60),(x,.56),(x+.085,.585),.026)
                else:curve((x-.085,.585),(x,.56),(x+.085,.60),.026)
            else:
                curve((x-.08,.59),(x,.575),(x+.08,.59),.023)
    if expression=="embarrassed":
        c.ellipse(.22,.48,.06,.032,blush);c.ellipse(.78,.48,.06,.032,blush)
    if expression=="laughing":
        c.ellipse(.50,.34,.18,.125,ink)
        c.rect(.36,.385,.64,.415,white)
        c.ellipse(.50,.305,.065,.025,(175,64,68,255))
    elif expression in ("shocked","surprised"):
        c.ellipse(.50,.34,.10,.13,ink)
        c.ellipse(.50,.275,.058,.025,(175,64,68,255))
    elif expression=="happy":
        curve((.27,.40),(.50,.63),(.73,.40),.050)
    elif expression=="sad":
        curve((.30,.30),(.50,.52),(.70,.30),.045)
    elif expression=="angry":
        curve((.32,.34),(.50,.49),(.68,.34),.043)
    elif expression=="worried":
        curve((.32,.30),(.50,.43),(.68,.30),.035)
    elif expression=="embarrassed":
        curve((.41,.36),(.50,.31),(.59,.36),.022)
    elif expression=="smug":
        curve((.34,.35),(.55,.34),(.69,.42),.038)
    elif expression=="unimpressed":
        curve((.36,.35),(.50,.36),(.64,.35),.030)
    elif expression=="tired":
        curve((.36,.34),(.50,.39),(.64,.34),.028)
    else:
        curve((.35,.36),(.50,.33),(.65,.36),.028)
    # Keep the complete expression small and low on the head UV.
    small=Canvas(1024)
    n=c.n
    for y in range(n):
        sy=round((y/n-.36)/.60*n+.53*n)
        if not 0<=sy<n:continue
        for x in range(n):
            sx=round((x/n-.50)/.60*n+.50*n)
            if 0<=sx<n:
                src=(sy*n+sx)*4;dst=(y*n+x)*4
                small.data[dst:dst+4]=c.data[src:src+4]
    return small

def face_material(expression):
    im=face_canvas(expression).image("Hero face 1024 / "+expression)
    mat=bpy.data.materials.new("Hero face / "+expression)
    mat.use_nodes=True
    ns,ls=mat.node_tree.nodes,mat.node_tree.links
    ns.clear()
    out=ns.new("ShaderNodeOutputMaterial")
    mix=ns.new("ShaderNodeMixShader")
    clear=ns.new("ShaderNodeBsdfTransparent")
    # Ink is softly lit, not emissive; thick marks stay legible under key light.
    ink=ns.new("ShaderNodeBsdfDiffuse")
    tex=ns.new("ShaderNodeTexImage")
    tex.image=im
    ls.new(tex.outputs["Alpha"],mix.inputs[0])
    ls.new(tex.outputs["Color"],ink.inputs[0])
    ls.new(clear.outputs[0],mix.inputs[1])
    ls.new(ink.outputs[0],mix.inputs[2])
    ls.new(mix.outputs[0],out.inputs["Surface"])
    return mat


def cloth_canvas(kind):
    colors={"sweater":(24,105,91,255),"sleeve":(24,105,91,255),"tee":(239,222,181,255),
            "tee_sleeve":(239,222,181,255),"denim":(34,61,103,255),"hat":(195,114,29,255),"green_tee":(29,171,51,255),"green_sleeve":(29,171,51,255),"yellow_denim":(255,221,0,255),"blue_tee":(34,105,213,255),"blue_sleeve":(34,105,213,255)}
    c=Canvas(1024,colors[kind])
    dark=(14,64,58,255)
    cream=(241,207,138,255)
    orange=(190,73,31,255)
    if kind in ("sweater","sleeve","hat"):
        if kind=="hat":
            dark=(133,68,17,255)
            cream=(224,151,50,255)
            orange=cream
        # Wide ribbed hem/cuff, and actual drawn Fair Isle diamond motif.
        c.rect(0,0,1,.09,dark)
        for x in range(0,100,2):
            c.rect(x/100,0,x/100+.006,.09,cream if kind=="hat" else (35,128,111,255))
        for y in (.30,.66):
            c.rect(0,y-.075,1,y+.075,dark)
            c.rect(0,y-.085,1,y-.074,orange)
            c.rect(0,y+.074,1,y+.085,orange)
            for x in (.08,.25,.42,.59,.76,.93):
                c.polygon([(x,y+.066),(x+.065,y),(x,y-.066),(x-.065,y)],cream)
                c.polygon([(x,y+.036),(x+.035,y),(x,y-.036),(x-.035,y)],orange)
        if kind=="sweater":
            c.line([(.29,.99),(.33,.91),(.42,.865),(.50,.85),(.58,.865),(.67,.91),(.71,.99)],.06,dark)
            c.line([(.30,.99),(.35,.92),(.50,.875),(.65,.92),(.70,.99)],.012,cream)
    elif kind in ("tee","tee_sleeve","green_tee","green_sleeve","blue_tee","blue_sleeve"):
        seam=(176,154,118,255) if kind.startswith("tee") else (23,66,43,255) if kind.startswith("green") else (21,49,104,255)
        c.rect(0,0,1,.035,seam)
        c.line([(.03,.07),(.97,.07)],.007,(249,236,202,255))
        if kind in ("tee","green_tee","blue_tee"):
            c.line([(.31,1),(.36,.90),(.50,.86),(.64,.90),(.69,1)],.055,(45,85,105,255))
            # Original screen-printed mountain/sun badge with layered ink.
            c.ellipse(.50,.49,.245,.26,(33,77,98,255))
            c.ellipse(.50,.49,.222,.237,(226,158,73,255))
            c.ellipse(.57,.58,.095,.10,(246,213,122,255))
            c.polygon([(.29,.39),(.43,.64),(.52,.50),(.61,.58),(.71,.39)],(34,78,92,255))
            c.polygon([(.43,.64),(.40,.52),(.47,.55)],(249,236,202,255))
            c.polygon([(.31,.36),(.69,.36),(.64,.30),(.36,.30)],(33,77,98,255))
            for x in (.40,.46,.52,.58):
                c.rect(x,.325,x+.025,.337,(245,220,165,255))
        else:
            c.rect(0,.05,1,.10,(45,85,105,255))
    else:
        if kind=="yellow_denim":
            c.rect(0,.93,1,1,(191,142,0,255))
        else:
            c.rect(0,.93,1,1,(24,44,80,255))
        for x in (.055,.945):
            c.line([(x,.04),(x,.95)],.014,(170,126,0,255) if kind=="yellow_denim" else (18,36,66,255))
            for y in range(5,96,4):
                c.rect(x-.006,y/100,x+.006,y/100+.017,(192,136,68,255))
        c.line([(.15,.87),(.22,.76),(.38,.72)],.014,(170,126,0,255) if kind=="yellow_denim" else (20,39,70,255))
        c.line([(.62,.72),(.78,.76),(.85,.87)],.014,(170,126,0,255) if kind=="yellow_denim" else (20,39,70,255))
        c.line([(.48,.96),(.48,.73)],.01,(192,136,68,255))
        c.ellipse(.5,.955,.024,.024,(205,151,73,255))
    # Baked illustrated stitch marks and soft edge shading, not only a shader stripe.
    n=c.n
    for y in range(n):
        v=y/(n-1)
        for x in range(n):
            u=x/(n-1)
            i=(y*n+x)*4
            edge=.84+.16*min(1,min(u,1-u)*9)
            stitch=1+.055*math.sin(x*.67)*math.cos(y*.96)+.025*math.sin(x*.31+y*.4)
            shade=edge*stitch*(.96+.04*math.sin(v*math.pi))
            for k in (0,1,2):
                c.data[i+k]=min(255,int(c.data[i+k]*shade))
    return c


def illustrated_material(kind):
    im=cloth_canvas(kind).image("Original illustrated UV / "+kind)
    mat=bpy.data.materials.new("Hero cloth / "+kind)
    mat.use_nodes=True
    ns,ls=mat.node_tree.nodes,mat.node_tree.links
    bs=ns.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.84
    bs.inputs["Sheen Weight"].default_value=.19
    if kind=="yellow_denim":
        bs.inputs["Sheen Weight"].default_value=.03
        bs.inputs["Specular IOR Level"].default_value=.08
    tex=ns.new("ShaderNodeTexImage")
    tex.image=im
    ls.new(tex.outputs["Color"],bs.inputs["Base Color"])
    noise=ns.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=135
    noise.inputs["Detail"].default_value=2
    bump=ns.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=.13
    bump.inputs["Distance"].default_value=.014
    ls.new(noise.outputs["Fac"],bump.inputs["Height"])
    ls.new(bump.outputs[0],bs.inputs["Normal"])
    return mat
