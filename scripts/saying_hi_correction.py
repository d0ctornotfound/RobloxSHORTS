"""Story-local correction geometry; locked chapter modules are imported, not edited.
All contact and visibility reports use evaluated meshes, at every 30 Hz sample.
"""
import math,json
import bpy
import numpy as np
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
from render_saying_hi_shot import SceneUnit,V,ease,clamp,frame,actor_points,show,FPS,mesh_points,bounds,cube,material,empty,project,group_tree,tree_for_object,hand_contact,carry_two,waffle_pose,seat_setup,neutral_feet,sit_pose,rear_hip,Articulation,ArticulatedClothes,Retarget,StrideLock,yaw_to
from saying_hi_contacts import surface_tree
from saying_hi_square import build_square

def meshes(root):
    return [o for o in [root]+list(root.children_recursive) if o.type=="MESH" and not o.hide_render]
def worldpts(objs):
    return [p for o in objs for p in mesh_points(o)]
def visible_ray(scene,cam,target,allowed):
    # Nearest scene hit, skip explicitly hidden render geometry. Perspective only.
    origin=cam.location.copy();v=target-origin;distance=v.length
    if distance<1e-6:return False
    direction=v.normalized();deps=bpy.context.evaluated_depsgraph_get()
    for _ in range(25):
        hit,p,_,_,ob,_=scene.ray_cast(deps,origin,direction,distance=distance+.005)
        if not hit:return True
        ob=ob.original
        if ob in allowed:return True
        if not ob.hide_render:return (p-target).length<.004
        origin=p+direction*.002;distance=(target-origin).dot(direction)
        if distance<=0:return True
    return False
def object_visibility(scene,cam,objs,grid=7):
    """Screen-silhouette ray samples. Compare nearest target BVH hit to actual
    nearest scene hit, so hidden/back vertices are not treated as occlusion."""
    pts=worldpts(objs);p=project(scene,cam,pts)
    trees=[tree_for_object(o) for o in objs];allowed=set(objs)
    f=cam.data.view_frame(scene=scene);xmin=min(v.x/v.z for v in f);xmax=max(v.x/v.z for v in f);ymin=min(v.y/v.z for v in f);ymax=max(v.y/v.z for v in f)
    # Blender camera local -Z; world_to_camera_view x,y increase to right/up.
    tested=blocked=0
    for x in np.linspace(p[0],p[1],grid):
        for y in np.linspace(p[2],p[3],grid):
            local=V((-(xmax-(xmax-xmin)*x),-(ymax-(ymax-ymin)*y),-1))
            ray=(cam.matrix_world.to_3x3()@local).normalized();origin=cam.location.copy()
            hits=[tree.ray_cast(origin,ray,1000) for tree in trees]
            hits=[h for h in hits if h[0] is not None]
            if not hits:continue
            target=min(hits,key=lambda h:h[3])[0];tested+=1
            blocked+=not visible_ray(scene,cam,target,allowed)
    safe=p[4]>0 and .035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965
    return {"samples":tested,"blocked":blocked,"bounds":list(p),"safe":bool(safe),"visible_fraction":1-blocked/tested if tested else 0}

def add_tallies():
    root=bpy.data.objects["Saying Hi story-local wall and seats"]
    mat=material("Wall tally charcoal",(.045,.029,.018));objs=[]
    # Four strokes + diagonal cross stroke, repeated along actual front face.
    for j in range(7):
        x=-3.60+j*1.20
        for i in range(4):
            objs.append(cube("wall tally %d-%d"%(j,i),(x-.12+i*.075,7.930,.24),(.019,.012,.19),mat,root,bevel=0))
        o=cube("wall tally %d slash"%j,(x-.008,7.921,.24),(.32,.012,.020),mat,root,bevel=0)
        o.rotation_euler.y=-.52;objs.append(o)
    bpy.context.view_layer.update()
    return objs

