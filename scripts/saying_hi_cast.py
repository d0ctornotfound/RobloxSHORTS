"""Story-local cast construction. Reuses locked rig, cloth shells, expression/blink and hair geometry.
No changes to any locked source module. New look recipes require visual review.
"""
import math,random
import bpy
from mathutils import Vector
from PIL import ImageDraw
from r6_character import R6Character,matte
from r6_variant_character import apply_garments,remove_accessories,knitted_beanie,fiber_mat
from r6_variant_textures import srgb
from chapter4_wardrobe import atlas,replace_image,fabric,torso_details
from chapter4_hair import apply_hair
import clothing_system as cs
from render_demo import cube
from quality_cafe import sphere

# role, locked hair choice, hair color, skin (linear RGB), top (sRGB), bottom, construction, pattern
LOOKS={
"narrator":("patron_green","default",(.18,.035,.009),(.60,.32,.13),(34,90,175),(30,47,76),"polo","white_stripe"),
"otis":("patron_blue","curly_crop",(.025,.014,.008),(.83,.54,.27),(45,114,74),(166,143,97),"polo","navy_stripe"),
"june":("patron_blue","curly_crop",(.020,.012,.008),(.26,.105,.043),(200,36,117),(43,76,121),"knit","solid"),
"brody":("patron_green","messy_fringe",(.18,.045,.015),(.93,.66,.39),(36,95,59),(36,39,41),"flannel","plaid"),
"chase":("patron_green","messy_fringe",(.55,.32,.09),(.93,.66,.39),(205,38,42),(76,79,85),"sport","solid"),
"kai":("patron_green","messy_fringe",(.018,.010,.008),(.60,.32,.13),(111,54,158),(212,195,161),"soft","solid"),
"ava":("patron_green","default",(.64,.40,.11),(.93,.66,.39),(224,178,39),(43,78,129),"knit","solid"),
"bella":("patron_green","default",(.025,.015,.010),(.83,.54,.27),(24,140,146),(218,223,219),"polo","solid"),
"cleo":("patron_blue","curly_crop",(.31,.065,.022),(.93,.66,.39),(226,107,36),(92,54,36),"knit","solid"),
"daisy":("patron_green","default",(.029,.015,.009),(.26,.105,.043),(85,163,213),(43,54,79),"knit","solid"),
"ella":("patron_green","default",(.15,.066,.025),(.60,.32,.13),(225,209,169),(106,49,85),"knit","solid"),
"faye":("patron_green","default",(.29,.052,.022),(.93,.66,.39),(35,87,49),(32,40,49),"jacket","solid"),
"gia":("patron_green","messy_fringe",(.015,.010,.008),(.83,.54,.27),(237,97,148),(41,91,153),"sport","solid"),
"hana":("patron_green","default",(.022,.014,.012),(.60,.32,.13),(40,53,112),(219,216,202),"knit","solid"),
"ivy":("patron_green","default",(.53,.49,.36),(.93,.66,.39),(237,107,93),(57,59,63),"knit","solid"),
"leo":("patron_green","default",(.13,.055,.022),(.83,.54,.27),(211,151,29),(31,46,81),"polo","solid"),
"max":("patron_green","messy_fringe",(.022,.014,.009),(.26,.105,.043),(21,158,186),(28,36,49),"jacket","solid"),
"noah":("patron_green","messy_fringe",(.27,.052,.018),(.93,.66,.39),(232,217,185),(68,103,53),"sport","solid"),
"ryan":("patron_green","default",(.57,.37,.12),(.93,.66,.39),(119,39,61),(170,132,90),"knit","solid"),
"sam":("patron_green","messy_fringe",(.025,.014,.008),(.60,.32,.13),(111,116,125),(221,105,26),"jacket","solid"),
}

