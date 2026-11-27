"""Original, deterministic R6 variant artwork. No external images or AI API.
Produces 1024px RGBA facial decals and RGB garment-panel atlases."""
from pathlib import Path
import argparse,math,random
from PIL import Image,ImageDraw,ImageFilter
import numpy as np

EXPRESSIONS=("neutral","happy","smug","tired","worried","laughing","shocked","sad","unimpressed")
SKINS={"honey":(.83,.54,.27),"warm_tan":(.60,.32,.13),"peach":(.93,.66,.39),"dad_tan":(.68,.40,.19)}
def srgb(c):return tuple(round(255*(12.92*x if x<=.0031308 else 1.055*x**(1/2.4)-.055)) for x in c)

def face(expr,identity="young"):
    S=2048;im=Image.new("RGBA",(S,S));d=ImageDraw.Draw(im)
    dark=(31,23,21,255);brow=(43,30,23,255)
    def xy(p):return tuple(round(x*S) for x in p)
    def oval(x,y,w,h,color):d.ellipse(xy((x-w/2,y-h/2,x+w/2,y+h/2)),fill=color)
    def poly(p,c):d.polygon([xy(q) for q in p],fill=c)
    def curve(a,b,c,width,color=dark):
        pts=[xy(((1-t)**2*a[0]+2*t*(1-t)*b[0]+t*t*c[0],(1-t)**2*a[1]+2*t*(1-t)*b[1]+t*t*c[1])) for t in [i/64 for i in range(65)]]
        d.line(pts,fill=color,width=round(width*S),joint="curve")
        for x,y in (a,c):oval(x,y,width,width,color)
    # Soft transparent warm shading, never opaque skin-colored rectangles.
    shading=Image.new("RGBA",(S,S));sd=ImageDraw.Draw(shading)
    for x in (.34,.66):sd.ellipse(xy((x-.105,.42,x+.105,.53)),fill=(103,58,39,24 if identity=="dad" else 13))
    sd.ellipse(xy((.45,.43,.55,.62)),fill=(113,63,34,33))
    sd.ellipse(xy((.34,.67,.67,.79)),fill=(119,66,43,18))
    im=Image.alpha_composite(shading.filter(ImageFilter.GaussianBlur(32)),im);d=ImageDraw.Draw(im)
    for i,x in enumerate((.34,.66)):
        sign=-1 if i==0 else 1
        ey=.385
        if expr=="laughing":curve((x-.08,ey),(x,ey-.12),(x+.08,ey),.032)
        elif expr=="smug":
            oval(x+.025,ey,.066,.088,dark);curve((x-.073,ey-.039),(x,ey-.06),(x+.068,ey-.036),.026)
        elif expr in ("tired","unimpressed"):
            oval(x+(.025 if expr=="tired" else 0),ey,.060,.10,dark)
            curve((x-.083,ey-.042),(x,ey-.036),(x+.083,ey-.043),.025)
            if expr=="tired":curve((x-.06,ey+.085),(x,ey+.113),(x+.06,ey+.085),.011,(100,60,41,100))
        else:
            oval(x,ey,.075,.145 if expr=="shocked" else .104,dark)
            if expr=="shocked":oval(x-.012,ey-.025,.017,.027,(255,255,255,220))
        # Mature brows are broad and angular, younger ones more tapered.
        if expr in ("worried","sad"):
            inner=.264;outer=.325
            pts=[(x-.087,outer if i==0 else inner),(x+.087,inner if i==0 else outer)]
        elif expr=="smug":pts=[(x-.09,.285+.015*i),(x+.086,.263+.035*i)]
        elif expr=="shocked":pts=[(x-.084,.247),(x+.084,.247)]
        else:pts=[(x-.084,.281),(x+.084,.281+.012*sign)]
        a,b=pts;th=.037 if identity=="dad" else .026
        poly([a,(a[0]+.02,a[1]-th/2),(b[0]-.014,b[1]-th/2),b,(b[0]-.005,b[1]+th/2),(a[0]+.01,a[1]+th/2)],brow)
    curve((.475,.51),(.465,.565),(.522,.572),.012,(102,57,33,110))
    if expr in ("smug","happy","laughing"):
        if expr=="smug":a=(.28,.651);b=(.74,.574);top=[a,(.46,.649),(.60,.626),b];bottom=[(.69,.682),(.55,.727),(.40,.721)]
        elif expr=="laughing":a=(.29,.582);b=(.71,.582);top=[a,b];bottom=[(.67,.765),(.50,.805),(.33,.765)]
        else:a=(.27,.595);b=(.73,.595);top=[a,(.50,.644),b];bottom=[(.65,.722),(.50,.748),(.35,.722)]
        poly(top+bottom,dark)
        if expr=="smug":poly([(.314,.661),(.46,.660),(.61,.637),(.711,.601),(.669,.656),(.55,.691),(.43,.691)],(250,245,225,255))
        else:poly([(.31,.612),(.50,.654),(.69,.612),(.65,.666),(.50,.691),(.35,.666)],(250,245,225,255))
        if expr=="laughing":oval(.5,.748,.16,.063,(156,63,61,255))
    elif expr=="shocked":oval(.5,.685,.195,.215,dark);oval(.5,.735,.12,.045,(149,70,60,255))
    elif expr in ("worried","sad"):curve((.31,.735),(.5,.51 if expr=="sad" else .57),(.70,.735),.027)
    elif expr=="tired":curve((.34,.69),(.49,.64),(.66,.69),.024)
    else:curve((.35,.66),(.5,.66 if expr=="unimpressed" else .705),(.65,.66),.026)
    return im.resize((1024,1024),Image.Resampling.LANCZOS)