def collision_pairs(actors,fixtures):
    # Closed evaluated mesh overlap, including native rig body, head and clothing.
    # Broadphase avoids querying every irrelevant plaza mesh.
    pairs=0;detail=[]
    for a in actors:
        for o in meshes(a.root):
            if not o.data.polygons:continue
            lo,hi=bounds(mesh_points(o))
            for fixture in fixtures:
                flo,fhi=bounds(mesh_points(fixture))
                if any(hi[i]<flo[i] or fhi[i]<lo[i] for i in range(3)):continue
                n=len(tree_for_object(o).overlap(tree_for_object(fixture)))
                if n:detail.append([o.name,fixture.name,n]);pairs+=n
    return pairs,detail

def search_walk(actor,start,end,nframes,pickup):
    """Coarse search on interpolated evaluated local sole samples. Exact
    verification replays original StrideLock, no end snap, no root warp."""
    ret=Retarget(actor);duration=ret.clips["walk_cycle"]["duration"]
    lock=StrideLock(ret,"walk_cycle",FPS,.2,start,0)
    N=240;levels=np.array([0,.25,.5,.75,1.]);table=np.empty((5,N,2,3))
    for j,s in enumerate(levels):
        for i in range(N):
            table[j,i]=np.array([list(v) for v in lock.sample_local(i/N*duration/.2,float(s))])
        print("SOLE_TABLE",j,N,flush=True)
    movement=nframes-pickup;hold=4;dist=(end-start).length
    rates=np.arange(.135,.341,.0025);phases=np.arange(N)/N
    rr,pp=np.meshgrid(rates,phases,indexing="ij");rr=rr.ravel();pp=pp.ravel()
    predicted=[]
    for settle_len in (5,8,12,16,20,26,32):
        K=len(rr);pos=np.zeros((K,2));prev=None;support=None
        backward=np.zeros(K,dtype=int);rms=np.zeros(K);count=np.zeros(K);gap=np.zeros(K);lastspeed=np.zeros(K)
        for i in range(movement):
            settle=ease((i-(movement-hold-settle_len))/max(1,settle_len-1))
            phase=((pp+i*rr/(FPS*duration))%1)*N;ix=phase.astype(int);fx=(phase-ix)[:,None,None]
            j=min(3,int(settle*4));fy=settle*4-j
            local=(1-fy)*(table[j,ix]*(1-fx)+table[j,(ix+1)%N]*fx)+fy*(table[j+1,ix]*(1-fx)+table[j+1,(ix+1)%N]*fx)
            low=local[:,:,2].min(axis=1)
            if prev is None:support=local[:,:,2].argmin(axis=1)
            else:
                eligible=local[:,:,2]<=low[:,None]+.018
                score=(local[:,:,1]-prev[:,:,1])*FPS
                score[np.arange(K),support]+=.12;score[~eligible]=-1e8
                new=score.argmax(axis=1);delta=prev[np.arange(K),new,:2]-local[np.arange(K),new,:2]
                pos+=delta;lastspeed=-delta[:,1]*FPS;backward+=(lastspeed<-.01)
                same=new==support
                velocity=((local[np.arange(K),new,2]-low)-(prev[np.arange(K),new,2]-prev[:,:,2].min(axis=1)))*FPS
                rms+=same*velocity**2;count+=same;support=new
            gap=np.maximum(gap,local[np.arange(K),support,2]-low);prev=local
        foot=pos+local[np.arange(K),support,:2];error=abs(np.linalg.norm(foot,axis=1)-dist)
        rms=np.sqrt(rms/np.maximum(1,count));angles=np.arctan2(foot[:,0],-foot[:,1])
        penalty=error+backward*.10+np.maximum(0,rms-.03)*10+np.maximum(0,gap-.02)*5+np.maximum(0,abs(angles)-.24)*5
        idx=np.argsort(penalty)[:30]
        predicted.extend((float(penalty[i]),float(rr[i]),float(pp[i]),settle_len,float(error[i]),int(backward[i]),float(rms[i])) for i in idx)
    predicted.sort();actual=[];chosen=None
    # Exact verification on selected candidates. First compute local endpoint
    # using yaw zero, rotate to fixed destination, then replay with that yaw.
    def replay(rate,phase,settle_len,yaw):
        l=StrideLock(ret,"walk_cycle",FPS,rate,start,yaw);offset=phase*duration/rate
        for i in range(movement):
            s=ease((i-(movement-hold-settle_len))/max(1,settle_len-1))
            l.step(offset+i/FPS,settle=s)
        return l
    for _,rate,phase,settle_len,pe,pb,pr in predicted[:24]:
        l=replay(rate,phase,settle_len,0);last=l.records[-1];d=V(last["contact_world"])-start
        yaw=yaw_to(start,end)-math.atan2(d.x,-d.y)
        yaw=(yaw+math.pi)%(2*math.pi)-math.pi
        # Rotation preserves the exact support calculation; endpoint analytically
        # rotated about the fixed start, then one final real replay is required.
        contact=start+Matrix.Rotation(yaw,3,"Z")@d;err=(contact-end).length
        report=l.report();allback=sum(x["forward_speed"]<-.01 for x in l.records)
        rows=[x for x in l.records if x["continuing"]]
        allrms=math.sqrt(sum(x["velocity"]**2 for x in rows)/len(rows))
        last4=l.records[-hold:];drift=max((V(x["contact_world"])-V(last4[-1]["contact_world"])).length for x in last4)
        row={"rate":rate,"phase":phase,"settle_frames":settle_len,"hold_frames":hold,"yaw":yaw,"predicted_error":pe,"stop_error":err,"locked_pass":report["pass"],"backward_frames":allback,"stance_rms":allrms,"settled_contact_drift":drift,"max_contact_gap":report["max_contact_gap"],"locked_stance_rms":report["stance_velocity_rms"],"final_support":last["support"]}
        row["pass"]=report["pass"] and allback==0 and allrms<=.03 and err<=.05 and abs(yaw)<=.24 and drift<=.005
        actual.append(row);print("EXACT_STOP",json.dumps(row),flush=True)
        if row["pass"]:chosen=row;break
    if chosen is None:chosen=min(actual,key=lambda q:(not q["locked_pass"],q["backward_frames"],max(0,q["stance_rms"]-.03),q["stop_error"]))
    return chosen,actual,ret

