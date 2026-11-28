"""Chapter 4 wardrobe candidates, separate from locked Chapter 3 source.
Choose at construction time; never mutate an animated actor's wardrobe in-place.
"""
import bpy
import numpy as np
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from r6_character import R6Character, matte
from r6_variant_character import apply_garments, remove_accessories
from r6_variant_textures import SKINS, srgb
from library_character import character, clothed_character
import clothing_system as cs
from chapter4_hair import apply_hair

# Top construction, top sRGB, trousers construction, trouser sRGB.
WARDROBE = {
 "lead": {"forest_bomber":("jacket",(51,91,67),"jeans",(48,57,76)),
          "navy_sleepwear":("pajama",(65,99,147),"soft",(65,99,147))},
 "friend":{"rugby_polo":("polo",(30,112,138),"chino",(188,151,92)),
           "track_kit":("sport",(192,63,42),"soft",(45,53,66))},
 "teacher":{"navy_formal":("formal",(38,58,91),"chino",(39,49,65)),
            "oat_knit":("knit",(188,154,113),"jeans",(43,69,85))},
 "dad":{"charcoal_suit":("formal",(49,51,61),"chino",(49,51,61)),
        "weekend_flannel":("flannel",(125,55,42),"jeans",(43,66,95))},
 "librarian":{"teal_cardigan":("knit",(42,107,108),"chino",(112,93,74)),
              "plum_blazer":("formal",(91,55,94),"chino",(41,49,54))},
 "patron_green":{"school_polo":("polo",(224,219,189),"chino",(48,76,109))},
 "patron_blue":{"sports_kit":("sport",(128,61,154),"soft",(55,58,78))},
}
SKIN_KEY=dict(lead="warm_tan",friend="peach",teacher="honey",dad="dad_tan",
              librarian="honey",patron_green="patron_green",patron_blue="patron_blue")
PROFILE=dict(jacket="jacket",formal="jacket",pajama="tee",knit="cardigan",
             flannel="hoodie",polo="tee",sport="green_tee",jeans="jeans",
             chino="teacher_trousers",soft="hoodie")

