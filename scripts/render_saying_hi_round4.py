"""Round 4 isolated proof driver; immutable Chapter 1–4 sources.
All-frame measures precede smoke/native rendering. No fallback still motion."""
import math,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Matrix
from render_saying_hi_shot import SceneUnit,V,FPS,frame,actor_points,project,Retarget,StrideLock,yaw_to,show,cube,material,ROOT,rear_hip,mesh_points,group_points
from saying_hi_correction import CorrectedUnit,meshes,worldpts,visible_ray,object_visibility
from render_saying_hi_round3 import Round3Unit,evaluate_gate as round3_gate
import render_saying_hi_correction as runner

def safe(p):
    return p[4]>0 and .035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965
def diag_path(unit):
    return ROOT/"assets/saying_hi_review/corrections/round3_precheck_retry1"/unit/"geometry.json"
def old_face_diagnostics(unit):
    g=json.loads(diag_path(unit).read_text())
    return [{"global_frame":r["global_frame"],"local_frame":r["global_frame"]-g["frame_window"][0],"blocked":r["metrics"]["speaker_visibility"]["blocked"],"objects":r["metrics"]["speaker_visibility"]["blockers"]} for r in g["metrics"] if r["metrics"]["speaker_visibility"]["blocked"]]

class Round4Unit(Round3Unit):
    def prepare_stride(self,nframes):
        self.move_frames=nframes-self.pickup_frames
        ret=Retarget(self.a);duration=ret.clips["walk_cycle"]["duration"]
        original=self.end.copy();route=(original-self.start).normalized();yaw=yaw_to(self.start,original)
        rate=duration*FPS/(self.move_frames-1)
        choices=[]
        for i in range(48):
            phase=i/48;offset=phase*duration/rate
            lock=StrideLock(ret,"walk_cycle",FPS,rate,self.start,yaw)
            # Same-foot support contact, actual evaluated sole proxy, one
            # complete imported cycle. First/last support must be the same.
            for k in range(self.move_frames):lock.step(offset+k/FPS,settle=0)
            rs=lock.records;r=lock.report();first=V(rs[0]["contact_world"]);last=V(rs[-1]["contact_world"])
            displacement=last-first;stride=displacement.dot(route)
            same=rs[0]["support"]==rs[-1]["support"]
            final_plant=rs[-1]["support"]!=rs[-2]["support"]
            mark=self.start+route*stride
            sole=(last-mark).length;root=(V((lock.pos.x,lock.pos.y,mark.z))-mark).length
            row={"rate":rate,"phase":phase,"yaw":yaw,"settle_frames":0,"hold_frames":1,"cycle_count":1,"stride_length":stride,"stride_source":"same-foot evaluated support-point displacement projected along route","start_support":list(first),"end_support":list(last),"support_displacement":list(displacement),"destination":list(mark),"original_destination":list(original),"root_stop_error_xy":root,"planted_stop_error":sole,"final_support":rs[-1]["support"],"start_support_index":rs[0]["support"],"same_foot":same,"final_plant":final_plant,"final_contact_gap":abs(rs[-1]["contact_gap"]),"locked_pass":r["pass"],"backward_frames":r["backward_frames"],"stance_rms":r["stance_velocity_rms"],"max_contact_gap":r["max_contact_gap"]}
            row["pass"]=same and final_plant and r["pass"] and r["backward_frames"]==0 and r["stance_velocity_rms"]<=.03 and r["max_contact_gap"]<=.02 and root<=.05 and sole<=.05 and stride>0
            choices.append(row);print("PLANTED_STRIDE",json.dumps(row),flush=True)
        best=min(choices,key=lambda q:(not q["pass"],not(q["same_foot"] and q["final_plant"]),q["backward_frames"],max(0,q["stance_rms"]-.03),q["planted_stop_error"]+q["root_stop_error_xy"]))
        self.stride_candidate=best;self.stride_search=choices;self.end=V(best["destination"]);self.yaw=yaw;self.stride_offset=best["phase"]*duration/rate
        self.settle_len=0;self.hold=1;self.lock=self.new_walk_lock(ret)
        for cid in self.stage["layouts"]["initial"]["wall"]+self.stage["layouts"]["initial"]["well"]:
            if cid!="narrator":self.seat(cid)
        wall=bpy.data.objects["tally wall"];well=bpy.data.objects["Piazza fountain"]
        anchors=[o.matrix_world@V(v) for o in [wall]+meshes(well) for v in o.bound_box]
        for p in (self.start,self.end):
            anchors.extend(p+V((x,y,z)) for x in (-.72,.72) for y in (-.50,.50) for z in (0,2.35))
        candidates=[]
        for x in (-8,-6,-4,-2,0,2,4,6,8):
            for y in (-10,-7,-4,-2,0,2,4,6,10):
                for z in (1.35,1.75,2.15,2.6,3.0):
                    loc=V((x,y,z))
                    for tz in (.65,1.0,1.35,1.65):
                        target=V((0,4,tz))
                        if (loc-target).length<1:continue
                        frame(self.scene,self.cam,loc,target,30);b=project(self.scene,self.cam,anchors)
                        if b[4]<=0:continue
                        lens=30*.46/max(.01,max(abs(v-.5) for v in b[:4]))
                        if not 10<=lens<=85:continue
                        frame(self.scene,self.cam,loc,target,lens);b=project(self.scene,self.cam,anchors)
                        if not (.035<=b[0]<=b[1]<=.965 and .035<=b[2]<=b[3]<=.965):continue
                        cov=min((lambda p:p[3]-p[2])(project(self.scene,self.cam,[self.start.lerp(self.end,u),self.start.lerp(self.end,u)+V((0,0,2.28))])) for u in (0,.25,.5,.75,1))
                        candidates.append((cov,loc.copy(),target.copy(),lens,list(b)))
        own=set(meshes(self.a.root));checked=[]
        for cov,loc,target,lens,b in sorted(candidates,key=lambda q:-q[0])[:120]:
            frame(self.scene,self.cam,loc,target,lens)
            blocked=sum(not visible_ray(self.scene,self.cam,self.start.lerp(self.end,u)+V((0,0,.10)),own) for u in (0,.125,.25,.375,.5,.625,.75,.875,1))
            checked.append({"position":list(loc),"target":list(target),"lens":lens,"geography_bounds":b,"min_vertical_coverage":cov,"setup_blocked_route_rays":blocked})
        if checked:
            q=min(checked,key=lambda q:(q["setup_blocked_route_rays"]>0,q["min_vertical_coverage"]<.25,q["setup_blocked_route_rays"],-q["min_vertical_coverage"]))
            frame(self.scene,self.cam,q["position"],q["target"],q["lens"])
            self.cross_camera={"candidate_found":True,**q,"framing_candidates":checked}
        else:
            frame(self.scene,self.cam,(0,-9,4),(0,4,1.05),20)
            self.cross_camera={"candidate_found":False,"min_vertical_coverage":0,"framing_candidates":[]}
        # A second FIXED camera tests the last third independently. No
        # motion substitution; wide and low results are separately reported.
        self.low_start=self.pickup_frames+2*(self.move_frames-1)//3
        p=self.start.lerp(self.end,2/3);target=(p+self.end)/2+V((0,0,1.05))
        low=[]
        for x in (-4,-3,-2,2,3,4):
            for dy in (-2,0,2):
                loc=target+V((x,dy,-.35))
                for lens in (22,28,35,40):
                    frame(self.scene,self.cam,loc,target,lens)
                    pts=[q+V((a,b,z)) for q in (p,self.end) for a in (-.65,.65) for b in (-.45,.45) for z in (0,2.35)]
                    bounds=project(self.scene,self.cam,pts)
                    if not safe(bounds):continue
                    cov=min((lambda b:b[3]-b[2])(project(self.scene,self.cam,[q,q+V((0,0,2.28))])) for q in (p,self.end))
                    blocked=sum(not visible_ray(self.scene,self.cam,p.lerp(self.end,u)+V((0,0,.07)),own) for u in (0,.25,.5,.75,1))
                    low.append((blocked,-cov,{"position":list(loc),"target":list(target),"lens":lens,"setup_coverage":cov,"setup_blocked":blocked}))
        self.low_camera=min(low,key=lambda q:q[:2])[2] if low else {"position":list(target+V((3,0,-.35))),"target":list(target),"lens":28,"setup_coverage":0,"setup_blocked":-1}
        q=self.cross_camera
        if q["candidate_found"]:frame(self.scene,self.cam,q["position"],q["target"],q["lens"])
        self.master_matrix=self.cam.matrix_world.copy();self.master_lens=self.cam.data.lens
    def update_crossing(self,index,u,t):
        m=super().update_crossing(index,u,t)
        if index>=self.low_start:
            q=self.low_camera;frame(self.scene,self.cam,q["position"],q["target"],q["lens"])
            support=V(self.lock.records[-1]["contact_world"])
            m["low_camera"]={"actor_bounds":list(project(self.scene,self.cam,actor_points(self.a))),"foot_visible":visible_ray(self.scene,self.cam,support+V((0,0,.07)),set(meshes(self.a.root)))}
            self.cam.matrix_world=self.master_matrix.copy();self.cam.data.lens=self.master_lens;bpy.context.view_layer.update()
        return m
    def setup_june(self):
        # Audit prior evaluated face-ray records BEFORE changing the marks.
        self.inherited_face_failures=old_face_diagnostics(self.unit)
        print("INHERITED_FACE_FAILURES",json.dumps(self.inherited_face_failures),flush=True)
        old=json.loads((diag_path(self.unit).parent/"gate.json").read_text())["camera"]
        cached=self.reviewed_camera
        self.reviewed_camera=old
        CorrectedUnit.setup_june(self)
        a=self.actors["narrator"];b=self.actors["june"];hero=a if self.unit=="june_question" else b
        original_yaw=self.nyaw if hero==a else self.jyaw
        if hero==a:self.nyaw=original_yaw+math.radians(20)
        if cached and "mark_yaw_deg" in cached:
            if hero==a:self.nyaw=math.radians(cached["mark_yaw_deg"])
            else:self.jyaw=math.radians(cached["mark_yaw_deg"])
            frame(self.scene,self.cam,cached["location"],cached["target"],cached["lens"]);self.reverse_camera=cached;return
        base=V(old["location"]);target=V(old["target"]);candidates=[]
        n=32 if hero==a else 34
        # Small same-axis changes first; slightly wider safe framing is
        # permitted, not a face/prop visibility exception.
        for dx in (0,.08,-.08,.16,-.16,.30,-.30):
            for dz in (0,-.10,.10,-.20,.20,-.35):
                for scale in (1,.94,.88,.80):
                    loc=base+V((dx,0,dz));lens=old["lens"]*scale
                    frame(self.scene,self.cam,loc,target,lens)
                    m=self.update_june(n,.5,.45)
                    score=self.single_score([m],hero==a)
                    candidates.append((score,abs(dx)+abs(dz)+abs(1-scale),loc.copy(),lens))
        choices=[]
        for _,cost,loc,lens in sorted(candidates,key=lambda x:(x[0],x[1]))[:22]:
            frame(self.scene,self.cam,loc,target,lens)
            rows=[self.update_june(n,u,t) for u,t in ((0,0),(.25,.3),(.5,.45),(.75,.95),(1,1.7),(1,3.4))]
            choices.append((self.single_score(rows,hero==a),cost,loc.copy(),lens))
        score,cost,loc,lens=min(choices,key=lambda x:(x[0],x[1]))
        frame(self.scene,self.cam,loc,target,lens)
        self.reverse_camera={"location":list(loc),"target":list(target),"lens":lens,"mark_yaw_deg":math.degrees(self.nyaw if hero==a else self.jyaw),"camera_shift":list(loc-base),"candidate_score":list(score),"world_x_side":"positive","inherited_face_failures":self.inherited_face_failures}
    def single_score(self,rows,question):
        b=max(m["speaker_visibility"]["blocked"] for m in rows)
        safeall=all(m["speaker_visibility"]["safe"] and m["speaker_body_visibility"]["safe"] for m in rows)
        dot=min(m["speaker_front_dot"] for m in rows);body=min(m["speaker_body_visibility"]["visible_fraction"] for m in rows)
        out=(not safeall,b,max(0,.72-dot),max(0,.90-body),max(m["standing_seat_intersections"] for m in rows),max(m["foreground_intrusion"]["blocked"] for m in rows))
        if question:out+=(not all(m["pencil_external_visibility"]["safe"] for m in rows),max(m["pencil_external_visibility"]["blocked"] for m in rows),max(0,.8421052631578947-min(m["pencil_visibility"]["visible_fraction"] for m in rows)))
        return out
    def setup_seating(self):
        # Named actual raised bench beside the original fountain, not stools.
        # Change only the local seating shot marks and its support geometry.
        self.marks={**self.marks,"june_seat":{**self.marks["june_seat"],"xyz":[3,-.92,0],"yaw_deg":90},"narrator_seat":{**self.marks["narrator_seat"],"xyz":[3,.92,0],"yaw_deg":90},"waffle":{**self.marks["waffle"],"xyz":[3.9,0,0],"yaw_deg":90}}
        SceneUnit.setup_seating(self);self.prev_phase={}
        root=bpy.data.objects["Saying Hi story-local wall and seats"]
        # Remove shot-local café stool fixtures; preserve fountain and wall.
        for o in meshes(root):
            if o.name.startswith(("seat ","pedestal ","Pair bench leg")):show(o,False)
        self.bench.name="Round4 fountain-side raised bench"
        self.bench.location=(self.bench_center.x,0,self.bench_top-.07)
        self.bench.dimensions=(.85,3.35,.14)
        trim=material("Round4 stone bench support",(.47,.39,.28))
        self.seat_supports=[cube("Round4 fountain bench support "+str(i),(self.bench.location.x,y,(self.bench_top-.14)/2),(.63,.28,self.bench_top-.14),trim,root,bevel=.015) for i,y in enumerate((-1.35,1.35))]
        bpy.context.view_layer.update()
        if self.reviewed_camera:
            q=self.reviewed_camera;self.dog[0].location=q["dog_mark"];frame(self.scene,self.cam,q["position"],q["target"],q["lens"]);self.payoff_camera=q
            self.prev_feet={};self.prev_hip={};self.prev_phase={};return
        target=V((3.05,0,1.05));options=[]
        for x in (7,8,9,10):
            for y in (-1.5,-.75,0,.75,1.5):
                for z in (1.35,1.65):
                    for lens in (35,40,45,50):
                        loc=V((x,y,z));frame(self.scene,self.cam,loc,target,lens)
                        self.dog[0].location=(3.9,0,0)
                        self.prev_feet={};self.prev_hip={};self.prev_phase={}
                        m=self.update_seating(43,1,1)
                        score=self.seat_score([m])
                        options.append((score,loc.copy(),lens))
        checked=[]
        for _,loc,lens in sorted(options,key=lambda q:q[0])[:18]:
            frame(self.scene,self.cam,loc,target,lens)
            for mark in ((3.9,0,0),(4.2,0,0),(4,-.35,0),(4,.35,0)):
                self.dog[0].location=mark;rows=[]
                for u in (0,.24,.4,.57,.75,1):
                    self.prev_feet={};self.prev_hip={};self.prev_phase={}
                    rows.append(self.update_seating(43,u,u))
                checked.append((self.seat_score(rows),loc.copy(),lens,mark))
        _,loc,lens,mark=min(checked,key=lambda q:q[0]);self.dog[0].location=mark;frame(self.scene,self.cam,loc,target,lens)
        self.payoff_camera={"position":list(loc),"target":list(target),"lens":lens,"dog_mark":list(mark),"support":self.bench.name,"seat_kind":"raised_bench","seat_top":self.bench_top,"support_objects":[o.name for o in self.seat_supports]}
        self.prev_feet={};self.prev_hip={};self.prev_phase={}
    def update_seating(self,n,u,t,after_name=True):
        m=CorrectedUnit.update_seating(self,n,u,t,after_name)
        if not hasattr(self,"seat_supports"):return m
        m["readability_faces"]={cid:{"visibility":object_visibility(self.scene,self.cam,[a.face],7),"facing_dot":self.front_dot(a)} for cid,a in self.actors.items()}
        seat=object_visibility(self.scene,self.cam,[self.bench],9)
        supports=[object_visibility(self.scene,self.cam,[o],7) for o in self.seat_supports]
        inv=self.bench.matrix_world.inverted(); bb=[V(v) for v in self.bench.bound_box]
        lo=[min(v[i] for v in bb) for i in range(3)];hi=[max(v[i] for v in bb) for i in range(3)]
        on={}
        for cid,a in self.actors.items():
            pts=group_points(a.body,a.bones["torso"].name);z=rear_hip(a)[0]
            bottom=[inv@p for p in pts if p.z<=z+.035]
            on[cid]=bool(bottom) and all(lo[0]-.015<=p.x<=hi[0]+.015 and lo[1]-.015<=p.y<=hi[1]+.015 for p in bottom)
        m["seat_readability"]={"name":self.bench.name,"kind":"raised_bench","surface":seat,"supports":supports,"hips_over_surface":on,"raised_height":self.bench_top,"support_reaches_ground":all(abs(o.location.z-o.dimensions.z/2)<.002 for o in self.seat_supports),"surface_horizontal":abs(self.bench.rotation_euler.x)+abs(self.bench.rotation_euler.y)<1e-6}
        return m
    def seat_score(self,rows):
        settled=[m for m in rows if all(x["phase"]=="seated" for x in m["seat_contacts"].values())]
        faces=[f for m in settled for f in m["readability_faces"].values()]
        dog=[m["dog_visibility"] for m in rows]
        seats=[m["seat_readability"] for m in settled]
        return (not all(safe(p) for m in rows for p in m["actor_bounds"].values()),max((f["visibility"]["blocked"] for f in faces),default=999),max(0,.5-min((f["facing_dot"] for f in faces),default=-1)),not all(f["visibility"]["safe"] for f in faces),not all(all(s["hips_over_surface"].values()) for s in seats),not all(s["surface"]["safe"] and s["surface"]["visible_fraction"]>0 and any(v["visible_fraction"]>0 and v["safe"] for v in s["supports"]) for s in seats),max(d["blocked"] for d in dog),not all(d["safe"] for d in dog),max(0,.12-min(d["bounds"][1]-d["bounds"][0] for d in dog)),max(0,.055-min(d["bounds"][3]-d["bounds"][2] for d in dog)))