class CorrectedUnit(SceneUnit):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not self.chart_mode:
            self.tallies=add_tallies()
            if self.unit=="empty_wall":
                # Actual front of the north wall; no actors in this beat.
                frame(self.scene,self.cam,(0,3.9,1.35),(0,8.05,.29),22)
    def prepare_stride(self,nframes):
        self.move_frames=nframes-self.pickup_frames
        best,rows,ret=search_walk(self.a,self.start,self.end,nframes,self.pickup_frames)
        self.stride_candidate=best;self.stride_search=rows;self.yaw=best["yaw"]
        self.stride_offset=best["phase"]*ret.clips["walk_cycle"]["duration"]/best["rate"]
        self.lock=StrideLock(ret,"walk_cycle",FPS,best["rate"],self.start,self.yaw)
        self.settle_len=best["settle_frames"];self.hold=best["hold_frames"]
        for cid in self.stage["layouts"]["initial"]["wall"]+self.stage["layouts"]["initial"]["well"]:
            if cid!="narrator":self.seat(cid)
        # Lower fixed perspective camera, frame complete wall and fountain plus
        # route envelope. The spectators remain on their original marks.
        wall=bpy.data.objects["tally wall"];well=bpy.data.objects["Piazza fountain"]
        anchors=worldpts([wall]+meshes(well))
        for p in (self.start,self.end):
            anchors.extend(p+V((x,y,z)) for x in (-.72,.72) for y in (-.50,.50) for z in (0,2.35))
        target=V((0,4.1,1.05));choices=[]
        for x in (-6.,-4.,-2.,0.,2.,4.,6.):
            for y in (-8.,-6.,-4.):
                for z in (2.6,3.3,4.1,5.0):
                    loc=V((x,y,z))
                    for lens in (20,24,28,32,36):
                        frame(self.scene,self.cam,loc,target,lens)
                        b=project(self.scene,self.cam,anchors)
                        if b[4]<=0 or not (.035<=b[0]<=b[1]<=.965 and .035<=b[2]<=b[3]<=.965):continue
                        cov=min(project(self.scene,self.cam,[p,p+V((0,0,2.28))])[3]-project(self.scene,self.cam,[p,p+V((0,0,2.28))])[2] for p in (self.start,self.end))
                        # Penalize large height and reward coverage, no geography change.
                        choices.append((cov-.003*z,cov,loc.copy(),lens,list(b)))
        if not choices:
            frame(self.scene,self.cam,(0,-9,4),(0,4,1.05),20)
            self.cross_camera={"candidate_found":False,"min_vertical_coverage":0}
        else:
            _,cov,loc,lens,b=max(choices,key=lambda q:q[0]);frame(self.scene,self.cam,loc,target,lens)
            self.cross_camera={"candidate_found":True,"position":list(loc),"target":list(target),"lens":lens,"geography_bounds":b,"min_vertical_coverage":cov}
    def update_crossing(self,index,u,t):
        # Keep original pickup and dual-prop carry, but use the exact solved
        # settle schedule rather than the old hard-coded ten-frame blend.
        if index<self.pickup_frames:return super().update_crossing(index,u,t)
        a=self.a;k=index-self.pickup_frames
        s=ease((k-(self.move_frames-self.hold-self.settle_len))/max(1,self.settle_len-1))
        self.lock.step(self.stride_offset+k/FPS,settle=s);a.pose("worried" if k<self.move_frames*.75 else "neutral")
        show(self.chart,True);show(self.pencil,True)
        a.aim_arm(0,(.18,-.64,-.79));a.aim_arm(1,(-.20,-.40,-.92));bpy.context.view_layer.update()
        attachment=carry_two(self.chart,self.pencil,a.grips[1],a.grips[0])
        self.chart.rotation_euler=(0,0,self.yaw);self.pencil.rotation_euler=(.15,0,self.yaw);bpy.context.view_layer.update()
        row=self.lock.records[-1];support=V(row["contact_world"]);own=set(meshes(a.root))
        # Check the actual support foot slightly above the contact plane; the
        # ground itself is permitted at the exact contact point.
        foot_visible=visible_ray(self.scene,self.cam,support+V((0,0,.07)),own)
        box=project(self.scene,self.cam,actor_points(a))
        return {"phase":"carry","socket_alignment":attachment,"chart_contact":hand_contact(a,1,self.chart),"pencil_contact":hand_contact(a,0,self.pencil),"stride":row,"foot_visible":foot_visible,"actor_bounds":list(box)}
    def setup_eyes(self):
        super().setup_eyes();self.eye_solution=None
    def eyes_pose(self,u,t,params):
        a=self.place("otis",self.eye_pos,0,"worried",t=t);self.eye_art.rigid()
        lo,hi=bounds(mesh_points(a.head));center=(lo+hi)/2;w=ease(min(1,u*2.2))
        dx,offset,z,polex,poley=params;res=[]
        head=tree_for_object(a.head)
        for i,limb in enumerate(self.eye_art.arms):
            sign=(-1,1)[i]
            target=V((center.x+sign*dx,lo.y-offset,center.z+z))
            rest=limb.lower.matrix_world@V((0,0,-limb.b));target=rest.lerp(target,w)
            end=self.eye_art.arm_target(i,target,V((sign*polex,poley,-.45)),0)
            parts=[limb.upper,limb.lower]
            pairs=sum(len(head.overlap(tree_for_object(o))) for o in parts)
            res.append({"hand_target_gap":(end-target).length,"head_arm_overlap_pairs":pairs,"upper_overlap":len(head.overlap(tree_for_object(limb.upper))),"lower_overlap":len(head.overlap(tree_for_object(limb.lower)))})
        self.eye_clothes.sync()
        # Eye rays toward the actual visible face; require both eye locations
        # blocked by the gesture, not merely an arbitrary hands-raised pose.
        fp=mesh_points(a.face);fl,fh=bounds(fp);mid=(fl+fh)/2
        arms=[tree_for_object(o) for l in self.eye_art.arms for o in l.objects]
        covered=0
        for sign in (-1,1):
            p=V((mid.x+sign*(fh.x-fl.x)*.22,mid.y,mid.z+(fh.z-fl.z)*.14))
            ray=p-self.cam.location;covered+=any(tr.ray_cast(self.cam.location,ray.normalized(),ray.length-.005)[0] is not None for tr in arms)
        return {"eyes":res,"coverage_progress":w,"eye_samples_covered":covered}
    def update_eyes(self,u,t):
        if self.eye_solution is None:
            candidates=[]
            for dx in (.07,.12,.17,.22):
                for offset in (.22,.28,.34,.40,.48,.55):
                    for z in (.04,.10,.16):
                        for px,py in ((1,-.25),(1,-.8),(.4,-1.0)):
                            p=(dx,offset,z,px,py);m=self.eyes_pose(1,.8,p)
                            overlap=sum(x["head_arm_overlap_pairs"] for x in m["eyes"]);gap=max(x["hand_target_gap"] for x in m["eyes"])
                            candidates.append((overlap,2-m["eye_samples_covered"],gap,p))
            candidates.sort();tested=[]
            for _,_,_,p in candidates[:16]:
                ms=[self.eyes_pose(i/29,i/30,p) for i in range(30)]
                pairs=max(x["head_arm_overlap_pairs"] for m in ms for x in m["eyes"])
                coverage=min(m["eye_samples_covered"] for m in ms if m["coverage_progress"]>.99)
                row={"params":p,"max_head_intersections":pairs,"covered_eye_samples":coverage};tested.append(row)
                if pairs==0 and coverage==2:self.eye_solution=p;break
            if self.eye_solution is None:self.eye_solution=min(tested,key=lambda x:(x["max_head_intersections"],-x["covered_eye_samples"]))["params"]
            self.eye_search=tested;print("EYE_SEARCH",json.dumps(tested),flush=True)
        return self.eyes_pose(u,t,self.eye_solution)
    def setup_june(self):
        # Separate standing interview marks from the fixed well seats, no
        # relocation of wall or well. Use the permanent bench as nearby seat.
        self.jp=V((4.65,-1.75,0));self.np=V((4.65,.35,0));self.jyaw=yaw_to(self.jp,self.np);self.nyaw=yaw_to(self.np,self.jp)
        a=self.place("narrator",self.np,self.nyaw,"worried");b=self.place("june",self.jp,self.jyaw,"happy")
        # Seat placement helper calibrates actual support dimensions, then put
        # the unoccupied interview seat behind June, outside both body envelopes.
        temp=Articulation(b,legs=True,arms=False);feet=neutral_feet(b,temp,self.jyaw);s=seat_setup(b,temp,self.jyaw,feet)
        # Remove only this disposable articulated actor and reconstruct original
        # standing body to retain locked geometry for the interview.
        for o in list(b.root.children_recursive)+[b.root]+[o for l in temp.legs for o in l.objects]:
            if o.name in bpy.data.objects:bpy.data.objects.remove(o,do_unlink=True)
        del self.actors["june"];b=self.place("june",self.jp,self.jyaw,"happy")
        root=bpy.data.objects["Saying Hi story-local wall and seats"]
        # Existing well_June fixture is calibrated with the helper, not an
        # arbitrary replacement geometry. Keep it near its original mark.
        seat=bpy.data.objects["seat june"];seat.dimensions=(s[2][0],s[2][1],.11)
        seat.location=(3.12,-.70,s[0]-.055);seat.rotation_euler.z=self.jyaw
        ped=bpy.data.objects["pedestal june"];ped.location=(3.12,-.70,(s[0]-.11)/2);ped.dimensions=(.40,.37,s[0]-.11)
        self.interview_fixtures=[o for o in meshes(root) if o.name.startswith(("seat ","pedestal ","Actual pair seat","Pair bench leg"))]
        # Side-on reverse with both faces and the raised pencil on the near side.
        if self.unit=="june_question":loc=(1.7,1.65,1.85);aim=(4.65,-.20,1.43);lens=38
        else:loc=(1.7,-3.1,1.85);aim=(4.65,-1.0,1.43);lens=38
        frame(self.scene,self.cam,loc,aim,lens);self.reverse_camera={"location":list(loc),"target":list(aim),"lens":lens}
    def update_june(self,n,u,t):
        m=super().update_june(n,u,t)
        a=self.actors["narrator"];b=self.actors["june"]
        pairs,detail=collision_pairs([a,b],self.interview_fixtures)
        m["standing_seat_intersections"]=pairs;m["seat_overlap_detail"]=detail
        hero=a if self.unit=="june_question" else b
        m["speaker_visibility"]=object_visibility(self.scene,self.cam,[hero.face],5)
        if self.unit=="june_question":
            m["pencil_visibility"]=object_visibility(self.scene,self.cam,meshes(self.pencil),9)
        return m
    def setup_seating(self):
        super().setup_seating()
        # Move only dog/shot camera, not the plaza. Foreground of bench, away
        # from all original ring fixtures. Camera faces pair from clear side.
        self.dog[0].location=(4.20,-.82,0)
        frame(self.scene,self.cam,(2.0,-.86,2.25),(4.95,-.87,1.05),31)
        self.prev_hip={}
    def update_seating(self,n,u,t,after_name=True):
        # Keep June's pelvis/feet on the calibrated final mark. Her welcoming
        # movement is a head/torso gesture, not a root or foot slide.
        records={}
        for cid,item in self.seat_data.items():
            a,art,cloth,feet,seat,pos,yaw=item
            f=ease(clamp((u-.20)/.75)) if n==43 and cid=="narrator" else 0 if n==42 and cid=="narrator" else 1
            sit_pose(a,art,"sit",f,t,yaw,feet,None,seat);art.shift(pos);cloth.sync()
            a.pose("happy");a.set_bone("head",(.035*math.sin(t*4) if cid=="june" else 0,0,.12 if cid=="june" else -.12))
            soles=art.soles();old=self.prev_feet.get(cid);hip=(a.armature.matrix_world@a.bones["torso"].matrix).translation
            if cid not in self.prev_hip:self.prev_hip[cid]=hip.copy()
            records[cid]={"seated_fraction_command":f,"signed_rear_hip_gap":float(rear_hip(a)[0]-self.bench_top),"signed_foot_gaps":[float(v.z) for v in soles],"foot_step_drift":[float((v-w).length) for v,w in zip(soles,old)] if old else None,"lateral_hip_drift":abs((hip-self.prev_hip[cid]).y)}
            self.prev_feet[cid]=[v.copy() for v in soles]
        visible=n!=42 or after_name;show(self.dog[0],visible)
        dog_metric=waffle_pose(self.dog,"roll_over" if n==43 else "lie_down",ease(u)) if visible else None
        return {"seat_top":self.bench_top,"seat_contacts":records,"waffle":dog_metric,"dog_visible":visible,"dog_visibility":object_visibility(self.scene,self.cam,meshes(self.dog[0]),11) if visible else None,"note":"June stays on the planted calibrated mark; head/torso welcome rather than sliding feet."}
    def update(self,n,u,t,index,after_name=True):
        if self.unit=="empty_wall":
            return {"tally_count":len(self.tallies),"wall_visibility":object_visibility(self.scene,self.cam,[bpy.data.objects["tally wall"]],9),"tally_visibility":object_visibility(self.scene,self.cam,self.tallies,15),"boys_on_wall":len(self.actors)}
        return super().update(n,u,t,index,after_name)