def atlas(rgb,kind,seed,skin=None,cutoff=None):
    """Private 4-panel atlas with seams/folds but no painted pockets/buttons."""
    n=512; im=Image.new("RGB",(2*n,2*n)); rng=np.random.default_rng(seed)
    y,x=np.mgrid[0:n,0:n]/n
    rgb=np.array(rgb,dtype=float)
    for i in range(4):
        grain=rng.normal(0,2.2,(n,n))+2*np.sin(x*500*3.14)+1.8*np.cos(y*490*3.14)
        folds=4*np.sin(13*x+4*y+i)+3*np.sin(17*y-3*x)
        arr=rgb[None,None,:]+(grain+folds)[...,None]
        if kind in ("flannel","pajama"):
            grid=(np.cos(x*math_tau()*5)+np.cos(y*math_tau()*7))*8
            arr+=grid[...,None]
        if kind=="sport" and i in (0,1):
            arr+=((x<.13)|(x>.87))[...,None]*27
        if kind=="polo" and i in (0,1):
            arr+=((y>.37)&(y<.49))[...,None]*22
        panel=Image.fromarray(np.clip(arr,0,255).astype("uint8"));d=ImageDraw.Draw(panel)
        dark=tuple(int(max(0,v-30)) for v in rgb)
        light=tuple(int(min(255,v+28)) for v in rgb)
        for q in (12,499):
            d.line([(q,8),(q,504)],fill=dark,width=5)
            for z in range(10,502,16):d.line([(q+4,z),(q+4,z+7)],fill=light,width=2)
        d.line([(5,480),(507,480)],fill=dark,width=4)
        if skin is not None:
            z=round(n*(1-cutoff));d.rectangle((0,z,n,z+2*n),fill=tuple(skin))
            d.line([(0,z-7),(n,z-7)],fill=dark,width=4)
        im.paste(panel,((i%2)*n,(i//2)*n))
    return im

def math_tau():return 6.283185307179586

def replace_image(material,im):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/"atlas.png";im.save(p)
        image=bpy.data.images.load(str(p),check_existing=False);image.pack()
    for n in material.node_tree.nodes:
        if n.type=="TEX_IMAGE":n.image=image

def fabric(actor,label,rgb,kind,factor=1):
    m=matte(actor.role+" / ch4 "+label,tuple(cs._srgb_linear(v)*factor for v in rgb))
    cs._add_fabric_shader(m,PROFILE[kind]);return m

def torso_details(a,kind,top,accent):
    lo,hi=a.torso_bounds;c=(lo+hi)*.5;e=hi-lo;y=lo.y-.023
    box=lambda label,x,z,w,h,m,rot=0:cs._add_box(a,"ch4 "+label,(x,y,z),(w,.027,h),m,rotation_y=rot)
    # Physically raised waist hem; other details depend on garment construction.
    box("waist hem",c.x,lo.z+.025,e.x*.98,.041,accent)
    if kind in ("jacket","formal","knit","flannel","pajama","polo"):
        h=.31 if kind=="polo" else .82
        box("front placket",c.x,hi.z-e.z*(.07+h/2),e.x*.07,e.z*h,accent)
        for sign in (-1,1):
            box("collar",c.x+sign*e.x*.14,hi.z-e.z*.11,e.x*.12,e.z*.19,accent,sign*.45)
        button=matte(a.role+" / ch4 buttons",(.37,.30,.21))
        for f in ((.83,.72) if kind=="polo" else (.74,.55,.36,.17)):
            cs._add_button(a,"ch4 raised button",(c.x,y-.025,lo.z+e.z*f),.015,button)
        if kind in ("jacket","formal","flannel","pajama"):
            for sign in ((-1,1) if kind=="jacket" else (-1,)):
                px=c.x+sign*e.x*.26
                box("patch pocket",px,c.z+e.z*.08,e.x*.23,e.z*.19,top)
                box("pocket stitched welt",px,c.z+e.z*.17,e.x*.23,.022,accent)
    else:
        cs._add_tee_collar(a,accent)

def build_character(name,role="lead",hair="default",outfit="default"):
    if outfit=="default":
        a=clothed_character(name,role)
    else:
        if outfit not in WARDROBE[role]:raise ValueError("Incompatible outfit "+role+"/"+outfit)
        kind,rgb,pkind,prgb=WARDROBE[role][outfit]
        cfg=cs.ROLE_CLOTHES[role];cut=cfg["sleeve_cutoff"]
        a=R6Character(name,role) if role.startswith("patron_") else character(name,role)
        if role.startswith("patron_"):a.variant_garment=apply_garments(a,cfg["shirt"],cfg["pants"])
        # Remove only legacy outfit-specific accessories on this new candidate.
        if role=="teacher":cs._remove_old_teacher_cardigan_details(a)
        if role=="lead":remove_accessories(a,("signature red star",))
        original_vertices=len(a.body.data.vertices);bones=tuple(b.name for b in a.armature.data.bones)
        seed=sum(ord(ch) for ch in role+outfit)
        for token,col,style,skin in (("shirt",rgb,kind,None),("pants",prgb,pkind,None),
                                    ("sleeve",rgb,kind,srgb(SKINS[SKIN_KEY[role]]))):
            m=cs._material(a," / "+token)
            replace_image(m,atlas(col,style,seed,skin,cut))
            cs._add_fabric_shader(m,PROFILE[style])
            if skin is not None:cs._mask_sleeve_bump(m,cut)
        top=fabric(a,"top",rgb,kind);accent=fabric(a,"trim",rgb,kind,.72)
        pant=fabric(a,"trouser",prgb,pkind)
        cs._cover_shoulder_caps(a,top)
        cs._make_shell(a,"shirt and sleeves",(cs.TORSO_GROUP,)+cs.ARM_GROUPS,arm_cutoff=cut)
        cs._make_shell(a,"trousers",cs.LEG_GROUPS)
        cs._add_cuffs(a,accent,cut)
        if pkind=="jeans":cs._add_denim_pockets(a,pant)
        torso_details(a,kind,top,accent)
        if len(a.body.data.vertices)!=original_vertices or tuple(b.name for b in a.armature.data.bones)!=bones:
            raise RuntimeError("Rig changed")
        a.clothing_upgraded=True
        a.clothing_report={"role":role,"outfit":outfit,"top":kind,"pants":pkind,
            "sleeve_cutoff_fraction_from_wrist":cut,"shells":2,"body_vertices":original_vertices,"bones":len(bones)}
    apply_hair(a,hair)
    a.chapter4_outfit=outfit
    return a
