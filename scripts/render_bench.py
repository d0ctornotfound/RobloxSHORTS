#!/usr/bin/env python3
"""The Bench: isolated story driver, original repo primitives and locked character APIs.
Candidate production, not approval. Each shot is a separate Blender process.
"""
import argparse,json,math,os,sys,time,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from PIL import Image
import numpy as np
from render_demo import cube,empty,material,point_at,area_light
from quality_cafe import sphere
from stage_a_cafe import cylinder
from library_props import palette,build
from library_character import clothed_character,character
from library_atmosphere import Atmosphere
from library_camera import create,project
from library_locomotion import StrideLock
from r6_imported_cycles import Retarget
from character_motion_correction import apply_corrected
from chapter1_articulation import Articulation
from chapter1_round2 import neutral_feet,seat_setup,pose as sit_pose
from chapter1_round3 import pose as reach_pose
from clothing_articulation import ArticulatedClothes,clearance_metrics
from facial_expressions import enable_blinking
from r6_character import mesh_points,bounds

ROOT=Path(__file__).resolve().parents[1]
FPS=24
def V(p):return Vector(p)
def ease(t):t=max(0,min(1,t));return t*t*(3-2*t)
def all_mesh(root):
    return [o for o in root.children_recursive if o.type=="MESH"]
def hide(root,value):
    for o in [root]+list(root.children_recursive):o.hide_render=value
def ell(name,loc,dim,mat,parent=None):
    ob=sphere(name,loc,dim,mat)
    if parent:ob.parent=parent;ob.location=loc
    return ob
def paper(name,p):
    r=empty(name,(0,0,0));m=p["paper"]
    cube(name+" folded paper", (0,0,-.155),(.24,.15,.32),m,r,bevel=.014)
    cube(name+" folded mouth",(0,0,.012),(.235,.16,.048),p["paper_fold"],r,bevel=.009)
    for x in [-.105,.105]:
        cube(name+" gusset",(x,0,-.15),(.013,.15,.28),p["paper_fold"],r,bevel=.004)
    return r
def flatcap(p):
    r=empty("Old man's flat cap",(0,0,0))
    ell("Wool crown",(0,.02,.075),(.61,.49,.19),p["cap"],r)
    ell("Short front visor",(0,-.20,.027),(.53,.26,.065),p["cap_dark"],r)
    return r
def pigeon(name,p):
    r=empty(name,(0,0,0))
    ell(name+" body",(0,.015,.17),(.20,.32,.23),p["bird"],r)
    for x in [-.081,.081]:
        ell(name+" folded wing",(x,.05,.18),(.07,.29,.13),p["bird_dark"],r)
        for y in [-.015,.045]:
            cube(name+" wing bar",(x,y,.20),(.071,.027,.085),p["bird_bar"],r,bevel=.008)
    ell(name+" neck",(0,-.105,.255),(.12,.13,.17),p["bird_neck"],r)
    head=empty(name+" head pivot",(0,-.115,.29),r)
    ell(name+" head",(0,-.012,.025),(.13,.14,.13),p["bird_dark"],head)
    beak=ell(name+" beak",(0,-.088,.015),(.047,.078,.039),p["beak"],head)
    for x in [-.055,.055]:ell(name+" eye",(x,-.028,.035),(.025,.025,.025),p["eye"],head)
    for x in [-.039,.039]:
        cube(name+" leg",(x,.0,.052),(.021,.021,.104),p["foot"],r,bevel=.003)
        cube(name+" toes",(x,-.025,.012),(.055,.077,.018),p["foot"],r,bevel=.004)
    tail=ell(name+" tail",(0,.168,.145),(.13,.17,.065),p["bird_dark"],r)
    return r,head
def cane(p):
    r=empty("Old man's cane",(0,0,0))
    cylinder("Cane shaft",(0,0,-.49),.028,.98,p["cane"],r)
    cube("Cane grip",(0,-.065,.025),(.09,.20,.065),p["cane"],r,bevel=.027)
    cylinder("Cane rubber tip",(0,0,-.99),.035,.065,p["bird_bar"],r)
    return r