def painted_atlas(rgb,kind,seed,pattern,skin=None,cutoff=None):
    im=atlas(rgb,kind,seed,skin,cutoff);d=ImageDraw.Draw(im)
    for i in range(4):
        x=(i%2)*512;y=(i//2)*512
        limit=512 if skin is None else round(512*(1-cutoff))-8
        if pattern in ("white_stripe","navy_stripe"):
            color=(237,240,232) if pattern=="white_stripe" else (24,43,74)
            for yy in range(48,limit-26,98):d.rectangle((x+14,y+yy,x+497,y+yy+33),fill=color)
        elif pattern=="plaid":
            for yy in range(35,limit-25,105):d.rectangle((x+13,y+yy,x+497,y+yy+35),fill=(24,36,29))
            for xx in range(50,495,105):d.rectangle((x+xx,y+12,x+xx+26,y+limit-2),fill=(28,42,32))
    return im

def build_cast_actor(cid,record):
    role,hair,hc,skin,top,bot,kind,pattern=LOOKS[cid]
    a=R6Character(cid,role,height=2.28*record["scale"],skin=skin)
    cfg=cs.ROLE_CLOTHES[role];cut=.14 if cid in ("narrator","otis","june","brody","kai","ava","cleo","ella","faye","hana","ivy","ryan","sam","max") else .48
    a.variant_garment=apply_garments(a,cfg["shirt"],cfg["pants"])
    seed=sum(ord(c) for c in cid)
    for token,col,style,pat,sk in (("shirt",top,kind,pattern,None),("pants",bot,"jeans","solid",None),("sleeve",top,kind,pattern,srgb(skin))):
        m=cs._material(a," / "+token);replace_image(m,painted_atlas(col,style,seed,pat,sk,cut if sk else None))
        cs._add_fabric_shader(m,"hoodie" if kind=="soft" else cs._fabric_profile.__name__ if False else ("jeans" if token=="pants" else "tee"))
        if sk:cs._mask_sleeve_bump(m,cut)
    topmat=fabric(a,"private top",top,kind);accent=fabric(a,"private trim",top,kind,.72);pant=fabric(a,"private trousers",bot,"jeans")
    cs._cover_shoulder_caps(a,topmat);cs._make_shell(a,"shirt and sleeves",(cs.TORSO_GROUP,)+cs.ARM_GROUPS,arm_cutoff=cut)
    cs._make_shell(a,"trousers",cs.LEG_GROUPS);cs._add_cuffs(a,accent,cut);cs._add_denim_pockets(a,pant)
    if cid=="kai":cs._add_hoodie_details(a,topmat)
    else:torso_details(a,kind,topmat,accent)
    a.clothing_upgraded=True;a.clothing_report={"sleeve_cutoff_fraction_from_wrist":cut,"shells":2,"story_recipe":cid}
    if cid=="narrator":
        remove_accessories(a,("head short block hair",));knitted_beanie(a)
    else:
        apply_hair(a,hair)
        # Private hair material; retain approved shape but change color for identity.
        for ob in a.accessories:
            if "head ch4 hair" in ob.name and ob.type=="MESH":
                for i in range(len(ob.data.materials)):ob.data.materials[i]=fiber_mat(cid+" hair "+str(i),hc)
    c=sum(a.head_bounds,Vector())/2;s=a.scale;hm=fiber_mat(cid+" custom locks",hc)
    def ball(name,p,dims,mat=hm):
        ob=sphere(cid+" / "+name,tuple(c+s*Vector(p)),tuple(s*v for v in dims),mat);a.attach_mesh(ob,"head");return ob
    def block(name,p,dims,mat=hm):
        ob=cube(cid+" / "+name,tuple(c+s*Vector(p)),tuple(s*v for v in dims),mat,bevel=.035*s);a.attach_mesh(ob,"head");return ob
    if cid=="otis":
        rim=matte("Otis round glasses",(.025,.021,.016))
        for x in (-.235,.235):
            bpy.ops.mesh.primitive_torus_add(major_segments=32,minor_segments=8,location=tuple(c+s*Vector((x,-.645,.13))),rotation=(math.pi/2,0,0),major_radius=.21*s,minor_radius=.025*s)
            ob=bpy.context.object;ob.name="otis / round glasses";ob.data.materials.append(rim);a.attach_mesh(ob,"head")
        block("glasses bridge",(0,-.65,.13),(.10,.04,.035),rim)
    if cid=="june":
        rng=random.Random(882);beads=[matte("June bead "+str(i),col) for i,col in enumerate(((.9,.32,.10),(.8,.68,.10),(.8,.06,.35)))]
        for sign in (-1,1):
            ball("puff bun",(sign*.54,.08,.78),(.70,.66,.66))
            for k in range(8):
                ang=k*math.tau/8;ball("puff curl",(sign*.54+.23*math.cos(ang),.08+.20*math.sin(ang),.86+rng.uniform(-.08,.08)),(.25,.25,.23))
            for k in range(4):
                ball("braid lock",(sign*.59,-.47,.23-k*.15),(.14,.14,.18))
            for k in range(3):ball("bead",(sign*.59,-.47,-.29-k*.09),(.16,.16,.11),beads[k])
    if cid in ("ava","hana","ella"):
        x=.47 if cid=="hana" else 0;z=.80 if cid=="ava" else .38
        ball("tied ponytail or bun",(x,.56,z),(.55,.45,.64 if cid!="ella" else .45))
        if cid!="ella":block("ponytail length",(x,.67,.19),(.37,.30,.86))
    if cid in ("bella","ivy"):
        block("bob back",(0,.52,.07),(1.27,.31,.87 if cid=="bella" else .64))
        for sign in (-1,1):block("bob side",(sign*.59,.05,.03),(.24,1.0,.81 if cid=="bella" else .58))
    if cid in ("daisy","faye"):
        for sign in ((1,) if cid=="daisy" else (-1,1)):
            for k in range(7):ball("braid",(sign*.53,.27,.22-k*.15),(.23,.23,.21))
    if cid in ("chase","sam"):ball("swept quiff",(.10,-.22,.80),(.73,.58,.42))
    if cid=="brody":block("side part",(-.24,-.14,.70),(.66,.82,.22))
    if cid=="max":block("side part",(.28,-.09,.67),(.58,.81,.24))
    bpy.context.view_layer.update()
    return a
