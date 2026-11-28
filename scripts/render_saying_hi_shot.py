"""Saying Hi candidate proof/animatic render driver. Story-local only.
Every motion sample invokes Blender render independently. No full-film mode.
"""
import argparse,json,math,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ.setdefault("R6_KNEE_BLEND","1")
import bpy
import numpy as np
from mathutils import Vector,Matrix
from PIL import Image
from render_demo import cube,empty,material,point_at,area_light
from quality_cafe import sphere
from stage_a_cafe import cylinder
from library_camera import create,project
from library_atmosphere import Atmosphere
from library_props import build,palette
from library_locomotion import StrideLock
from r6_imported_cycles import Retarget
from r6_character import mesh_points,bounds,group_points
from character_motion_correction import apply_corrected,rear_hip
from chapter1_articulation import Articulation,group_tree,tree_for_object
from chapter1_round2 import neutral_feet,seat_setup,pose as sit_pose
from clothing_articulation import ArticulatedClothes
from saying_hi_cast import build_cast_actor
from saying_hi_square import build_square
from saying_hi_contacts import waffle,waffle_pose,carry_two,surface_tree
from saying_hi_chart_render import portrait_board
from facial_expressions import enable_blinking
from render_saying_hi_smoke import load,setup,frame,actor_points,seat_actor

ROOT=Path(__file__).resolve().parents[1];FPS=30
UNITS={"chart_initial":[4,5,6,7],"crossing":[20,21],"otis_eyes":[22],"june_question":[31,32,33],"june_answer":[34],"dog_name":[42],"seating":[43],"empty_wall":[45],"chart_final":[46],"closing":[48]}
CHART={4:"columns",5:"arrows",6:"zero",7:"me",18:"arrows",39:"me",46:"replacement"}
def V(x):return Vector(x)
def clamp(u):return max(0,min(1,u))
def ease(u):u=clamp(u);return u*u*(3-2*u)
def show(root,visible):
    for o in [root]+list(root.children_recursive):o.hide_render=not visible
def yaw_to(a,b):
    d=V(b)-V(a);return math.atan2(d.x,-d.y)
def aim_world(a,i,target):
    shoulder=(a.armature.matrix_world@a.arms[i].matrix).translation
    direction=a.root.matrix_world.to_3x3().inverted()@(V(target)-shoulder)
    a.aim_arm(i,direction);bpy.context.view_layer.update()
    return (a.grips[i].matrix_world.translation-V(target)).length
def hand_contact(a,i,prop):
    tree=group_tree(a,a.arms[i]);pts=group_points(a.body,a.arms[i].name)
    gaps=[];pairs=0
    for obj in prop.children_recursive:
        if obj.type!="MESH":continue
        ptree,pverts=surface_tree(obj)
        gaps += [tree.find_nearest(v)[3] for v in pverts]
        gaps += [ptree.find_nearest(v)[3] for v in pts]
        pairs+=len(tree.overlap(ptree))
    return {"sampled_min_arm_surface_gap":min(gaps) if gaps else None,"arm_prop_overlap_pairs":pairs,"scope":"whole rigid arm surface; not signed distal-hand penetration"}
def props(p):
    chart=empty("Otis portable chart",(0,0,0))
    cube("chart stiff paper",(.20,0,0),(.40,.022,.57),p["paper"],chart,bevel=.006)
    for i in range(5):
        cube("chart drawn row",( .20,-.013,.19-i*.075),(.32,.004,.011),p["ink"],chart,bevel=0)
    pencil=empty("narrator yellow pencil",(0,0,0))
    cube("pencil yellow shaft",(0,0,0),(.038,.038,.23),p["yellow"],pencil,bevel=.003)
    cube("pencil graphite point",(0,0,-.128),(.022,.022,.028),p["ink"],pencil,bevel=.003)
    return chart,pencil
def prop_mats():
    p=palette()
    for k,c in {"paper":(.89,.79,.59),"ink":(.055,.038,.025),"yellow":(.85,.49,.04),"wood2":(.29,.14,.055),"card":(.86,.23,.26),"dog_photo":(.50,.28,.12),"seat":(.30,.14,.055)}.items():p[k]=material(k,c)
    return p