def park(top,p):
    cube("Park lawn",(0,3,-.16),(32,30,.25),p["grass"],bevel=0)
    cube("Wide gravel walking path",(0,-1.7,-.035),(30,4.9,.07),p["path"],bevel=0)
    for x in range(-14,15,2):
        cube("Path border stone",(x, .77,.045),(1.95,.20,.12),p["stone"],bevel=.018)
    r=empty("Same wooden bench",(0,0,0))
    for i in range(5):
        cube("Oak seat slat",(0,.05+i*.145,top-.042),(3.45,.134,.084),p["wood"],r,bevel=.018)
    for i in range(4):
        cube("Oak backrest slat",(0,.79,top+.23+i*.15),(3.45,.10,.135),p["wood"],r,bevel=.018)
    for x in [-1.48,1.48]:
        cube("Bench iron leg",(x,.30,top/2),(.10,.62,top),p["iron"],r,bevel=.022)
        cube("Bench iron back support",(x,.80,top+.35),(.095,.10,.82),p["iron"],r,bevel=.015)
        cube("Bench armrest",(x,.30,top+.29),(.14,.66,.065),p["iron"],r,bevel=.026)
    for x,y,s in [(-4.4,3.1,1.55),(3.9,3.4,1.7),(-8,4.4,1.9),(8,5,1.8),(-1.1,8.4,1.5),(6.5,10,1.6),(-6,10,1.6)]:
        build("tree",pos=(x,y,0),scale=s,p=p)
    for x in [-6.2,6.5]:build("lamp",pos=(x,1.2,0),scale=1.25,p=p)
    for x in range(-12,13):
        cube("Park fence picket",(x*.8,9,.57),(.10,.11,1.14),p["iron"],bevel=.012)
    for z in [.37,.89]:cube("Park fence rail",(0,9,z),(20,.09,.09),p["iron"],bevel=.01)
    rng=random.Random(18)
    for i in range(55):
        x=rng.uniform(-11,11);y=rng.uniform(1.15,7.9)
        if abs(x)<1.9 and y<1.5:continue
        ell("Low clover patch",(x,y,.025),(.20,.15,.065),p["leaf"])
    return r

class Actor:
    def __init__(self,name,role,mode,position,yaw=0,rate=.6):
        before=set(bpy.data.objects)
        self.a=clothed_character(name,role);self.mode=mode;self.pos=V(position);self.yaw=yaw
        self.art=self.clothes=self.feet=self.seat=self.lock=None
        if mode in ("sit","sit_down","reach"):
            self.art=Articulation(self.a,legs=True,arms=mode!="reach")
            self.clothes=ArticulatedClothes(self.a,self.art)
            self.feet=neutral_feet(self.a,self.art,yaw)
            if mode!="reach":self.seat=seat_setup(self.a,self.art,yaw,self.feet)
        elif mode=="walk":
            self.lock=StrideLock(Retarget(self.a),"walk_cycle",fps=FPS,rate=rate,start=self.pos,yaw=yaw)
        self.objects=set(bpy.data.objects)-before
    def update(self,u,t,expr,head=None):
        if self.lock:self.lock.step(t)
        elif self.art:
            if self.mode=="reach":reach_pose(self.a,self.art,"reach",u,t,self.yaw,self.feet,None,None)
            else:sit_pose(self.a,self.art,"sit",u if self.mode=="sit_down" else 1,t,self.yaw,self.feet,None,self.seat)
            self.art.shift(self.pos);self.clothes.sync()
        else:apply_corrected(self.a,"idle",u,t,tuple(self.pos),self.yaw)
        if head is not None:self.a.set_bone("head",head)
        self.a.pose(expr)
    def hand(self,i):
        if self.art and self.art.arms:
            limb=self.art.arms[i];return limb.lower.matrix_world@V((0,0,-limb.b))
        return self.a.grips[i].matrix_world.translation.copy()
    def aim(self,i,target):
        if self.art and self.art.arms:
            pole=self.art.rot(self.yaw)@V(((-1,1)[i],-.13,-.45))
            end=self.art.arm_target(i,V(target),pole,self.yaw);self.clothes.sync()
        else:
            bone=self.a.arms[i];shoulder=(self.a.armature.matrix_world@bone.matrix).translation
            delta=self.a.root.matrix_world.to_3x3().inverted()@(V(target)-shoulder)
            self.a.aim_arm(i,delta);end=self.hand(i)
        return (end-V(target)).length
    def meshes(self):
        return [o for o in self.objects if o.type=="MESH" and o.name in bpy.data.objects and not o.hide_render]

