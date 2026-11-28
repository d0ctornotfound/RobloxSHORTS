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
from chapter1_articulation import Articulation,tree_for_object
from chapter1_round2 import neutral_feet,seat_setup,pose as sit_pose
from chapter1_round3 import pose as reach_pose
from clothing_articulation import ArticulatedClothes,clearance_metrics
from facial_expressions import enable_blinking
from r6_character import mesh_points,bounds
from bench_camera_qa import geometry,prop_geometry,rendered_visibility

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
    ell("Wool crown",(0,.02,.085),(.76,.66,.17),p["cap"],r)
    ell("Short front visor",(0,-.24,.018),(.65,.34,.05),p["cap_dark"],r)
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
            self.art=Articulation(self.a,legs=True,arms=True)
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
    def hand_surface(self,i):
        # The wrist/end socket is not the dorsal skin surface. Raycast down onto the distal hand itself.
        limb=self.art.arms[i]
        center=limb.lower.matrix_world@V((0,0,-limb.b*.88))
        tree=tree_for_object(limb.lower)
        hit=tree.ray_cast(center+V((0,0,1)),V((0,0,-1)),2)
        if hit[0] is None:raise RuntimeError("No distal hand support")
        return hit[0],tree
    def meshes(self):
        return [o for o in self.objects if o.type=="MESH" and o.name in bpy.data.objects and not o.hide_render]

def wear_cap(cap,actor):
    # Story-local wardrobe layering only: the cap covers the crown locks, not the face/fringe.
    # The character rig, hair meshes, material assets and locked clothes remain unmodified on disk.
    for ob in actor.objects:
        if ob.type!="MESH" or "strand lock " not in ob.name:continue
        try:index=int(ob.name.rsplit("strand lock ",1)[1].split(".")[0])
        except ValueError:continue
        if index<24:ob.hide_render=True
    lo,hi=bounds(mesh_points(actor.a.head));c=(lo+hi)/2
    cap.location=(c.x,c.y,hi.z-.045)
    cap.rotation_euler.z=actor.yaw

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

def hero_names(n,kind,actors):
    # Singles deliberately focus on the acting character; another character can
    # remain physically present outside the portrait composition.
    if kind=="insert":return []
    if n==18:return ["Milo"]  # focal single; next shot establishes both bags
    if n==48:return ["Milo","Dad"]  # intentional two-face closing composition
    # Opening narration is about Milo walking to school. Dad is established in shot 03.
    if n==1:return ["Milo"]
    if n in (3,6,8,15,16,21,43,46):return ["Dad"] if "Dad" in actors else []
    return ["Milo"] if "Milo" in actors else list(actors)