def fit_camera(scene,cam,actors,target=None,wide=False):
    pts=[v for a in actors for v in actor_points(a)]
    if pts:
        lo,hi=bounds(pts);center=(lo+hi)/2
    else:center=V((0,4,1))
    if target is not None:center=V(target)
    if wide:frame(scene,cam,(10.8,-14.6,10.7),center,25);return
    # choose a fixed angle with visible faces; conservative framing over all subjects
    candidates=[]
    for ang in (-.85,-.50,-.20,.20,.50,.85,1.6,-1.6,2.5,-2.5,3.14):
        for dist in (3.3,4.0,4.8,5.8,7.0):
            loc=center+V((math.sin(ang)*dist,-math.cos(ang)*dist,.20))
            frame(scene,cam,loc,center,46)
            if not pts:continue
            box=project(scene,cam,pts);ex=sum(max(0,z) for z in (.05-box[0],box[1]-.95,.05-box[2],box[3]-.95))
            visible=0
            for a in actors:
                head=(sum(a.head_bounds,V((0,0,0)))/2)
                face=sum(mesh_points(a.face),V((0,0,0)))/len(mesh_points(a.face))
                forward=(a.root.matrix_world.to_3x3()@V((0,-1,0))).normalized()
                visible+=max(0,forward.dot((loc-face).normalized()))
            score=100*ex-1.2*visible-0.5*(box[3]-box[2])
            candidates.append((score,loc.copy(),center.copy()))
    if not candidates:frame(scene,cam,center+V((0,-4,1)),center,40);return
    _,loc,center=min(candidates,key=lambda q:q[0]);frame(scene,cam,loc,center,46)