def calibrate():
    before=set(bpy.data.objects)
    a=character("seat fixture calibration","dad")
    art=Articulation(a,legs=True,arms=True)
    feet=neutral_feet(a,art,0)
    top,c,wh=seat_setup(a,art,0,feet)
    from facial_expressions import disable_blinking
    disable_blinking(bpy.context.scene,a)
    for ob in set(bpy.data.objects)-before:bpy.data.objects.remove(ob,do_unlink=True)
    return float(top),float(c.y)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shot",type=int,required=True);ap.add_argument("--output",required=True);ap.add_argument("--mode",choices=["preflight","render"],default="preflight")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:]);n=args.shot
    story=json.loads((ROOT/"stories/the_bench_plan.json").read_text());shot=story["shots"][n-1]
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine="BLENDER_EEVEE";scene.render.resolution_x=540;scene.render.resolution_y=960;scene.render.resolution_percentage=100
    scene.render.fps=FPS;scene.frame_start=1;scene.frame_end=2880;scene.eevee.taa_render_samples=32
    if hasattr(scene.eevee,"use_gtao"):scene.eevee.use_gtao=True;scene.eevee.gtao_distance=.35
    scene.render.image_settings.file_format="PNG";scene.render.image_settings.color_mode="RGB";scene.render.film_transparent=False
    scene.world.use_nodes=True;scene.view_settings.view_transform="AgX"
    p=palette()
    for k,c in {"grass":(.16,.31,.12),"path":(.50,.44,.34),"stone":(.55,.52,.43),"iron":(.13,.19,.16),"paper":(.48,.26,.105),"paper_fold":(.32,.16,.06),"cap":(.24,.20,.15),"cap_dark":(.16,.13,.10),"bird":(.35,.40,.45),"bird_dark":(.19,.24,.31),"bird_bar":(.13,.16,.19),"bird_neck":(.19,.35,.32),"beak":(.50,.45,.34),"eye":(.08,.045,.02),"foot":(.64,.27,.20),"cane":(.23,.10,.038),"crumb":(.73,.55,.31)}.items():p[k]=material(k,c)
    top,cy=calibrate();bench=park(top,p)
    # Bench slats sit beneath the measured rear-hip support, not an arbitrary chair height.
    bench.location.y=cy-.36
    atmosphere=Atmosphere(scene,target=(0,0,1.2));atmosphere.apply(shot["atmosphere"])
    area_light("Gentle story bounce",(4,-3,4),120,5,(1,.88,.76))
    camera=create(scene,"The Bench camera",42)
    bags=[paper("Brown paper bag "+str(i+1),p) for i in range(2)]
    cap=flatcap(p);stick=cane(p)
    birds=[pigeon("Pigeon %02d"%i,p) for i in range(6)]
    rng=random.Random(201)
    crumbs=[ell("Bread crumb %02d"%i,(0,0,0),(.025,.020,.018),p["crumb"]) for i in range(20)]
    actors={};milo_seated=n in (18,19,20,21,22,23,24,35,36,37,38,39,41,42,45,46,47,48)
    dad_seated=n in tuple(range(1,25))+(45,46,47,48)
    show_m=n not in (3,4,5,6,8,12,15,16,27,28,29,37,40,41,43,44,47)
    show_d=(n<=24 and n not in (7,9,10,11,12,14,17)) or n>=43
    if n==26:show_m=False
    if n==33:show_m=False
    if show_m:
        mode="walk" if n in (1,2,9,17,25) else "reach" if n==31 else "sit_down" if n==35 else "sit" if milo_seated else "idle"
        pos=(-3.2,-1.55,0) if mode=="walk" else (-.83,0,0) if milo_seated else (-.65,-.9,0)
        actors["Milo"]=Actor("Milo","lead",mode,pos,math.pi/2 if mode=="walk" else .12 if milo_seated else .25)
    if show_d:
        mode="walk" if n in (43,44) else "sit_down" if n==45 else "sit" if dad_seated else "idle"
        pos=(3.1,-.75,0) if mode=="walk" else (.83,0,0)
        actors["Dad"]=Actor("Dad","dad",mode,pos,-math.pi/2 if mode=="walk" else -.12,.33 if mode=="walk" else .6)
    # Global timeline means per-shot processes retain the same blink schedule.
    for name,a in actors.items():enable_blinking(scene,a.a,seed=23 if name=="Milo" else 71)
    num=round((shot["end"]-shot["start"])*FPS);first=round(shot["start"]*FPS)+1
    selected=set(range(num)) if args.mode=="render" else {0,num//2,num-1}
    records=[];started=time.monotonic()
    for f in range(num):
        global_frame=first+f;scene.frame_set(global_frame)
        u=f/(num-1);t=f/FPS
        m=actors.get("Milo");d=actors.get("Dad")
        if m:
            expr="neutral" if n<=12 else "worried" if n in (13,14,25,30,31,32,34) else "sad" if 35<=n<=40 else "surprised" if n==42 else "happy"
            pitch=.20 if n in (30,31,32,34,38) else -.10 if n in (39,42) else .02
            m.update(u,t,expr,(pitch,0,-.25 if n in (7,13,20,24,39,42,45,48) else 0))
        if d:
            expr="tired" if n<=15 or n in (43,44,45) else "happy"
            pitch=.27 if n<=14 else .27*(1-ease(u)) if n==15 else .16*math.sin(math.pi*2*u) if n==16 else .10 if n in (43,44) else -.02
            d.update(u,t,expr,(pitch,0,.20 if n in (15,16,20,21,45,48) else 0))
        # Prop roots are positioned at actual evaluated hand endpoints or measured supports.
        for ob in bags+[cap,stick]:hide(ob,True)
        cap.location=(.83,cy,top+.01);cap.rotation_euler=(0,0,0)
        for i,(bird,head) in enumerate(birds):
            bird.location=(-1.8+i*.56,-1.20-.34*(i%3),0)
            bird.rotation_euler.z=.5*math.sin(i*2)+.15*math.sin(t+i)
            head.rotation_euler.x=.22+.66*max(0,math.sin(t*5+i))
        for i,c in enumerate(crumbs):
            c.location=(-.4+.13*(i%5),-1.22-.13*(i//5),.015)
            c.hide_render=n in (26,27,29,40,41)
        if n in range(25,41) or n>=45:
            hide(cap,False)
        if n<=24 and d:
            hide(cap,False)
            _,hi=bounds(mesh_points(d.a.head))
            cap.location=(hi.x-.27,d.a.head.matrix_world.translation.y,hi.z-.025)
            cap.rotation_euler.z=d.yaw
        if n in (36,38,39,41,42):cap.location=(.65,cy,top+.01)
        if n==31 and m:
            if u>.43:cap.location=m.hand(0)
        if n==32 and m:cap.location=m.hand(0)
        if n>=46 and d:
            lo,hi=bounds(mesh_points(d.a.head));cap.location=((lo.x+hi.x)/2,(lo.y+hi.y)/2,hi.z+.015)
            cap.rotation_euler.z=d.yaw
        if d and n<=24:
            hide(bags[0],False);bags[0].location=d.hand(1);bags[0].rotation_euler=(0,0,0)
        if m and (9<=n<=24 or 35<=n<=39 or n>=45):
            hide(bags[1],False);bags[1].location=m.hand(0);bags[1].rotation_euler=(0,0,0)
        contacts=[]
        if n in (6,21,22,23,38):
            who=d if n in (6,21) else m
            if who:
                hand=who.hand(0);goal=hand+V((0,-.18,.12))
                contacts.append({"event":"offer_hand","target_error":who.aim(0,goal)})
                hand=who.hand(0)
                if n in (22,23):
                    bird,head=birds[0];a=ease(u) if n==23 else 0
                    bird.location=V((-1.35,-1.45,0)).lerp(hand+V((0,-.03,.015)),a)
                    if n==23:bird.location.z+=.24*math.sin(math.pi*a)
                    head.rotation_euler.x=.55+.35*math.sin(t*8)
                else:
                    for i,c in enumerate(crumbs[:7]):
                        a=(u+i*.12)%1;c.location=hand.lerp(V((hand.x+(i-3)*.07,hand.y-.3,.015)),a)
        if n==12:
            for i,c in enumerate(crumbs):
                a=(u+i*.04)%1;c.location=(-.7+(i%5)*.035,-1.1-(i//5)*.055,.015+1.1*(1-a*a))
        if n in (43,44) and d:
            hide(stick,False);hand=d.hand(0);stick.location=(hand.x,hand.y-.12,max(.99,hand.z));stick.rotation_euler=(0,.08*math.sin(t*2),0)
        if n in (45,48) and m and d:
            # Contact choreography is story-specific, not a modification to the locked motion functions.
            mh,dh=m.hand(1),d.hand(0)
            target=(mh+dh)/2+V((0,-.13,.16))
            weight=ease(u if n==48 else max(0,(u-.55)/.45))
            if weight>.01:
                m.aim(1,mh.lerp(target,weight));d.aim(0,dh.lerp(target,weight))
            mh,dh=m.hand(1),d.hand(0)
            prop=cap if n==45 else bags[1];hide(prop,False)
            prop.location=mh.lerp(dh,ease((u-.72)/.18)) if n==45 else dh.lerp(mh,ease((u-.42)/.18))
            contacts.append({"event":"cap" if n==45 else "bag","socket_separation":(mh-dh).length,"handoff":.72<=u<=.90 if n==45 else .42<=u<=.60})
        if n in (47,48) and d:
            for i,bag in enumerate(bags):
                hide(bag,False)
                if n==47:bag.location=d.hand(i)+V((0,-.10,.12*ease(u)))
                elif i==0:bag.location=d.hand(1)
        bpy.context.view_layer.update()
        if f not in selected:continue
        # Explicit shot-specific subject and prop framing; measured bounds are logged, not assumed.
        actor_target=d if n in (3,8,15,16,43,44,46,47) else m or d
        kind=shot["camera"];target=V((0,-.1,1.05));dist=5.8;lens=42;angle=.10 if n%2 else -.13
        if actor_target:
            lo,hi=bounds(v for ob in actor_target.meshes() for v in mesh_points(ob));center=(lo+hi)/2
            target=center;target.z=1.05 if actor_target.mode=="walk" else center.z+.12
            if kind=="medium":dist=4.2;lens=48
            if kind=="close":target=(lo+hi)/2;target.z=hi.z-.28;dist=2.1;lens=52
        if n in (13,18,20,45,48):target=V((0,.04,1.08));dist=5.4;lens=39;angle=-.08
        if kind=="wide":dist=7.1;lens=36;target=V((0,-.35,1.02));angle=.16
        if kind=="insert":
            obj=bags[0] if n in (4,19,47) else bags[1] if n==10 else cap if n in (29,32,36) else stick if n==44 else birds[0][0] if n in (5,23,28,37) else None
            target=obj.location.copy() if obj else V((0,-1.15,.25))
            if n==19:target=(bags[0].location+bags[1].location)/2
            if n==27:target=V((.83,cy,top+.13))
            if n==41:target=V((.78,cy,top+.12))
            if n==22 and m:target=m.hand(0)
            target.z+=.10;dist=1.85 if n not in (19,27,41) else 3.4;lens=40;angle=.25
        location=target+V((math.sin(angle)*dist,-math.cos(angle)*dist,.32 if kind!="insert" else .65))
        camera.location=location;camera.data.lens=lens;point_at(camera,target);bpy.context.view_layer.update()
        projection=[]
        for name,a in actors.items():
            verts=[v for ob in a.meshes() for v in mesh_points(ob)]
            if not verts:continue
            b=project(scene,camera,verts);projection.append({"actor":name,"coverage":max(0,min(1,b[3])-max(0,b[2])),"bounds":list(b)})
        row={"global_frame":global_frame,"shot":n,"camera":kind,"projection":projection,"contacts":contacts}
        if args.mode=="preflight":
            row["garments"]={name:clearance_metrics(a.a,a.clothes) for name,a in actors.items()}
        path=out/("frame_%04d.png"%global_frame)
        scene.render.filepath=str(path);clock=time.monotonic()
        print("BENCH_RENDER_START",n,global_frame,flush=True);bpy.ops.render.render(write_still=True)
        pixels=np.asarray(Image.open(path).convert("RGB"));row["near_black_percent"]=100*float(np.mean(np.max(pixels,axis=2)<=24));row["render_seconds"]=time.monotonic()-clock
        records.append(row);(out/"partial.json").write_text(json.dumps(records,indent=2))
        print("BENCH_RENDER_DONE",json.dumps(row),flush=True)
    manifest={"shot":shot,"frames":len(records),"mode":args.mode,"resolution":[540,960],"fps":24,"engine":"EEVEE","denoising":False,"samples":32,"elapsed":time.monotonic()-started,"records":records,"review":"candidate; visual and contact verification required"}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    assert len(records)==len(selected)
    # The full film's stricter encoded darkness gate is run after editing.
    assert max(r["near_black_percent"] for r in records)<= (10 if args.mode=="preflight" else 2),"Darkness gate; partial images retained"
    if args.mode=="preflight":assert all(g["pass_tracking"] for r in records for g in r.get("garments",{}).values()),"Garment tracking gate"
if __name__=="__main__":main()
