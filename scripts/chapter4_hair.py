"""Opt-in Chapter 4 hair: identity-preserving defaults and selectable styles.
No changes to the legacy rig, expression, motion or clothing implementations.
"""
import math
import random
import bpy
from mathutils import Vector
from r6_variant_character import accessory_mesh, remove_accessories, fiber_mat

DEFAULTS = dict(lead="spikes", friend="beanie", teacher="swept_bun",
                dad="classic_sweep", librarian="soft_sweep",
                patron_green="short_crop", patron_blue="short_crop")
HAIR = dict(lead=("messy_fringe","side_part"), friend=("curly_crop","quiff"),
            teacher=("low_ponytail","rounded_bob"), dad=("short_crew","side_part"),
            librarian=("low_bun","rounded_bob"), patron_green=("messy_fringe",),
            patron_blue=("curly_crop",))
COLORS = dict(lead=(.019,.010,.006), friend=(.043,.018,.008),
              teacher=(.018,.009,.005), dad=(.009,.008,.007),
              librarian=(.018,.009,.005), patron_green=(.055,.025,.013),
              patron_blue=(.055,.025,.013))

def apply_hair(actor, style="default"):
    role=actor.role
    style=DEFAULTS[role] if style=="default" else style
    if style not in (DEFAULTS[role], *HAIR[role]):
        raise ValueError("Incompatible hairstyle: "+role+"/"+style)
    if style=="beanie":
        return style
    remove_accessories(actor, ("head fitted hair cap","head strand lock","head hair",
        "head fringe","head short block hair","head rounded swept bun","head block bun",
        "head knitted beanie","head beanie","head ch4 hair"))
    rng=random.Random(role+":"+style)
    c=sum(actor.head_bounds,Vector())/2;s=actor.scale
    color=COLORS[role]
    mats=[fiber_mat("Ch4 "+role+" "+style+" tone "+str(i),tuple(v*f for v in color))
          for i,f in enumerate((.72,.85,1,1.13,1.28))]
    def mesh(label,vs,fs,uv,mat):
        return accessory_mesh(actor,"head ch4 hair "+label,[tuple(c+s*Vector(v)) for v in vs],fs,uv,mat)
    long=style=="rounded_bob"
    crop=style in ("short_crop","short_crew","curly_crop")
    corrected = role in ("teacher","dad","librarian") or (role=="patron_green" and style=="messy_fringe") or (role=="patron_blue" and style=="curly_crop")
    peak={"short_crew":.635,"classic_sweep":.80,"side_part":.75,"soft_sweep":.70,
          "rounded_bob":.77,"swept_bun":.75,"curly_crop":.69,"messy_fringe":.74}.get(style,.68 if crop else .77) if corrected else (.68 if crop else .77)
    if long and corrected:
        rings=((.68,.70,.10),(.745,.755,.30),(.74,.75,.48),(.59,.60,.69),(.23,.26,peak))
    elif corrected and style=="short_crew":
        rings=((.621,.621,.42),(.634,.634,.52),(.59,.59,.603),(.27,.30,peak))
    else:
        rings=((.627,.627,.34),(.65,.65,.52),(.55,.54,peak-.06),(.24,.26,peak))
    # Irregular fitted squircle, front edge high enough for eyes/glasses.
    N=64;vs=[];fs=[];uv=[]
    for j,(rx,ry,z) in enumerate(rings):
        for i in range(N):
            a=math.tau*i/N;co,si=math.cos(a),math.sin(a)
            front=max(0,-si)**4
            dz=(.40 if long else .10)*front if j==0 else ((.19*front) if long and j==1 else 0)
            zz=z+dz+.012*math.sin(5*a+.4)+.006*math.cos(11*a)
            if corrected and style=="side_part" and j>=2:zz+=.055*co
            vs.append((rx*math.copysign(abs(co)**.58,co),ry*math.copysign(abs(si)**.58,si),zz))
            uv.append((i/N,j/(len(rings)-1)))
    for j in range(len(rings)-1):
        for i in range(N):
            a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
    fs.append(tuple(range((len(rings)-1)*N,len(rings)*N)))
    mesh("cap",vs,fs,uv,mats[1])
    batches=[([],[],[]) for _ in mats]
    def lock(start,mid,end,width,depth,tone,curl=0,blunt=.035,roll=0):
        start,mid,end=map(Vector,(start,mid,end))
        vs,fs,uv=batches[tone];base=len(vs);steps=11;sides=8
        for j in range(steps):
            t=j/(steps-1)
            p=(1-t)**2*start+2*t*(1-t)*mid+t*t*end
            tang=2*(1-t)*(mid-start)+2*t*(end-mid)
            if tang.length<1e-5:tang=Vector((0,0,1))
            tang.normalize();a=tang.cross(Vector((0,1,0)))
            if a.length<.1:a=tang.cross(Vector((0,0,1)))
            a.normalize();b=tang.cross(a).normalized()
            p+=curl*math.sin(t*math.tau)*a
            taper=max(blunt,(1-t)**.62)
            if roll:
                a,b=math.cos(roll)*a+math.sin(roll)*b,-math.sin(roll)*a+math.cos(roll)*b
            for k in range(sides):
                q=math.tau*k/sides
                vs.append(tuple(p+taper*(width*math.cos(q)*a+depth*math.sin(q)*b)))
                uv.append((k/sides,t))
        for j in range(steps-1):
            for k in range(sides):
                a=base+j*sides+k;b=base+j*sides+(k+1)%sides
                fs.append((a,b,b+sides,a+sides))
        fs.append(tuple(base+(steps-1)*sides+k for k in range(sides)))
        fs.append(tuple(base+k for k in reversed(range(sides))))
    if corrected:
        # Broad overlapping masses determine the silhouette before smaller locks.
        if style=="short_crew":
            for i in range(20):
                x=rng.uniform(-.48,.48);y=rng.uniform(-.46,.46)
                lock((x,y,.59),(x+.035,y+.025,.655),(x+.07,y+.07,.625),
                     rng.uniform(.035,.073),rng.uniform(.018,.032),rng.randrange(1,4),blunt=.26)
        elif style=="curly_crop":
            for i in range(29):
                a=i*2.39996;rad=.49*math.sqrt((i+.5)/29)
                x=rad*math.cos(a);y=rad*math.sin(a);rr=rng.uniform(.07,.17)
                h=rng.uniform(.74,.85);rot=rng.uniform(-math.pi,math.pi);dx,dy=math.cos(rot),math.sin(rot)
                lock((x,y,.62),(x+rr*dx,y+rr*dy,h+.07),(x-rr*.45*dx,y-rr*.45*dy,h-.055),
                     rng.uniform(.065,.13),rng.uniform(.05,.10),rng.randrange(1,5),
                     curl=rng.uniform(.025,.075),blunt=.31,roll=rot)
        elif style=="side_part":
            for sign,count in ((-1,8),(1,14)):
                for i in range(count):
                    y=-.49+1.0*(i+.5)/count+rng.uniform(-.045,.045)
                    x=-.22+sign*rng.uniform(.035,.085)
                    h=.71 if sign<0 else .85
                    lock((x,y,.66),(x+sign*.20,y-.035,h),(x+sign*.42,y+.10,h-.13),
                         rng.uniform(.07,.13),rng.uniform(.045,.075),rng.randrange(1,5),blunt=.16)
        elif style=="messy_fringe":
            for i in range(17):
                x=rng.uniform(-.49,.49);y=rng.uniform(-.34,.43)
                lock((x,y,.59),(x+rng.uniform(-.14,.15),y-.12,rng.uniform(.75,.86)),
                     (x+rng.uniform(-.15,.15),max(-.67,y-.25),rng.uniform(.43,.72)),
                     rng.uniform(.085,.16),rng.uniform(.055,.09),rng.randrange(1,5),blunt=.24)
        else:
            h={"classic_sweep":.91,"soft_sweep":.76,"rounded_bob":.82,"swept_bun":.79}.get(style,.80)
            sign=-1 if style=="classic_sweep" else 1
            for i in range(22):
                x=rng.uniform(-.48,.48);y=rng.uniform(-.46,.46)
                lock((x,y,.58),(x+sign*rng.uniform(.10,.22),y+.025,h+rng.uniform(-.025,.045)),
                     (max(-.64,min(.64,x+sign*.26)),min(.63,y+.20),h-.14),
                     rng.uniform(.075,.145),rng.uniform(.04,.075),rng.randrange(1,5),blunt=.16)
        if style!="short_crew":
            for i in range(26 if long else 19):
                a=math.tau*i/(26 if long else 19)+rng.uniform(-.06,.06);co,si=math.cos(a),math.sin(a)
                x=.60*math.copysign(abs(co)**.60,co);y=.60*math.copysign(abs(si)**.60,si)
                front=si<-.60
                if long and front:continue
                z=(.12 if long else (.43 if front else .34))+rng.uniform(-.025,.035)
                if style=="messy_fringe" and front:z-=rng.uniform(.035,.08)
                reach=1.19 if long else 1.055
                lock((x*.73,y*.73,.68),(x*reach,y*reach,.43 if long else .55),
                     (x*(1.08 if long else 1.025),y*(1.08 if long else 1.025),z),
                     rng.uniform(.095,.15) if long else rng.uniform(.045,.095),
                     rng.uniform(.06,.10) if long else rng.uniform(.035,.065),rng.randrange(1,5),blunt=.34 if long else .20)
    else:
        # Staggered and jittered crown roots; no shared repeating strand trajectory.
        for row in range(5):
            for col in range(10):
                x=-.52+col*.115+rng.uniform(-.041,.041)
                y=-.43+row*.213+rng.uniform(-.065,.065)
                z=.56+rng.uniform(-.028,.045)
                if style in ("spikes","messy_fringe"):
                    h=.91 if style=="spikes" else .82
                    mid=(x+rng.uniform(-.17,.17),y-.12,h+rng.uniform(.02,.15))
                    end=(x+rng.uniform(-.23,.23),y+rng.uniform(-.22,.13),h+rng.uniform(-.06,.13))
                elif style=="curly_crop":
                    mid=(x+.07,y-.05,.78+rng.uniform(0,.10))
                    end=(x-.04,y+.06,.73+rng.uniform(-.02,.06))
                elif style=="quiff":
                    mid=(x+.08,y-.16,.92+rng.uniform(-.05,.13))
                    end=(x+.15,y+.17,.83+rng.uniform(-.04,.07))
                else:
                    d=-1 if style in ("classic_sweep","side_part","short_crew") else 1
                    h=.71 if crop else .83
                    mid=(x+d*rng.uniform(.06,.17),y+.045,h+rng.uniform(-.025,.065))
                    end=(x+d*rng.uniform(.10,.22),y+.14,h-.08+rng.uniform(-.04,.055))
                lock((x,y,z),mid,end,rng.uniform(.059,.099),rng.uniform(.045,.084),rng.randrange(5),.045 if style=="curly_crop" else 0)
        # Distinct edge lengths and flow at the hairline, temples and nape.
        for i in range(40):
            a=math.tau*i/40+rng.uniform(-.045,.045);co,si=math.cos(a),math.sin(a)
            x=.60*math.copysign(abs(co)**.60,co);y=.60*math.copysign(abs(si)**.60,si)
            front=si<-.5
            z=(.39 if front else (.04 if long else .28))+rng.uniform(-.035,.065)
            if style in ("spikes","messy_fringe") and front:z-=rng.uniform(.02,.14)
            lock((x*.72,y*.72,.67),(x*1.08,y*1.08,.54),(x*1.10,y*1.10,z),
                 rng.uniform(.052,.085),rng.uniform(.042,.070),rng.randrange(5))
    if style in ("swept_bun","low_bun"):
        # Filled ellipsoid beneath overlapping irregular coils.
        z=.84 if style=="swept_bun" else .46
        V=[];F=[];U=[];n=40;m=20
        for j in range(m+1):
            t=math.pi*j/m
            for i in range(n):
                a=math.tau*i/n
                V.append((.30*math.sin(t)*math.cos(a),.76+.30*math.cos(t),z+.30*math.sin(t)*math.sin(a)))
                U.append((i/n,j/m))
        for j in range(m):
            for i in range(n):
                k=j*n+i;l=j*n+(i+1)%n;F.append((k,l,l+n,k+n))
        mesh("solid bun core",V,F,U,mats[2])
        for i in range(17):
            a=i*2.39996;rad=.235*math.sqrt((i+.5)/17)
            x=rad*math.cos(a);zz=z+rad*math.sin(a)
            lock((x*.65,.80,zz),(x+.09*math.cos(a+.8),1.06,zz+.09*math.sin(a+.8)),
                 (x*.55,.98,zz*.55+z*.45),rng.uniform(.075,.12),rng.uniform(.055,.095),rng.randrange(1,5),blunt=.27)
    elif style=="low_ponytail":
        z=.84 if style=="swept_bun" else .46
        # Overlapping nonuniform spiral locks over a compact tied silhouette.
        for i in range(32):
            a=math.tau*i/32+rng.uniform(-.07,.07)
            r=.30 if style!="low_ponytail" else .19
            x=r*math.cos(a);zz=z+r*math.sin(a)
            tip=(x*.6,.86,zz*.5+z*.5) if style!="low_ponytail" else (x*.5,.86,.02+rng.uniform(-.20,.15))
            lock((x*.65,.53,zz),(x,.95,zz+rng.uniform(-.05,.05)),tip,
                 rng.uniform(.085,.13),rng.uniform(.075,.12),rng.randrange(5))
    for i,(v,f,u) in enumerate(batches):
        if v:mesh("locks "+str(i),v,f,u,mats[i])
    bpy.context.view_layer.update()
    actor.chapter4_hair=style
    return style