def facial_hair(kind):
    S=2048;im=Image.new("RGBA",(S,S));d=ImageDraw.Draw(im);r=random.Random(238)
    def ellipse(x,y,w,h,c):d.ellipse(tuple(round(v*S) for v in (x-w/2,y-h/2,x+w/2,y+h/2)),fill=c)
    if kind=="beard":
        d.polygon([(round(x*S),round(y*S)) for x,y in [(.19,.53),(.30,.61),(.35,.76),(.5,.81),(.65,.76),(.70,.61),(.81,.53),(.78,.82),(.64,.92),(.36,.92),(.22,.82)]],fill=(49,32,23,184))
    for i in range(2300 if kind=="beard" else 2100):
        x=r.uniform(.18,.82);y=r.uniform(.54,.90)
        # Moustache, chin and jaw, excluding the expression's mouth.
        moustache=((x-.5)/.23)**2+((y-.585)/.075)**2<1 and abs(x-.5)>.025
        jaw=((x-.5)/.31)**2+((y-.69)/.24)**2<1 and (y>.765 or abs(x-.5)>.205)
        if moustache or jaw:
            a=r.randint(115,235) if kind=="stubble" else r.randint(115,225)
            w=r.uniform(.003,.0105);ellipse(x,y,w,w*r.uniform(1.1,2.8),(38,27,21,a))
    return im.resize((1024,1024),Image.Resampling.LANCZOS)

