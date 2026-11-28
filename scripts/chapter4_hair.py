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
    peak=.68 if crop else .77
    # Irregular fitted squircle, front edge high enough for eyes/glasses.
    N=64;vs=[];fs=[];uv=[]
    for j,(rx,ry,z) in enumerate(((.627,.627,.19 if long else .34),(.65,.65,.52),(.55,.54,peak-.06),(.24,.26,peak))):
        for i in range(N):
            a=math.tau*i/N;co,si=math.cos(a),math.sin(a)
            front=max(0,-si)**4
            dz=(.20 if long else .10)*front if j==0 else 0
            zz=z+dz+.012*math.sin(5*a+.4)+.006*math.cos(11*a)
            vs.append((rx*math.copysign(abs(co)**.58,co),ry*math.copysign(abs(si)**.58,si),zz))
            uv.append((i/N,j/3))
    for j in range(3):
        for i in range(N):
            a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
    fs.append(tuple(range(3*N,4*N)))
    mesh("cap",vs,fs,uv,mats[1])
    batches=[([],[],[]) for _ in mats]
    def lock(start,mid,end,width,depth,tone,curl=0):
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
            taper=max(.035,(1-t)**.62)
            for k in range(sides):
                q=math.tau*k/sides
                vs.append(tuple(p+taper*(width*math.cos(q)*a+depth*math.sin(q)*b)))
                uv.append((k/sides,t))
        for j in range(steps-1):
            for k in range(sides):
                a=base+j*sides+k;b=base+j*sides+(k+1)%sides
                fs.append((a,b,b+sides,a+sides))
        fs.append(tuple(base+(steps-1)*sides+k for k in range(sides)))
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
    if style in ("swept_bun","low_bun","low_ponytail"):
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