def evaluate_gate(unit,driver,rows):
    g=round3_gate(unit,driver,rows);checks=g["checks"];ms=[r["metrics"] for r in rows]
    def add(k,v,lim,ok):checks[k]={"value":v,"limit":lim,"pass":bool(ok)}
    if unit=="crossing":
        s=driver.stride_candidate
        add("same_foot_full_cycle",s["same_foot"],True,s["same_foot"]);add("final_sample_is_plant",s["final_plant"],True,s["final_plant"])
        gap=max(abs(x["contact_gap"]) for x in driver.lock.records);add("max_contact_gap",gap,.02,gap<=.02)
        low=[m["low_camera"] for m in ms if "low_camera" in m];cov=min((x["actor_bounds"][3]-x["actor_bounds"][2] for x in low),default=0);blocked=sum(not x["foot_visible"] for x in low)
        g["low_camera"]={**driver.low_camera,"samples":len(low),"coverage":cov,"blocked_support_rays":blocked,"full_body_safe":bool(low) and all(safe(x["actor_bounds"]) for x in low),"pass":bool(low) and cov>=.25 and blocked==0 and all(safe(x["actor_bounds"]) for x in low)}
        # Keep original single-camera gates for now; split-camera native
        # release requires separate verified clips, not silent waiver.
    if unit in ("june_question","june_answer"):
        g["inherited_face_failures"]=driver.inherited_face_failures
        g["remaining_face_failures"]=[{"global_frame":r["global_frame"],"blocked":r["metrics"]["speaker_visibility"]["blocked"],"objects":r["metrics"]["speaker_visibility"]["blockers"]} for r in rows if r["metrics"]["speaker_visibility"]["blocked"]]
        if unit=="june_question":
            v=checks["visible_pencil_fraction"]["value"];add("round3_pencil_nonregression",v,.8421052631578947,v>=.8421052631578947)
    if unit=="seating":
        settled=[m for m in ms if all(x["phase"]=="seated" for x in m["seat_contacts"].values())]
        g["settled_samples"]=len(settled)
        for cid in ("june","narrator"):
            fs=[m["readability_faces"][cid] for m in settled]
            b=max((f["visibility"]["blocked"] for f in fs),default=999);dot=min((f["facing_dot"] for f in fs),default=-1)
            add(cid+"_settled_face_occlusion",b,0,bool(fs) and b==0 and all(f["visibility"]["samples"]>0 and f["visibility"]["safe"] for f in fs))
            add(cid+"_settled_facing_dot",dot,.5,dot>=.5)
        ss=[m["seat_readability"] for m in settled]
        legible=bool(ss) and all(s["kind"]=="raised_bench" and s["raised_height"]>.14 and s["support_reaches_ground"] and s["surface_horizontal"] and s["surface"]["safe"] and s["surface"]["visible_fraction"]>0 and any(v["safe"] and v["visible_fraction"]>0 for v in s["supports"]) and all(s["hips_over_surface"].values()) for s in ss)
        add("named_supported_seat_legibility",legible,True,legible);g["seat_readability_settled"]=ss
    g["pass"]=all(x["pass"] for x in checks.values());return g
if __name__=="__main__":
    runner.CorrectedUnit=Round4Unit;runner.evaluate_gate=evaluate_gate;runner.main()