# Garment atlas: top-left front, top-right back, bottom-left sides, bottom-right caps.
COLORS={"hoodie":(104,111,116),"jacket":(176,142,95),"tee":(216,190,138),"cardigan":(161,49,87),"jeans":(34,39,46),"yellow_denim":(224,165,10),"stripe_pants":(25,28,33),"blue_denim":(25,64,128)}
def cloth(kind,skin=None):
    S=512;atlas=Image.new("RGB",(1024,1024))
    base=COLORS[kind.split("_sleeve")[0]]
    rng=np.random.default_rng(17)
    y,x=np.mgrid[:S,:S]/S
    for panel in range(4):
        # Fine textile grain plus broader tonal fold shading; use panel-local UVs.
        g=rng.normal(0,2.6,(S,S))+2.0*np.sin(x*S*math.pi/2)+1.2*np.cos(y*S*math.pi/2)
        # Asymmetric creases instead of regular inflated waves; diffuse cloth.
        folds=3*np.sin(13*x+3*y)+2*np.sin(18*y+4*x)
        for a,b,c,amp,spread in ((.13,.23,.13,-11,.045),(.85,.70,-.13,-15,.065),(.35,.52,.16,8,.12),(.48,.83,-.22,-9,.055),(.70,.14,.14,8,.07)):
            center=a+c*(y-b)
            folds+=amp*np.exp(-((x-center)/spread)**2-((y-b)/.19)**2)
        if kind in ("jeans","blue_denim","yellow_denim"):
            folds+=20*np.exp(-((x-.53)/.26)**2)*np.exp(-((y-.45)/.42)**2)
            g+=4*np.sin((x+y*.5)*S*math.pi*.74)+rng.normal(0,2.1,(S,S))
        arr=np.clip(np.array(base)[None,None,:]+(g+folds)[...,None],0,255).astype("uint8")
        im=Image.fromarray(arr);d=ImageDraw.Draw(im)
        dark=tuple(max(0,c-35) for c in base);lit=tuple(min(255,c+27) for c in base);seam=tuple(max(0,c-18) for c in base)
        def q(p):return tuple(round(v*S) for v in p)
        def line(p,c=seam,w=.009):d.line([q(a) for a in p],fill=c,width=max(1,round(w*S)),joint="curve")
        def rect(p,c):d.rectangle(q(p),fill=c)
        def poly(p,c):d.polygon([q(a) for a in p],fill=c)
        def pocket(x0,y0,x1,y1):
            poly([(x0,y0),(x1,y0),(x1,y1-.045),((x0+x1)/2,y1),(x0,y1-.045)],dark)
            poly([(x0+.012,y0+.012),(x1-.012,y0+.012),(x1-.012,y1-.053),((x0+x1)/2,y1-.014),(x0+.012,y1-.053)],base)
            line([(x0+.023,y0+.035),(x1-.023,y0+.035)],lit,.005)
        def stitch(x0,y0,x1,y1,c=lit):
            for i in range(18):
                a=i/18;b=a+.028
                line([(x0+(x1-x0)*a,y0+(y1-y0)*a),(x0+(x1-x0)*b,y0+(y1-y0)*b)],c,.0035)
        # Panel hem and fold creases.
        line([(.025,.92),(.35,.945),(.68,.925),(.975,.94)],dark,.018)
        line([(.025,.903),(.35,.927),(.68,.907),(.975,.92)],lit,.008)
        if "_sleeve" in kind:
            # Last 14% is exposed hand; cuff and seam above it.
            rect((0,.86,1,1),skin or (220,170,115));rect((0,.80,1,.86),dark)
            for a in (.815,.835,.85):line([(0,a),(1,a)],lit,.004)
            line([(.04,.03),(.10,.37),(.08,.76)],dark,.01)
        elif kind=="hoodie":
            if panel==0:
                poly([(0,.02),(.32,0),(.5,.14),(.68,0),(1,.02),(1,.16),(.5,.29),(0,.16)],dark)
                poly([(.03,.025),(.33,.02),(.5,.16),(.67,.02),(.97,.025),(.97,.13),(.5,.235),(.03,.13)],lit)
                for px in (.43,.57):
                    line([(px,.16),(px-.01,.38),(px+.015,.48)],(191,196,197),.012)
                poly([(.28,.61),(.72,.61),(.81,.84),(.19,.84)],dark)
                poly([(.30,.63),(.70,.63),(.78,.82),(.22,.82)],base)
                line([(.29,.65),(.22,.80)],lit,.012);line([(.71,.65),(.78,.80)],lit,.012)
                stitch(.30,.625,.70,.625);stitch(.24,.827,.76,.827)
            elif panel==1:poly([(.12,.02),(.88,.02),(.78,.24),(.5,.37),(.22,.24)],dark)
        elif kind=="jacket":
            if panel==0:
                poly([(.34,0),(.66,0),(.65,1),(.35,1)],(25,26,28))
                for k in (0,1):
                    a=.33 if k==0 else .67
                    line([(a,.04),(a,.98)],dark,.018)
                    poly([(a,.02),(a+(-.12 if k==0 else .12),.02),(a+(-.035 if k==0 else .035),.26)],(224,207,176))
                pocket(.075,.30,.29,.54);pocket(.71,.30,.925,.54)
                for x0,x1 in ((.075,.29),(.71,.925)):
                    rect((x0,.30,x1,.36),dark);rect((x0+.009,.306,x1-.009,.349),base)
                    stitch(x0+.018,.373,x1-.018,.373,lit)
                    d.ellipse(q(((x0+x1)/2-.012,.325,(x0+x1)/2+.012,.349)),fill=(222,209,184))
                stitch(.035,.08,.035,.91);stitch(.965,.08,.965,.91)
                for yy in (.31,.49,.67,.85):d.ellipse(q((.315,yy,.34,yy+.025)),fill=(219,208,183))
            elif panel==1:line([(.12,.2),(.5,.28),(.88,.2)],dark,.014)
        elif kind in ("jeans","yellow_denim","blue_denim","stripe_pants"):
            line([(.06,.02),(.06,.98)],dark,.012);line([(.078,.02),(.078,.98)],lit,.005)
            line([(.94,.02),(.94,.98)],dark,.011)
            stitch(.085,.04,.085,.94);stitch(.922,.04,.922,.94)
            if kind=="stripe_pants":
                if panel in (0,2):line([(.12,.02),(.12,.98)],(225,226,219),.018)
            else:
                if panel==0:line([(.15,.03),(.21,.16),(.43,.19)],lit,.012);line([(.86,.03),(.79,.16),(.56,.19)],lit,.012)
                if panel==1:pocket(.22,.08,.78,.29)
                line([(.22,.48),(.45,.50),(.79,.44)],lit,.008);line([(.23,.52),(.50,.54),(.80,.49)],dark,.009)
        else:
            if panel==0:
                poly([(.30,0),(.70,0),(.60,.17),(.40,.17)],dark)
                if kind=="cardigan":
                    line([(.50,.13),(.50,.94)],dark,.02)
                    for yy in (.26,.42,.58,.74):d.ellipse(q((.49,yy,.52,yy+.026)),fill=lit)
                else:poly([(.32,.31),(.68,.31),(.64,.48),(.37,.48)],dark)
        atlas.paste(im,((panel%2)*S,(panel//2)*S))
    return atlas

def generate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for identity in ("young","dad","teacher","friend"):
        folder=out/identity;folder.mkdir(exist_ok=True)
        for expr in EXPRESSIONS:face(expr,"dad" if identity=="dad" else identity).save(folder/(expr+".png"))
    for kind in ("stubble","beard"):facial_hair(kind).save(out/(kind+".png"))
    for kind in COLORS:cloth(kind).save(out/(kind+".png"))
    for role,skin,kind in [("lead","warm_tan","hoodie"),("friend","peach","tee"),("teacher","honey","cardigan"),("dad","dad_tan","jacket")]:
        cloth(kind+"_sleeve",srgb(SKINS[skin])).save(out/(role+"_sleeve.png"))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default="assets/r6_variants");a=p.parse_args();generate(a.output)