def pair_camera(scene,cam,actors):
    # Conservative bound corners propose a fixed two-shot camera; the existing
    # all-frame exact geometry and rendered visibility tests decide acceptance.
    boxes=[];faces=[]
    for name in ("Milo","Dad"):
        actor=actors[name];lo,hi=bounds(v for ob in actor.meshes() for v in mesh_points(ob))
        boxes.append([V((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)])
        flo,fhi=bounds(mesh_points(actor.a.head));faces.append((flo+fhi)/2)
    target=sum(faces,V((0,0,0)))/2;target.z-=.50
    best=None
    for angle in (0,.45,-.45,.65,-.65,.85,-.85,1.0,-1.0,1.15,-1.15):
        for dist in (2.8,3.2,3.6,4.0,4.6,5.2,6.0):
            for lens in (35,42,49,56,63,70):
                for height in (.15,.45,.75):
                    cam.location=target+V((math.sin(angle)*dist,-math.cos(angle)*dist,height));cam.data.lens=lens;point_at(cam,target);bpy.context.view_layer.update()
                    bb=[project(scene,cam,box) for box in boxes];face=[project(scene,cam,[f]) for f in faces]
                    cover=[b[3]-b[2] for b in bb]
                    excess=sum(max(0,.04-b[0])+max(0,b[1]-.96)+max(0,.04-b[2])+max(0,b[3]-.96) for b in bb)
                    shortage=sum(max(0,.45-c) for c in cover);separation=abs(face[0][0]-face[1][0]);overlap=max(0,min(bb[0][1],bb[1][1])-max(bb[0][0],bb[1][0]))
                    cost=30*excess+12*shortage+5*max(0,.20-separation)+1.4*overlap+.25*abs(cover[0]-cover[1])+.02*abs(angle)
                    if min(b[4] for b in bb)<=0:continue
                    if best is None or cost<best[0]:best=(cost,cam.location.copy(),target.copy(),lens)
    if best is None:raise RuntimeError("No pair-camera proposal")
    return best

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shot",type=int,required=True);ap.add_argument("--output",required=True);ap.add_argument("--mode",choices=["preflight","render"],default="preflight")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:]);n=args.shot
    story=json.loads((ROOT/"stories/the_bench_plan.json").read_text());shot=dict(story["shots"][n-1])
    if n==48:shot.update(camera="close",camera_note="Intentional two-person closing portrait; both heads and both bags must remain inside frame. Waist/legs may be cropped.")
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
    area_light("Gentle story bounce",(4,-3,4),220,5,(1,.88,.76))
    area_light("Front facial fill",(-2,-4,3.4),380 if shot["atmosphere"]=="morning" else 240,5,(1,.96,.90))
    if n in (1,2):area_light("Walking trouser shadow fill",(-3,-2.8,1.5),340 if n==1 else 260,3.5,(1,.94,.87))
    if n in (43,44):area_light("Cane and trouser shadow fill",(2.0,-3.2,1.8),520,4.0,(.94,.96,1))
    if n==43:area_light("Returning walk side fill",(-.8,-3.6,1.2),280,3.5,(.94,.96,1))
    if n==46:area_light("Cap donning trouser fill",(1.6,-3.0,1.4),220,3.5,(1,.95,.88))
    camera=create(scene,"The Bench camera",42)
    bags=[paper("Brown paper bag "+str(i+1),p) for i in range(2)]
    cap=flatcap(p);stick=cane(p)
    shadow_centres=[]
    if n==41:
        # Story-only stylized shadow assist: a feathered diagonal attenuation band
        # in the existing bench/cap shaders. No geometry or locked assets changed.
        copies={}
        for ob in all_mesh(bench)+all_mesh(cap):
            if ob.name.startswith("Oak") or ob in all_mesh(cap):
                for slot in ob.material_slots:
                    src=slot.material
                    if not src or not src.use_nodes:continue
                    if src.name not in copies:
                        mat=src.copy();mat.name=src.name+" | returning shadow insert"
                        nd=mat.node_tree.nodes;lk=mat.node_tree.links
                        bs=next((v for v in nd if v.type=="BSDF_PRINCIPLED"),None)
                        if bs is None:continue
                        geo=nd.new("ShaderNodeNewGeometry");sep=nd.new("ShaderNodeSeparateXYZ");lk.new(geo.outputs["Position"],sep.inputs[0])
                        slant=nd.new("ShaderNodeMath");slant.operation="MULTIPLY_ADD";lk.new(sep.outputs["Y"],slant.inputs[0]);slant.inputs[1].default_value=.48;lk.new(sep.outputs["X"],slant.inputs[2])
                        c=nd.new("ShaderNodeValue");c.label="Animated approaching shadow";shadow_centres.append(c.outputs[0])
                        delta=nd.new("ShaderNodeMath");delta.operation="SUBTRACT";lk.new(slant.outputs[0],delta.inputs[0]);lk.new(c.outputs[0],delta.inputs[1])
                        absolute=nd.new("ShaderNodeMath");absolute.operation="ABSOLUTE";lk.new(delta.outputs[0],absolute.inputs[0])
                        ramp=nd.new("ShaderNodeMapRange");ramp.clamp=True;ramp.interpolation_type="SMOOTHERSTEP";lk.new(absolute.outputs[0],ramp.inputs["Value"]);ramp.inputs["From Min"].default_value=.22;ramp.inputs["From Max"].default_value=.65;ramp.inputs["To Min"].default_value=.60;ramp.inputs["To Max"].default_value=0
                        mix=nd.new("ShaderNodeMixRGB");mix.blend_type="MULTIPLY";lk.new(ramp.outputs["Result"],mix.inputs[0]);mix.inputs[2].default_value=(.22,.26,.32,1)
                        bc=bs.inputs["Base Color"]
                        if bc.is_linked:
                            source=bc.links[0].from_socket;lk.remove(bc.links[0]);lk.new(source,mix.inputs[1])
                        else:mix.inputs[1].default_value=bc.default_value
                        lk.new(mix.outputs[0],bc);copies[src.name]=mat
                    slot.material=copies[src.name]
    birds=[pigeon("Pigeon %02d"%i,p) for i in range(6)]
    rng=random.Random(201)
    crumbs=[ell("Bread crumb %02d"%i,(0,0,0),(.025,.020,.018),p["crumb"]) for i in range(20)]
    actors={};milo_seated=n in (18,19,20,21,22,23,24,31,32,35,36,37,38,39,41,42,45,46,47,48)
    dad_seated=n in tuple(range(1,25))+(45,46,47,48)
    show_m=n not in (3,4,5,6,8,12,15,16,27,28,29,37,40,41,43,44,47)
    show_d=(n<=24 and n not in (7,9,10,11,12,14,17)) or n>=43 or n==41
    if n==26:show_m=False
    if n==33:show_m=False
    if show_m:
        mode="walk" if n in (1,2,9,17,25) else "sit_down" if n==35 else "sit" if milo_seated else "idle"
        pos=(-3.6,-1.42,0) if n==2 else (-3.2,-1.55,0) if mode=="walk" else (-.83,0,0) if milo_seated else (-.65,-.9,0)
        # Pickup is staged beside the seat, using the existing reach motion and a separate articulated hand target.
        if n in (31,32):pos=(-.24,0,0)
        yaw=math.pi/2 if mode=="walk" else 0 if n in (31,32) else .12 if milo_seated else .25
        actors["Milo"]=Actor("Milo","lead",mode,pos,yaw,.40 if n==2 else .6)
    if show_d:
        mode="walk" if n in (41,43,44) else "sit_down" if n==45 else "sit" if dad_seated else "idle"
        pos=(4.6,.55,0) if n==41 else (3.1,-.75,0) if mode=="walk" else (.83,0,0)
        actors["Dad"]=Actor("Dad","dad",mode,pos,-math.pi/2 if mode=="walk" else -.12,.19 if n==41 else .33 if mode=="walk" else .6)
    if n==41:
        area_light("Returning actor shadow key",(6,1.25,3.15),620,.48,(.82,.88,1))
        area_light("Bench shadow detail fill",(-1.8,-3.4,2.5),650,4.0,(.96,.96,1))
    # Global timeline means per-shot processes retain the same blink schedule.
    for name,a in actors.items():enable_blinking(scene,a.a,seed=23 if name=="Milo" else 71)
    num=round((shot["end"]-shot["start"])*FPS);first=round(shot["start"]*FPS)+1
    selected=set(range(num)) if args.mode=="render" else {0,num//2,num-1}
    if args.mode=="preflight" and n in (23,31,45,46,47,48):selected.update({num//4,3*num//4})
    if args.mode=="preflight" and n==1:selected.update({35,36,37,38}) # exact failed global frames 36–39
    if args.mode=="preflight" and n==43:selected.update(range(11,19)) # exact at-risk frames 2532–2539
    records=[];geometry_records=[];started=time.monotonic();cap_attached=False;cap_mount=None;cane_length=None;pair_setup=None
    for f in range(num):
        global_frame=first+f;scene.frame_set(global_frame)
        u=f/(num-1);t=f/FPS
        for socket in shadow_centres:socket.default_value=2.85-2.20*ease(u)
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
            # Keep pigeons out of the walking corridor in the corrected shots.
            if n in (1,2,9,17,25):bird.location=(.10+i*.47,-.55-.11*(i%3),0)
            # Reunion: flock disperses beyond the walking and cane corridor.
            if n in (41,43,44):bird.location=(-2.7+i*.48,-2.2-.16*(i%3),0)
            if n in (41,44):hide(bird,True)
            bird.rotation_euler.z=.5*math.sin(i*2)+.15*math.sin(t+i)
            head.rotation_euler.x=.22+.66*max(0,math.sin(t*5+i))
        for i,c in enumerate(crumbs):
            c.location=(-.4+.13*(i%5),-1.22-.13*(i//5),.015)
            c.hide_render=n in (26,27,29,40,41)
        if n in range(25,43) or n>=45:
            hide(cap,False)
        if n<=24 and d:
            hide(cap,False)
            wear_cap(cap,d)
        if n in (36,38,39,41,42):cap.location=(.65,cy,top+.01)
        if n in (31,32) and m:cap.location=(.83,cy,top+.015)
        if n>=47 and d:
            wear_cap(cap,d)
        if d and n<=24:
            hide(bags[0],False);bags[0].location=d.hand(1);bags[0].rotation_euler=(0,0,0)
        if m and (9<=n<=24 or 35<=n<=39):
            hide(bags[1],False);bags[1].location=m.hand(1 if n in (22,23,24) else 0);bags[1].rotation_euler=(0,0,0)
        contacts=[]
        if n==4 and d:
            # Move the actual giving arm forward so the folded bag clears the jacket.
            limb=d.art.arms[1];goal=limb.joint()+V((-.20,-.78,-.40)).normalized()*(limb.a+limb.b)*.79
            error=d.aim(1,goal);bags[0].location=d.hand(1);bags[0].scale=(1.35,1.35,1.35)
            contacts.append({"event":"paper_bag_display","target_error":float(error),"socket_error":(bags[0].location-d.hand(1)).length})
        if n==10 and m:
            # The locked R6 arm is posed toward the camera; the bag remains attached to its hand.
            goal=m.hand(0)+V((.05,-.30,.18));error=m.aim(0,goal);bags[1].location=m.hand(0);bags[1].scale=(1.35,1.35,1.35)
            contacts.append({"event":"paper_bag_display","target_error":float(error),"socket_error":(bags[1].location-m.hand(0)).length})
        if n==19 and m and d:
            # Inner hands bring both bags into the same plane, with a physical gap.
            for actor,index,bag,side in ((m,1,bags[1],1),(d,0,bags[0],-1)):
                limb=actor.art.arms[index];goal=limb.joint()+V((-side*.30,-.88,-.36)).normalized()*(limb.a+limb.b)*.83
                err=actor.aim(index,goal);bag.location=actor.hand(index);bag.scale=(1.25,1.25,1.25)
                contacts.append({"event":"paper_bag_display","target_error":float(err),"socket_error":(bag.location-actor.hand(index)).length})
            bpy.context.view_layer.update()
            a0,a1=bounds(v for ob in bags[0].children_recursive if ob.type=="MESH" for v in mesh_points(ob))
            b0,b1=bounds(v for ob in bags[1].children_recursive if ob.type=="MESH" for v in mesh_points(ob))
            contacts.append({"event":"two_bag_separation","world_x_gap":float(max(a0.x-b1.x,b0.x-a1.x))})
        if n in (31,32) and m:
            # R3 missed the cap by >=.440 units. Use the approved seated pose
            # beside it and the inner arm; measure the actual nearest crown edge.
            # The cap stays on its support until the physical target is reached.
            bpy.context.view_layer.update()
            crown=next(ob for ob in cap.children_recursive if ob.type=="MESH" and "Wool crown" in ob.name)
            points=mesh_points(crown);goal=min(points,key=lambda v:v.x).copy()
            grip_offset=cap.location.copy()-goal
            index=1;limb=m.art.arms[index];shoulder=limb.joint();length=limb.a+limb.b
            carry=shoulder+V((.12,-.66,-.55)).normalized()*length*.71
            if n==32:
                err=m.aim(index,carry);cap.location=m.hand(index)+grip_offset
                contacts.append({"event":"cap_carry","socket_error":(cap.location-m.hand(index)-grip_offset).length,"target_error":float(err)})
            else:
                gap=None;reach_weight=ease((u-.04)/.30)
                if not cap_attached:
                    err=m.aim(index,m.hand(index).lerp(goal,reach_weight));gap=(m.hand(index)-goal).length
                    if .34<=u<=.66 and gap<=.008:cap_attached=True
                if cap_attached:
                    target=goal.lerp(carry,ease((u-.66)/.34))
                    err=m.aim(index,target);cap.location=m.hand(index)+grip_offset
                bpy.context.view_layer.update()
                nearest=tree_for_object(crown).find_nearest(m.hand(index))
                contacts.append({"event":"cap_pickup","attached":cap_attached,"pre_contact_gap":None if cap_attached else float(gap),"grip_error":(cap.location-m.hand(index)-grip_offset).length if cap_attached else None,"surface_gap":None if nearest[0] is None else float(nearest[3]),"arm_reach":float(length),"goal_distance":float((goal-shoulder).length),"target_error":float(err)})
        if n==46 and d:
            # Cap lift and donning use a real hand target at the visor edge; record inability to reach.
            hide(cap,False)
            lo,hi=bounds(mesh_points(d.a.head));center=(lo+hi)/2
            mount=V((center.x,center.y,hi.z-.045));offset=V((-.25,0,.035))
            if cap_mount is None:cap_mount=d.hand(0)-offset
            alpha=ease(u/.76);desired=cap_mount.lerp(mount,alpha)+V((-.48*math.sin(math.pi*alpha),.14*math.sin(math.pi*alpha),.34*math.sin(math.pi*alpha)))
            if u<.82:
                err=d.aim(0,desired+offset);cap.location=d.hand(0)-offset
                contacts.append({"event":"cap_don","target_error":float(err),"mount_gap":(cap.location-mount).length,"released":False})
            else:
                wear_cap(cap,d)
                contacts.append({"event":"cap_don","mount_gap":(cap.location-mount).length,"released":True})
        if n in (6,21,22,23,24,38):
            who=d if n in (6,21) else m
            if who:
                hand=who.hand(0);goal=hand+V((0,-.18,.12))
                if n in (22,23,24):
                    # Reach forward and outward. Keep the elbow below the hand and expose the dorsal skin.
                    limb=who.art.arms[0];shoulder=limb.joint();length=limb.a+limb.b
                    goal=shoulder+V((-.32,-.86,-.22)).normalized()*length*.83
                contacts.append({"event":"offer_hand","target_error":who.aim(0,goal)})
                hand=who.hand(0)
                if n in (22,23,24):
                    bird,head=birds[0];a=1 if n==24 else ease(min(1,u/.70)) if n==23 else 0
                    surface,tree=who.hand_surface(0)
                    bird.scale=(.66,.66,.66);bird.rotation_euler.z=0
                    landing=surface+V((0,0,.005))
                    # Land on evaluated distal-hand skin, not the socket centre or sleeve volume.
                    bird.location=V((-1.35,-1.45,0)).lerp(landing,a)
                    if n==23:bird.location.z+=.27*math.sin(math.pi*a)
                    head.rotation_euler.x=.45+.35*math.sin(t*8)
                    for j,c in enumerate(crumbs[:3]):c.location=surface+V((.015*(j-1),-.045,.008));c.hide_render=False
                    if a>=.999:
                        gaps=[]
                        for x in (-.039,.039):
                            foot=bird.location+V((x*.66,-.025*.66,0))
                            hit=tree.ray_cast(foot+V((0,0,.5)),V((0,0,-1)),1)[0]
                            gaps.append(None if hit is None else foot.z-hit.z)
                        contacts.append({"event":"pigeon_feet","vertical_gaps":gaps,"surface":list(surface)})
                else:
                    for i,c in enumerate(crumbs[:7]):
                        a=(u+i*.12)%1;c.location=hand.lerp(V((hand.x+(i-3)*.07,hand.y-.3,.015)),a)
        if n==12:
            for i,c in enumerate(crumbs):
                a=(u+i*.04)%1;c.location=(-.7+(i%5)*.035,-1.1-(i//5)*.055,.015+1.1*(1-a*a))
        if n in (41,43,44) and d:
            hide(stick,False)
            index=1  # near-camera arm on the leftward walk
            d.aim(index,d.hand(index)+V((-.20,-.18,.08)))
            hand=d.hand(index);stick.location=hand
            if cane_length is None:cane_length=max(1.025,hand.z+.10)
            stick.scale=(1,1,cane_length/1.0225)
            tip_z=max(0,hand.z-cane_length)
            dx=math.sqrt(max(0,cane_length*cane_length-(hand.z-tip_z)**2))
            direction=V((-dx,0,tip_z-hand.z)).normalized()
            stick.rotation_mode="QUATERNION";stick.rotation_quaternion=V((0,0,-1)).rotation_difference(direction)
            contacts.append({"event":"cane","tip_floor_gap":tip_z,"grip_error":(stick.location-hand).length})
        if n in (45,48) and m and d:
            # Contact choreography is story-specific, not a modification to the locked motion functions.
            mh,dh=m.hand(1),d.hand(0)
            target=(mh+dh)/2+V((0,-.43 if n==48 else -.25,.14 if n==48 else .19))
            # Both hands arrive before ownership changes. Separate the two grip surfaces across the prop width.
            start=.55 if n==45 else .0;arrive=.76 if n==45 else .18;release=.91 if n==45 else .35
            weight=ease((u-start)/max(.01,arrive-start))
            # Releasing hand retreats; receiving hand holds at transfer position through the cut.
            mw=weight*(1-ease((u-release)/.09)) if n==45 else weight
            dw=weight if n==45 else weight*(1-ease((u-release)/.12))
            gap=.12 if n==45 else .085
            mt=target+V((-gap,0,0));dt=target+V((gap,0,0))
            m.aim(1,mh.lerp(mt,mw));d.aim(0,dh.lerp(dt,dw))
            mh,dh=m.hand(1),d.hand(0)
            prop=cap if n==45 else bags[1];hide(prop,False)
            # The prop remains attached to the giving grip until both hands reach the anchor.
            a=ease((u-arrive)/max(.01,release-arrive))
            prop.location=(mh+V((gap,0,0))).lerp(dh-V((gap,0,0)),a) if n==45 else (dh-V((gap,0,0))).lerp(mh+V((gap,0,0)),a)
            contacts.append({"event":"cap" if n==45 else "bag","socket_separation":(mh-dh).length,"giver_receiver_target_error":max((mh-mt).length,(dh-dt).length),"handoff":arrive<=u<=release})
        if n in (47,48) and d:
            for i,bag in enumerate(bags):
                hide(bag,False)
                if n==47:
                    # Pull folded bags upward and forward from the two outer jacket sides.
                    index=1-i;limb=d.art.arms[index];shoulder=limb.joint();length=limb.a+limb.b
                    direction=V(((-1,1)[index]*(.10+.30*ease(u)),-.14-.68*ease(u),-.92+.47*ease(u))).normalized()
                    error=d.aim(index,shoulder+direction*length*.77)
                    bag.location=d.hand(index)
                    contacts.append({"event":"bag_retrieval","bag":i,"target_error":float(error),"socket_error":(bag.location-d.hand(index)).length})
                elif i==0:bag.location=d.hand(1)
        bpy.context.view_layer.update()
        # Evaluate exact projection on every frame, not just the rendered samples.
        # Explicit shot-specific subject and prop framing; measured bounds are logged, not assumed.
        kind=shot["camera"];heroes=hero_names(n,kind,actors)
        actor_target=actors[heroes[0]] if heroes else d if n in (4,44,47) else m or d
        target=V((0,-.1,1.05));dist=5.8;lens=42;angle=.10 if n%2 else -.13
        if actor_target:
            lo,hi=bounds(v for ob in actor_target.meshes() for v in mesh_points(ob));center=(lo+hi)/2
            target=center;target.z=1.05 if actor_target.mode=="walk" else center.z+.12
            if kind=="medium":dist=3.75;lens=48;target.z=center.z+.02
            if kind=="close":target=(lo+hi)/2;target.z=hi.z-.30;dist=2.0;lens=52
        if n==18:target=V((0,.04,1.08));dist=5.4;lens=39;angle=-.08
        if kind=="wide":dist=7.1;lens=36;target=V((0,-.35,1.02));angle=.16
        if kind=="insert":
            obj=bags[0] if n in (4,19,47) else bags[1] if n==10 else cap if n in (29,32,36) else stick if n==44 else birds[0][0] if n in (5,23,28,37) else None
            target=obj.location.copy() if obj else V((0,-1.15,.25))
            if n==19:target=(bags[0].location+bags[1].location)/2
            if n==27:target=V((.83,cy,top+.13))
            if n==41:target=V((.78,cy,top+.12))
            if n==22 and m:target=m.hand(0)
            target.z+=.10;dist=1.85 if n not in (19,27,41) else 3.4;lens=40;angle=.25
        # Portrait-specific hero/prop camera overrides, never changing the locked rigs.
        if n==1 and m:
            lo,hi=bounds(v for ob in m.meshes() for v in mesh_points(ob));target=(lo+hi)/2;dist=3.65;lens=48;angle=.60
        if n in (3,6,21) and d:dist=3.28;lens=48
        if n in (4,10):
            obj=bags[0] if n==4 else bags[1];target=obj.location+V((0,-.02,-.17));dist=1.35;lens=45;angle=.10 if n==4 else -.12
            if n==4:dist=.98;lens=49;angle=.16
        if n==19:
            target=(bags[0].location+bags[1].location)/2+V((0,0,-.16));dist=2.30;lens=42;angle=.02
        if n==2 and m and d:
            mc=(bounds(v for ob in m.meshes() for v in mesh_points(ob))[0]+bounds(v for ob in m.meshes() for v in mesh_points(ob))[1])/2
            target=mc;target.z=mc.z+.03;dist=3.65;lens=48;angle=.88
        if n==16 and d:
            lo,hi=bounds(v for ob in d.meshes() for v in mesh_points(ob));target=V(((lo.x+hi.x)/2,(lo.y+hi.y)/2,hi.z-.38));dist=1.82;lens=49;angle=-.18
        if n==22 and m:
            surface,_=m.hand_surface(0);target=surface+V((.12,0,.14));dist=1.48;lens=43;angle=-.45
        if n==23 and m:
            # Follow the actual bird during approach rather than cropping its first 20 frames.
            target=birds[0][0].location+V((0,-.025,.12));dist=1.72;lens=43;angle=-.45
        if n==24 and m:
            lo,hi=bounds(mesh_points(m.a.head));head_center=(lo+hi)/2
            target=head_center.lerp(birds[0][0].location+V((0,0,.16)),.40);dist=2.50;lens=46;angle=-.30
        if n==25 and m:angle=.95
        if n==31 and m:
            # Frame the entire hero and the actual cap throughout the attachment.
            pts=[v for ob in m.meshes() for v in mesh_points(ob)]+[v for ob in cap.children_recursive if ob.type=="MESH" for v in mesh_points(ob)]
            lo,hi=bounds(pts);target=(lo+hi)/2;dist=3.45;lens=48;angle=.48
        if n==32 and m:target=cap.location+V((0,0,.10));dist=1.65;lens=45;angle=-.13
        if n==35 and m:
            lo,hi=bounds(v for ob in m.meshes() for v in mesh_points(ob));target=(lo+hi)/2;target.z=1.02;dist=3.45;lens=49;angle=.10
        if n==18 and m:
            lo,hi=bounds(v for ob in m.meshes() for v in mesh_points(ob));target=(lo+hi)/2;dist=3.55;lens=49;angle=-.28
        if n==41:
            target=V((.50,cy,top+.09));dist=1.6;lens=47;angle=-.30
        if n==43 and d:
            lo,hi=bounds(v for ob in d.meshes() for v in mesh_points(ob));target=(lo+hi)/2+V((-.12,-.12,0));dist=3.75;lens=48;angle=-.65
        if n==44:
            tip=stick.matrix_world@V((0,0,-1.0225));target=stick.location.lerp(tip,.5);dist=2.85;lens=45;angle=-.55
        if n==46 and d:
            pts=mesh_points(d.a.head)+[v for ob in cap.children_recursive if ob.type=="MESH" for v in mesh_points(ob)]
            lo,hi=bounds(pts);target=(lo+hi)/2+V((0,0,-.05));dist=2.70;lens=46;angle=.24
        if n==47:
            # Both actual prop meshes must remain inside the portrait margins as arms open.
            pts=[v for bag in bags for ob in bag.children_recursive if ob.type=="MESH" for v in mesh_points(ob)]
            lo,hi=bounds(pts);target=(lo+hi)/2;dist=3.25;lens=46;angle=.08
        if n==45 and m:
            pts=[v for ob in m.meshes() for v in mesh_points(ob)]+[v for ob in cap.children_recursive if ob.type=="MESH" for v in mesh_points(ob)]
            lo,hi=bounds(pts);target=(lo+hi)/2;dist=3.55;lens=48;angle=.40
        if n==48 and m and d:
            # Search a fixed closing portrait at the first frame. Include both heads
            # and both props, with conservative edge margin; do not optimize away Dad.
            if pair_setup is None:
                groups=[mesh_points(a.a.head) for a in (m,d)]+[[v for ob in bag.children_recursive if ob.type=="MESH" for v in mesh_points(ob)] for bag in bags]
                lo,hi=bounds(v for group in groups for v in group);aim=(lo+hi)/2
                best=None
                for ang in (0,.20,-.20,.35,-.35,.5,-.5,.65,-.65):
                    for ds in (3.7,4.1,4.5,4.9,5.3,5.8,6.3):
                        for ln in (42,48):
                            loc=aim+V((math.sin(ang)*ds,-math.cos(ang)*ds,.12));camera.location=loc;camera.data.lens=ln;point_at(camera,aim);bpy.context.view_layer.update()
                            bb=[project(scene,camera,g) for g in groups]
                            if min(b[4] for b in bb)<=0:continue
                            excess=sum(max(0,.07-b[0])+max(0,b[1]-.93)+max(0,.07-b[2])+max(0,b[3]-.93) for b in bb)
                            gap=max(bb[0][0]-bb[1][1],bb[1][0]-bb[0][1]);headsize=min(b[3]-b[2] for b in bb[:2])
                            score=100*excess+8*max(0,.035-gap)-headsize+.02*abs(ang)
                            if best is None or score<best[0]:best=(score,loc.copy(),aim.copy(),ln)
                if best is None:raise RuntimeError("No closing portrait proposal")
                pair_setup=best
            _,pair_location,target,lens=pair_setup
        location=pair_location if n==48 and pair_setup is not None else target+V((math.sin(angle)*dist,-math.cos(angle)*dist,.32 if kind!="insert" else .65))
        camera.location=location;camera.data.lens=lens;point_at(camera,target);bpy.context.view_layer.update()
        if n==31:
            # R7 proved the hero safely framed on all 60 frames and the cap
            # right edge at x=.996–1.000. Truck camera right without changing
            # lens, actor staging or contact. Exact geometry is still gated.
            right=camera.matrix_world.to_3x3()@V((1,0,0))
            shift=right*.13
            camera.location+=shift;target+=shift;point_at(camera,target);bpy.context.view_layer.update()
        geo=geometry(scene,camera,actors,heroes,kind)
        prop_roots={4:[bags[0]],5:[birds[0][0]],10:[bags[1]],19:bags,23:[birds[0][0]],24:[birds[0][0]],28:[birds[0][0]],29:[cap],31:[cap],32:[cap],36:[cap],37:[birds[0][0]],43:[stick],44:[stick],45:[cap],46:[cap],47:bags,48:bags}.get(n,[])
        props={ob.name:prop_geometry(scene,camera,ob) for ob in prop_roots if any(not x.hide_render for x in ob.children_recursive if x.type=="MESH")}
        if n==19 and len(props)==2:
            boxes=[project(scene,camera,[v for ob in bag.children_recursive if ob.type=="MESH" for v in mesh_points(ob)]) for bag in bags]
            gap=max(boxes[0][0]-boxes[1][1],boxes[1][0]-boxes[0][1]);contacts.append({"event":"two_bag_screen_separation","gap":float(gap)})
            if gap<.025:
                for p0 in props.values():p0["pass"]=False
        geometry_records.append({"frame":global_frame,"heroes":geo,"props":props,"contacts":contacts,"pass":all(x["pass"] for x in list(geo.values())+list(props.values()))})
        if f not in selected:continue
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
    visibility={};visibility_error=None
    if args.mode=="preflight" and heroes:
        try:visibility=rendered_visibility(scene,out,"bench_%02d"%n,actors,heroes)
        except Exception as exc:visibility_error=repr(exc);print("VISIBILITY_DIAGNOSTIC_FAILED",visibility_error,flush=True)
    (out/"geometry_all_frames.json").write_text(json.dumps(geometry_records,indent=2))
    manifest={"shot":shot,"frames":len(records),"geometry_frame_count":len(geometry_records),"geometry_pass":all(r["pass"] for r in geometry_records),"visibility":visibility,"visibility_error":visibility_error,"mode":args.mode,"resolution":[540,960],"fps":24,"engine":"EEVEE","denoising":False,"samples":32,"elapsed":time.monotonic()-started,"records":records,"review":"candidate; visual and contact verification required"}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    assert len(records)==len(selected)
    # The full film's stricter encoded darkness gate is run after editing.
    assert max(r["near_black_percent"] for r in records)<= (10 if args.mode=="preflight" else 2),"Darkness gate; partial images retained"
    if args.mode=="preflight":assert all(g["pass_tracking"] for r in records for g in r.get("garments",{}).values()),"Garment tracking gate"
    # Do not throw before partial uploads for failed geometry or visibility.
    # The package audit reports these independently and blocks final approval.
if __name__=="__main__":main()