class SceneUnit:
    def __init__(self,scene,cam,cast,stage,unit,shot_ids,map_path,lineup,variant=None):
        self.scene=scene;self.cam=cam;self.cast=cast;self.stage=stage;self.unit=unit;self.ids=shot_ids;self.lineup=lineup;self.actors={};self.marks=stage["marks"];self.p=prop_mats();self.metrics=[];self.scenery=None;self.static=[];self.frame_count=0;self.variant=variant
        self.chart_mode=all(n in CHART for n in shot_ids)
        if self.chart_mode:
            self.setup_chart();return
        _,self.scenery=build_square(stage,map_path)
        Atmosphere(scene,target=(0,3,1)).apply("midday")
        area_light("Saying Hi soft fill",(2,-5,6),550,8,(1,.94,.86))
        self.chart,self.pencil=props(self.p);show(self.chart,False);show(self.pencil,False)
        if unit=="crossing":self.setup_crossing()
        elif unit=="otis_eyes":self.setup_eyes()
        elif unit in ("seating","closing","dog_name"):self.setup_seating()
        elif unit in ("june_question","june_answer"):self.setup_june()
        elif unit=="empty_wall":frame(scene,cam,(0,3.5,3.6),(0,8,.7),26)
        else:self.setup_still(shot_ids[0])
    def actor(self,cid):
        if cid not in self.actors:
            self.actors[cid]=build_cast_actor(cid,self.cast["actors"][cid])
            enable_blinking(self.scene,self.actors[cid],seed=sum(ord(ch) for ch in cid))
        return self.actors[cid]
    def mark(self,cid):
        return self.marks[("wall_" if cid in self.stage["layouts"]["initial"]["wall"] else "well_")+cid]
    def place(self,cid,pos=None,yaw=None,expression="neutral",action="idle",u=.5,t=.5):
        a=self.actor(cid);m=self.mark(cid)
        apply_corrected(a,action,u,t,tuple(m["xyz"] if pos is None else pos),math.radians(m["yaw_deg"]) if yaw is None else yaw)
        a.pose(expression);return a
    def seat(self,cid):
        a=self.actor(cid);m=self.mark(cid);art,cloth,metrics=seat_actor(a,m);a.pose("happy" if cid in self.stage["layouts"]["initial"]["well"] else "neutral")
        self.static.append((cid,metrics));return a
    def setup_chart(self):
        scene=self.scene;scene.world.color=(.5,.5,.5);scene.view_settings.view_transform="Standard";area_light("Chart desk light",(0,-2,6),350,5,(1,.95,.87))
        p=self.p;cube("Otis desk",(0,0,.65),(2.5,3.5,1.30),p["wood2"],bevel=.03)
        cube("Chart paper backing",(0,0,1.315),(1.50,2.66,.025),p["paper"],bevel=.01)
        bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,1.331))
        self.sheet=bpy.context.object;self.sheet.name="Otis actual chart";self.sheet.scale=(.75,1.33,1)
        self.img=bpy.data.images.new("Otis chart artwork",1080,1920,alpha=True)
        mat=bpy.data.materials.new("Chart image");mat.use_nodes=True
        nt=mat.node_tree;bs=nt.nodes.get("Principled BSDF");tex=nt.nodes.new("ShaderNodeTexImage");tex.image=self.img
        em=nt.nodes.new("ShaderNodeEmission");nt.links.new(tex.outputs["Color"],em.inputs["Color"]);em.inputs["Strength"].default_value=1.;nt.links.new(em.outputs[0],nt.nodes.get("Material Output").inputs["Surface"])
        self.sheet.data.materials.append(mat);self.last_board=None
        a=self.actor("otis");self.chart,self.pencil=props(p);show(self.chart,False)
        # Otis is physically beside desk; crop deliberately allows pencil/arm at left.
        self.placement=V((-1.46,.35,0));self.chart_yaw=math.pi/2
        frame(scene,self.cam,(.02,0,6.6),(.02,0,1.33),40,ortho=2.10)
        self.cam.rotation_euler=(0,0,0);self.cam.location=(.02,0,6.6);bpy.context.view_layer.update()
    def update_chart(self,n,u,t):
        mode=CHART[n];progress=ease(u) if mode in ("columns","arrows","replacement") and n in (4,5,46) else 1
        if n==46:progress=.25+.75*progress
        key=(mode,max(1,math.ceil(20*progress)) if mode=="columns" else math.floor((20 if mode=="replacement" else 10)*progress+1e-8))
        if key!=self.last_board:
            img,info=portrait_board(self.stage,self.lineup,mode,progress);arr=np.array(img.convert("RGBA"),dtype=np.float32)[::-1]/255.
            self.img.pixels.foreach_set(arr.ravel());self.img.update();self.last_board=key;self.boardinfo=info
        a=self.place("otis",self.placement,self.chart_yaw,"smug",t=t)
        target=(-.92,.35+.23*math.sin(t*5),1.37)
        err=aim_world(a,0,target)
        self.pencil.matrix_world=a.grips[0].matrix_world.copy();self.pencil.rotation_euler=(0,-math.pi/2,0)
        bpy.context.view_layer.update()
        return {"chart":self.boardinfo,"pencil_aim_residual":err,"pencil_to_arm":hand_contact(a,0,self.pencil),"note":"Artwork is animated on a physical paper surface; pencil gesture is not guaranteed to track every individual arrow."}
    def setup_crossing(self):
        # Calibrate the locked native walk BEFORE constructing 19 spectators.
        # The actual scenery remains present. No actor translation warp.
        self.a=self.actor("narrator");self.start=V(self.marks["cross_start"]["xyz"]);self.end=V(self.marks["cross_end"]["xyz"])
        self.yaw=yaw_to(self.start,self.end);self.pickup_frames=20
        self.pickup_table=cube("Chart pickup ledge",tuple(self.start+V((-.8,.0,.54))),(.65,.52,1.08),self.p["wood2"],bevel=.02)
        self.chart_rest=self.start+V((-.83,0,1.13));self.pencil_rest=self.start+V((-.55,0,1.13))
    def prepare_stride(self,nframes):
        movement=nframes-self.pickup_frames
        if movement<12:raise ValueError("Crossing window too short")
        self.move_frames=movement;target=(self.end-self.start).length;ret=Retarget(self.a);duration=ret.clips["walk_cycle"]["duration"]
        candidates=[]
        def evaluate(rate,phase):
            lock=StrideLock(ret,"walk_cycle",FPS,rate,self.start,self.yaw);offset=phase*duration/rate
            for i in range(movement):lock.step(offset+i/FPS,settle=ease((i-(movement-10))/9))
            report=lock.report();delta=lock.pos-self.end;stop=math.hypot(delta.x,delta.y)
            # Locked pass is lexicographically mandatory, not a soft penalty.
            row={"rate":rate,"phase":phase,"offset_seconds":offset,"stop_error_xy":stop,"pass":report["pass"],"backward_frames":report["backward_frames"],"stance_velocity_rms":report["stance_velocity_rms"],"max_contact_gap":report["max_contact_gap"],"max_floor_error":report["max_floor_error"]}
            candidates.append(row);print("CROSSING_SEARCH",json.dumps(row),flush=True)
            return row
        rank=lambda q:(not q["pass"],q["backward_frames"],q["stop_error_xy"],q["stance_velocity_rms"])
        for phase in (0,.125,.25,.375,.5,.625,.75,.875):evaluate(.20,phase)
        best=min(candidates,key=rank)
        for rate in (.17,.185,.195,.205,.215,.23,.245):evaluate(rate,best["phase"])
        best=min(candidates,key=rank)
        for rate in (max(.10,best["rate"]-.004),best["rate"]+.004):evaluate(rate,best["phase"])
        best=min(candidates,key=rank)
        self.stride_candidate=best;self.stride_search=candidates
        self.stride_offset=best["offset_seconds"]
        self.lock=StrideLock(ret,"walk_cycle",FPS,best["rate"],self.start,self.yaw)
        for cid in self.stage["layouts"]["initial"]["wall"]+self.stage["layouts"]["initial"]["well"]:
            if cid!="narrator":self.seat(cid)
        # One locked camera: fit the whole geography and both ends of the
        # crossing using actual spectator geometry and narrator route envelope.
        pts=[v for cid,a in self.actors.items() if cid!="narrator" for v in actor_points(a)]
        for p in (self.start,self.end):
            pts.extend(p+V((x,y,z)) for x in (-.85,.85) for y in (-.4,.4) for z in (0,2.6))
        lo,hi=bounds(pts);aim=(lo+hi)/2;choices=[]
        for x in (-10.,-7.,7.,10.):
            for y in (-10.,-7.,-4.):
                for z in (6.,9.,12.):
                    loc=aim+V((x,y,z))
                    frame(self.scene,self.cam,loc,aim,35,ortho=12.)
                    p=project(self.scene,self.cam,pts)
                    needed=12.*max(abs(p[0]-.5),abs(p[1]-.5),abs(p[2]-.5),abs(p[3]-.5))/.455
                    scale=max(6.8,needed)
                    frame(self.scene,self.cam,loc,aim,35,ortho=scale)
                    b=project(self.scene,self.cam,pts)
                    # Larger actor pixels and less excess ground/sky.
                    probe=project(self.scene,self.cam,[self.start+V((0,0,0)),self.start+V((0,0,2.3))])
                    safe=b[4]>0 and .035<=b[0]<=b[1]<=.965 and .035<=b[2]<=b[3]<=.965
                    score=1000*(not safe)-(probe[3]-probe[2])+abs(x)*.001
                    choices.append((score,loc.copy(),scale,list(b),probe[3]-probe[2]))
        _,loc,scale,box,coverage=min(choices,key=lambda q:q[0]);frame(self.scene,self.cam,loc,aim,35,ortho=scale)
        self.cross_camera={"position":list(loc),"target":list(aim),"ortho_scale":scale,"group_bounds":box,"narrator_vertical_proxy":coverage}
    def update_crossing(self,index,u,t):
        a=self.a;show(self.chart,True);show(self.pencil,True)
        if index<self.pickup_frames:
            self.place("narrator",self.start,self.yaw,"worried",t=t)
            self.chart.location=self.chart_rest;self.chart.rotation_euler=(math.pi/2,0,0)
            self.pencil.location=self.pencil_rest;self.pencil.rotation_euler=(math.pi/2,0,0)
            w=ease(index/(self.pickup_frames-1))
            for i,target in ((0,self.pencil_rest),(1,self.chart_rest)):
                aim_world(a,i,a.grips[i].matrix_world.translation.lerp(target,w))
            if index<self.pickup_frames-2:return {"phase":"pickup reach","right_target_error":(a.grips[0].matrix_world.translation-self.pencil_rest).length,"left_target_error":(a.grips[1].matrix_world.translation-self.chart_rest).length}
        else:
            k=index-self.pickup_frames;row=self.lock.step(self.stride_offset+k/FPS,settle=ease((k-(self.move_frames-10))/9));a.pose("worried" if k<self.move_frames*.75 else "neutral")
        # Keep original lower body stride; only replace upper arm directions to carry.
        a.aim_arm(0,(.18,-.64,-.79));a.aim_arm(1,(-.20,-.40,-.92));bpy.context.view_layer.update()
        attachment=carry_two(self.chart,self.pencil,a.grips[1],a.grips[0])
        self.chart.rotation_euler=(0,0,self.yaw);self.pencil.rotation_euler=(.15,0,self.yaw);bpy.context.view_layer.update()
        return {"phase":"carry","socket_alignment":attachment,"chart_contact":hand_contact(a,1,self.chart),"pencil_contact":hand_contact(a,0,self.pencil),"stride":self.lock.records[-1] if self.lock.records else None}
    def setup_eyes(self):
        m=self.mark("otis");self.eye_pos=V(m["xyz"])+V((0,-.65,0));self.eye_yaw=0
        a=self.actor("otis");self.eye_art=Articulation(a,arms=True,legs=False);self.eye_clothes=ArticulatedClothes(a,self.eye_art)
        self.place("otis",self.eye_pos,0,"worried");self.eye_art.rigid();self.eye_clothes.sync()
        frame(self.scene,self.cam,self.eye_pos+V((0,-3.1,2.05)),self.eye_pos+V((0,0,1.65)),52)
    def update_eyes(self,u,t):
        a=self.place("otis",self.eye_pos,0,"worried",t=t);self.eye_art.rigid()
        lo,hi=bounds(mesh_points(a.head));center=(lo+hi)/2
        w=ease(min(1,u*2.2));res=[]
        for i,limb in enumerate(self.eye_art.arms):
            sign=(-1,1)[i];target=V((center.x+sign*.055,lo.y-.19,center.z+.12))
            hand=limb.lower.matrix_world@V((0,0,-limb.b));target=hand.lerp(target,w)
            end=self.eye_art.arm_target(i,target,V((sign,-.10,-.45)),0)
            res.append({"hand_target_gap":(end-target).length,"head_arm_overlap_pairs":len(tree_for_object(a.head).overlap(tree_for_object(limb.lower)))})
        self.eye_clothes.sync();return {"eyes":res,"coverage_progress":w,"limitation":"story long sleeves use locked adapter's original role cutoff; visual fit requires review"}
    def setup_june(self):
        jmark=self.marks["well_june"];j=V(jmark["xyz"]);n=V(self.marks["interview_june"]["xyz"])
        self.jp=j;self.np=n;self.jyaw=yaw_to(j,n);self.nyaw=yaw_to(n,j)
        a=self.place("narrator",n,self.nyaw,"worried");b=self.place("june",j,self.jyaw,"happy")
        hero=a if self.unit=="june_question" else b;pos=n if hero==a else j;yaw=self.nyaw if hero==a else self.jyaw
        forward=V((math.sin(yaw),-math.cos(yaw),0));side=V((math.cos(yaw),math.sin(yaw),0))
        # Select a genuine unobstructed reverse composition rather than
        # the old near-axis OTS where the foreground actor hid the speaker.
        target=pos+V((0,0,1.53))
        face=mesh_points(hero.face)
        center=sum(face,V((0,0,0)))/len(face)
        samples=[center]+[center.lerp(v,.55) for v in face]
        deps=bpy.context.evaluated_depsgraph_get();choices=[]
        for sign in (-1,1):
            for side_dist in (1.9,2.5,3.1):
                for forward_dist in (1.9,2.5,3.1):
                    loc=pos+forward*forward_dist+side*sign*side_dist+V((0,0,1.72))
                    frame(self.scene,self.cam,loc,target,44)
                    blocked=0
                    for sample in samples:
                        ray=sample-loc;hit,*_=self.scene.ray_cast(deps,loc,ray.normalized(),distance=max(0,ray.length-.025))
                        blocked+=int(hit)
                    proj=project(self.scene,self.cam,face)
                    safe=proj[4]>0 and .05<=proj[0]<=proj[1]<=.95 and .06<=proj[2]<=proj[3]<=.94
                    score=100*blocked+1000*(not safe)+abs(side_dist/forward_dist-.95)*2-(proj[3]-proj[2])
                    choices.append((score,blocked,loc.copy(),proj))
        score,blocked,loc,proj=min(choices,key=lambda q:q[0])
        frame(self.scene,self.cam,loc,target,44)
        self.reverse_camera={"face_blocked_samples":blocked,"face_samples":len(samples),"location":list(loc),"face_projection":list(proj)}
        if blocked:print("REVERSE_FACE_OCCLUSION",self.reverse_camera,flush=True)
    def update_june(self,n,u,t):
        a=self.place("narrator",self.np,self.nyaw,"worried" if self.unit=="june_question" else "neutral",t=t)
        b=self.place("june",self.jp,self.jyaw,"happy" if n==34 else "neutral",t=t)
        a.set_bone("head",(.06*math.sin(t*4),0,.035*math.sin(t*3)));a.set_bone("torso",(.035,0,.025*math.sin(t*2)))
        b.set_bone("head",(-.045*math.sin(t*3),0,.06*math.sin(t*2)));b.set_bone("torso",(.025*math.sin(t*2),0,0))
        if self.unit=="june_question":
            show(self.chart,True);show(self.pencil,True)
            a.aim_arm(1,(-.14,-.35,-.92));a.aim_arm(0,(.23+.04*math.sin(t*25),-.83,-.47+.045*math.sin(t*23)))
            carry=carry_two(self.chart,self.pencil,a.grips[1],a.grips[0]);self.chart.rotation_euler.z=self.nyaw;self.pencil.rotation_euler=(.20,0,self.nyaw)
            bpy.context.view_layer.update()
            return {"pencil_shake_phase":math.sin(t*25),"socket_alignment":carry,"chart_contact":hand_contact(a,1,self.chart),"pencil_contact":hand_contact(a,0,self.pencil),"reverse_camera":self.reverse_camera,"face_projection":list(project(self.scene,self.cam,mesh_points(a.face))),"pencil_projection":list(project(self.scene,self.cam,[v for o in self.pencil.children_recursive if o.type=="MESH" for v in mesh_points(o)]))}
        return {"reverse_camera":self.reverse_camera,"june_face_projection":list(project(self.scene,self.cam,mesh_points(b.face))),"head_reaction":True}
    def setup_seating(self):
        self.seat_data={};self.dog=waffle();self.dog[0].location=self.marks["waffle"]["xyz"]
        self.dog[0].rotation_euler.z=math.radians(self.marks["waffle"]["yaw_deg"])
        for cid in ("june","narrator"):
            a=self.actor(cid);m=self.marks[cid+"_seat"];yaw=math.radians(m["yaw_deg"])
            art=Articulation(a,legs=True,arms=False);cloth=ArticulatedClothes(a,art);feet=neutral_feet(a,art,yaw);s=seat_setup(a,art,yaw,feet)
            self.seat_data[cid]=(a,art,cloth,feet,s,V(m["xyz"]),yaw)
        centers=[item[4][1]+item[5] for item in self.seat_data.values()]
        top=min(item[4][0] for item in self.seat_data.values());center=sum(centers,V((0,0,0)))/2
        self.bench_top=top;self.bench_center=V((center.x,center.y,top))
        self.bench=bpy.data.objects["Actual pair seat"]
        self.bench.location.z=top-.07
        self.prev_feet={};self.prev_hip={}
        frame(self.scene,self.cam,(1.5,-3.8,2.7),(4.8,-.88,1.08),36)
    def update_seating(self,n,u,t,after_name=True):
        records={}
        for cid,item in self.seat_data.items():
            a,art,cloth,feet,seat,pos,yaw=item
            if n==43:
                f=ease(clamp((u-.20)/.75)) if cid=="narrator" else 1
                offset=V((0,.24*(1-ease(min(1,u*2.7))),0)) if cid=="june" else V((0,0,0))
            elif n==42:f=0 if cid=="narrator" else 1;offset=V((0,.24,0)) if cid=="june" else V((0,0,0))
            else:f=1;offset=V((0,0,0))
            sit_pose(a,art,"sit",f,t,yaw,feet,None,seat);art.shift(pos+offset);cloth.sync()
            a.pose("happy");a.set_bone("head",(0,0,.12 if cid=="june" else -.12))
            soles=art.soles();old=self.prev_feet.get(cid)
            records[cid]={"seated_fraction_command":f,"signed_rear_hip_gap":float(rear_hip(a)[0]-self.bench_top),"signed_foot_gaps":[float(v.z) for v in soles],"foot_step_drift":[float((v-w).length) for v,w in zip(soles,old)] if old else None}
            self.prev_feet[cid]=[v.copy() for v in soles]
        visible=n!=42 or after_name;show(self.dog[0],visible)
        dog_metric=waffle_pose(self.dog,"roll_over" if n==43 else "lie_down",ease(u)) if visible else None
        return {"seat_top":self.bench_top,"seat_contacts":records,"waffle":dog_metric,"dog_visible":visible,"limitation":"June's lateral seated shift translates feet; measured drift, not an exact stepping solve."}
    def setup_still(self,n):
        # Held-POSE animatic candidates, not finished acting. Keep recurring geography.
        s=json.loads((ROOT/"stories/saying_hi_plan.json").read_text())["shots"][n-1]
        ids=s["cast"];group=n in (1,8,9,13,19,21,36,38,44)
        if group:
            for cid in ids:
                if n in (21,38) and cid=="narrator":self.place(cid,self.marks["cross_end"]["xyz"],0,"neutral")
                elif n==44 and cid in ("leo","max"):
                    self.place(cid,self.marks["cross_end"]["xyz"][:],0,"happy")
                    self.actors[cid].root.location.x+=(-.7 if cid=="leo" else .7)
                else:self.seat(cid)
            frame(self.scene,self.cam,(10.8,-14.6,10.7),(0,4,1.1),25)
            return
        # Interview reenactments, marked at each girl's fixed well position.
        if n in (24,25,26,27,28,29,30):
            if n==30:
                ids={"faye_hi":["faye","brody"],"gia_seat":["gia","chase"],"hana_hi":["hana","kai"],"ivy_hi":["ivy","kai"]}[self.variant or "faye_hi"]
            g=next((cid for cid in ids if cid in self.cast["girls"]),"ava")
            p=V(self.marks["well_"+g]["xyz"]);q=V(self.marks["interview_"+g]["xyz"])
            for i,cid in enumerate(ids[:2]):self.place(cid,p if cid==g else q,yaw_to(p,q) if cid==g else yaw_to(q,p),"happy",action="wave" if n in (27,28,30) and cid!=g and self.variant!="gia_seat" else "idle",u=.5)
            if n==26 or self.variant=="gia_seat":
                mat=self.p["seat"];cube("Chase's actual saved chair",(p.x+.70,p.y,.55),(.70,.70,.12),mat,bevel=.02)
                for x in (-.24,.24):
                    for y in (-.24,.24):cube("Chair leg",(p.x+.70+x,p.y+y,.25),(.08,.08,.5),mat,bevel=.01)
                self.actors["chase"].aim_arm(0,(.30,-.85,-.2))
                bag=empty("Chase reserved school bag",(p.x+.70,p.y,.69));cube("School bag body",(0,0,.11),(.32,.24,.28),self.p["wood2"],bag,bevel=.035)
                cube("School bag pocket",(0,-.125,.10),(.24,.045,.17),self.p["ink"],bag,bevel=.012)
            if n in (25,29):
                girl=self.actors[g];girl.aim_arm(1,(-.12,-.72,-.64));photo=cube("Dog photograph",(0,0,0),(.30,.03,.23),self.p["dog_photo"],bevel=.004)
                photo.location=girl.grips[1].matrix_world.translation;photo.rotation_euler.z=girl.root.rotation_euler.z
                asker=next(self.actors[cid] for cid in ids if cid!=g);asker.aim_arm(0,(.16,-.65,-.60));asker.set_bone("head",(.07,0,-.10))
            fit_camera(self.scene,self.cam,list(self.actors.values()));return
        if n in (10,11,16,17):
            center=V((0,4,0))
            if n==17:ids=["chase"] if self.variant=="miss_ball" else ["kai"] if self.variant=="crayon" else ids
            for i,cid in enumerate(ids):self.place(cid,center+V(((i-(len(ids)-1)/2)*1.25,0,0)),0,"sad" if n==11 else "happy")
            if n==10:
                cart=empty("Valentine wheelbarrow",center+V((-.7,-.9,0)));cube("Wheelbarrow tray",(0,0,.50),(.70,1.02,.23),self.p["wood2"],cart)
                for i in range(12):cube("Valentine card",((i%4-.5)*.13,(i//4-1)*.17,.67+.025*i),(.16,.19,.028),self.p["card"],cart,bevel=.005)
                for x in (-.27,.27):cube("Cart handle",(x,.73,.61),(.06,.64,.07),self.p["wood2"],cart)
                sphere("Wheel",(cart.location.x,cart.location.y-.55,.20),(.15,.36,.36),self.p["ink"])
            if n==11:
                a=self.actors["narrator"];a.aim_arm(0,(.15,-.75,-.65));card=cube("Single card from Mom",a.grips[0].matrix_world.translation,(.24,.025,.19),self.p["card"],bevel=.005)
            if n==17:
                if "chase" in self.actors:
                    a=self.actors["chase"];a.pose("shocked");a.aim_arm(0,(.45,-.84,.25));a.aim_arm(1,(-.35,-.84,.25))
                    build("ball",pos=tuple(center+V((-.85,-.9,.22))),scale=.7,p=self.p)
                if "kai" in self.actors:
                    kai=self.actors["kai"];kai.aim_arm(0,(.20,-.65,.45));cube("Crayon",kai.grips[0].matrix_world.translation,(.04,.04,.24),self.p["yellow"],bevel=.005)
            fit_camera(self.scene,self.cam,list(self.actors.values()));return
        # Other narrative held poses: use named characters' marks, not anonymous stand-ins.
        if len(ids)>4:ids=ids[:4]
        if not ids:frame(self.scene,self.cam,(0,3.5,3.6),(0,8,.7),26);return
        base=V(self.marks["cross_end"]["xyz"] if n>=20 else (0,7,0))
        if n>=31 and n!=47:base=V(self.marks["interview_june"]["xyz"])
        for i,cid in enumerate(ids):
            self.place(cid,base+V(((i-(len(ids)-1)/2)*1.05,0,0)),0,"worried" if cid=="narrator" and n<37 else "happy" if n>=37 else "smug" if cid=="otis" else "neutral")
        if "chart" in s["props"]:
            a=self.actors.get("otis",self.actors.get("narrator",next(iter(self.actors.values()))))
            show(self.chart,True);a.aim_arm(1,(-.12,-.65,-.7));self.chart.matrix_world=a.grips[1].matrix_world.copy();self.chart.rotation_euler=(0,0,0)
        fit_camera(self.scene,self.cam,list(self.actors.values()))
    def update(self,n,u,t,index,after_name=True):
        if self.chart_mode:return self.update_chart(n,u,t)
        if self.unit=="crossing":return self.update_crossing(index,u,t)
        if self.unit=="otis_eyes":return self.update_eyes(u,t)
        if self.unit in ("june_question","june_answer"):return self.update_june(n,u,t)
        if self.unit in ("seating","closing","dog_name"):return self.update_seating(n,u,t,after_name)
        return {"held_pose":True,"static_seating":self.static}

def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument("--unit",choices=sorted(UNITS));g.add_argument("--shot",type=int)
    ap.add_argument("--variant");ap.add_argument("--mode",choices=["smoke","motion","still"],required=True);ap.add_argument("--map",required=True);ap.add_argument("--lineup",required=True);ap.add_argument("--output",required=True);a=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    c,stage=load();plan=json.loads((ROOT/"stories/saying_hi_plan.json").read_text());assert plan["status"]=="retimed_actual_audio"
    ids=UNITS[a.unit] if a.unit else [a.shot];unit=a.unit or next((k for k,v in UNITS.items() if a.shot in v),f"still_{a.shot:02d}")
    shots=[plan["shots"][i-1] for i in ids];start=round(shots[0]["edit_in"]*FPS);end=round(shots[-1]["edit_out"]*FPS);count=end-start
    if a.mode=="motion" and not a.unit:raise ValueError("No full-film motion mode")
    scene=setup(540,960);scene.frame_end=round(plan['audio_duration']*FPS);cam=create(scene)
    driver=SceneUnit(scene,cam,c,stage,unit,ids,a.map,a.lineup,a.variant)
    # A still for sentence 21 uses its held end state, while crossing proof spans 20–21.
    if unit=="crossing":
        whole=[plan["shots"][19],plan["shots"][20]]
        whole_start=round(whole[0]["edit_in"]*FPS);whole_end=round(whole[1]["edit_out"]*FPS)
        driver.prepare_stride(whole_end-whole_start)
        sim_start=whole_start;sim_end=whole_end
    else:sim_start=start;sim_end=end
    selected=set(range(start,end)) if a.mode=="motion" else {start+max(0,(count-1)//2)}
    if unit in ("dog_name","chart_initial","chart_final") and a.mode!="motion":selected={end-1}
    rec=[];rendered=[]
    for gf in range(sim_start,sim_end):
        if gf>=end:break
        shot=next((x for x in plan["shots"] if round(x["edit_in"]*FPS)<=gf<round(x["edit_out"]*FPS)),shots[-1])
        n=int(shot["sentence_ids"][0]);s0=round(shot["edit_in"]*FPS);s1=round(shot["edit_out"]*FPS)
        u=(gf-s0)/max(1,s1-s0-1);t=(gf-sim_start)/FPS
        scene.frame_set(gf+1);metrics=driver.update(n,u,t,gf-sim_start,gf/FPS>=shot["audio_out"])
        rec.append({"global_frame":gf,"sentence":n,"metrics":metrics})
        if gf not in selected:continue
        path=out/("frame_%05d.png"%gf);scene.render.filepath=str(path);clock=time.monotonic()
        print("SAYING_HI_RENDER_START",unit,gf,flush=True);bpy.ops.render.render(write_still=True)
        pixels=np.asarray(Image.open(path).convert("RGB"));row={"frame":gf,"file":path.name,"render_seconds":time.monotonic()-clock,"near_black_percent":100*float(np.mean(np.max(pixels,axis=2)<=24))}
        rendered.append(row);(out/"partial.json").write_text(json.dumps({"metrics":rec,"rendered":rendered},indent=2))
        print("SAYING_HI_RENDER_DONE",json.dumps(row),flush=True)
    report={"unit":unit,"sentence_ids":ids,"mode":a.mode,"variant":a.variant,"engine":"EEVEE","denoising":False,"eevee_spatial_samples":32,"rendered_temporal_samples_per_second":30 if a.mode=="motion" else None,"encoded_fps_target":30 if a.mode=="motion" else None,"actual_rendered_frames":len(rendered),"expected_rendered_frames":len(selected),"frame_window":[start,end],"scenery":driver.scenery,"metrics":rec,"rendered":rendered,"review":"candidate, visual and metric approval pending"}
    if unit=="crossing":
        report["stride"]=driver.lock.report();report["target_stop_error"]=(driver.lock.pos-driver.end).length
        report["calibration_candidate"]=driver.stride_candidate;report["stride_search"]=driver.stride_search;report["cross_camera"]=driver.cross_camera
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    assert len(rendered)==len(selected)
    if a.mode!="motion" and rendered:
        import shutil
        shutil.copyfile(out/rendered[0]["file"],out/"held_pose.png")
if __name__=="__main__":main()
