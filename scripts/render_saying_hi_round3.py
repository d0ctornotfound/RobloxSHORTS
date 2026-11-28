"""Round 3 story-local proof candidate. No locked implementation edits.
Only changed units may use this driver; existing native clips stay immutable.
"""
import math,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Matrix
from render_saying_hi_shot import SceneUnit,V,FPS,frame,actor_points,project,Retarget,StrideLock,yaw_to,show,cube,material
from saying_hi_correction import CorrectedUnit,meshes,worldpts,visible_ray,object_visibility
import render_saying_hi_correction as runner

class Round3Unit(CorrectedUnit):
    def prepare_stride(self,nframes):
        # The edit window is fixed. Quantize the previous slow production
        # playback rate to one complete imported cycle on the 30 Hz grid.
        # No fitting to old destination, no settling, no root snap.
        self.move_frames=nframes-self.pickup_frames
        ret=Retarget(self.a);duration=ret.clips["walk_cycle"]["duration"]
        intervals=self.move_frames-1
        rate=duration*FPS/intervals
        original=self.end.copy();route=(original-self.start).normalized()
        yaw=yaw_to(self.start,original)
        choices=[]
        for i in range(24):
            phase=i/24;offset=phase*duration/rate
            lock=StrideLock(ret,"walk_cycle",FPS,rate,self.start,yaw)
            for k in range(self.move_frames):lock.step(offset+k/FPS,settle=0)
            r=lock.report();first=V(lock.records[0]["contact_world"]);last=V(lock.records[-1]["contact_world"])
            stride=(lock.pos-self.start).dot(route)
            # The mark is on the original route, one measured stride from
            # start. The sole must independently land at that mark.
            mark=self.start+route*stride
            sole=(last-mark).length
            root=(V((lock.pos.x,lock.pos.y,mark.z))-mark).length
            row={"rate":rate,"phase":phase,"yaw":yaw,"settle_frames":0,"hold_frames":1,"cycle_count":1,"stride_length":stride,"start_support":list(first),"end_support":list(last),"support_displacement":list(last-first),"destination":list(mark),"original_destination":list(original),"root_stop_error_xy":root,"planted_stop_error":sole,"final_support":lock.records[-1]["support"],"start_support_index":lock.records[0]["support"],"final_contact_gap":abs(lock.records[-1]["contact_gap"]),"locked_pass":r["pass"],"backward_frames":r["backward_frames"],"stance_rms":r["stance_velocity_rms"],"max_contact_gap":r["max_contact_gap"]}
            row["pass"]=r["pass"] and r["backward_frames"]==0 and r["stance_velocity_rms"]<=.03 and r["max_contact_gap"]<=.02 and root<=.05 and sole<=.05 and row["final_contact_gap"]<=.02 and stride>0
            choices.append(row);print("WHOLE_STRIDE",json.dumps(row),flush=True)
        best=min(choices,key=lambda q:(not q["pass"],q["backward_frames"],max(0,q["stance_rms"]-.03),max(0,q["max_contact_gap"]-.02),q["planted_stop_error"]+q["root_stop_error_xy"]))
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
    def setup_june(self):
        # Construct the same two standing actors/seat fixtures, but bypass
        # the old OTS search; both actors remain present at the same marks.
        self.reviewed_camera={"location":[6.3,2.3,1.5],"target":[5.05,3.65,1.2],"lens":22}
        super().setup_june()
        self.reviewed_camera=None
        a=self.actors["narrator"];b=self.actors["june"]
        hero=a if self.unit=="june_question" else b
        pos=self.np if hero==a else self.jp
        yaw=self.nyaw if hero==a else self.jyaw
        f=V((math.sin(yaw),-math.cos(yaw),0))
        # Camera between the two characters, on the same world-X side of
        # their common eyeline. No hidden partner or visibility exception.
        candidates=[]
        for d in (1.15,1.40,1.65,1.85):
            for side in (.50,.75,1.,1.25):
                for z in (.90,1.10,1.30,1.50,1.70):
                    loc=pos+f*d+V((side,0,z));target=pos+V((0,0,1.16))
                    self.pose_june(32 if hero==a else 34,.5,.45)
                    frame(self.scene,self.cam,loc,target,24)
                    box=project(self.scene,self.cam,actor_points(hero))
                    if box[4]<=0:continue
                    extent=max(abs(v-.5) for v in box[:4])
                    lens=24*.455/max(extent,.001)
                    if not 12<=lens<=55:continue
                    frame(self.scene,self.cam,loc,target,lens)
                    face=object_visibility(self.scene,self.cam,[hero.face],7)
                    body=object_visibility(self.scene,self.cam,meshes(hero.root),7,meshes(self.chart)+meshes(self.pencil))
                    pencil=object_visibility(self.scene,self.cam,meshes(self.pencil),9) if hero==a else {"visible_fraction":1,"safe":True}
                    score=(not(face["safe"] and body["safe"] and pencil["safe"]),face["blocked"],max(0,.72-self.front_dot(hero)),max(0,.90-body["visible_fraction"]),max(0,.45-pencil["visible_fraction"]),-pencil["visible_fraction"])
                    candidates.append((score,loc.copy(),target.copy(),lens))
        checked=[]
        for _,loc,target,lens in sorted(candidates,key=lambda q:q[0])[:20]:
            frame(self.scene,self.cam,loc,target,lens);rows=[]
            for u,t in ((0,0),(.25,.3),(.5,.45),(.75,.95),(1,1.7),(1,3.4)):
                m=self.update_june(32 if hero==a else 34,u,t)
                rows.append(m)
            score=(max(m["speaker_visibility"]["blocked"] for m in rows),not all(m["speaker_visibility"]["safe"] and m["speaker_body_visibility"]["safe"] for m in rows),max(m["standing_seat_intersections"] for m in rows),max(m["foreground_intrusion"]["blocked"] for m in rows),max(0,.72-min(m["speaker_front_dot"] for m in rows)),max(0,.90-min(m["speaker_body_visibility"]["visible_fraction"] for m in rows)))
            if hero==a:score+= (max(m["pencil_external_visibility"]["blocked"] for m in rows),not all(m["pencil_external_visibility"]["safe"] for m in rows),max(0,.45-min(m["pencil_visibility"]["visible_fraction"] for m in rows)),-min(m["pencil_visibility"]["visible_fraction"] for m in rows))
            checked.append((score,loc.copy(),target.copy(),lens))
        if not checked:raise RuntimeError("No safe clean-single camera candidate")
        score,loc,target,lens=min(checked,key=lambda q:q[0]);frame(self.scene,self.cam,loc,target,lens)
        self.reverse_camera={"location":list(loc),"target":list(target),"lens":lens,"single":True,"world_x_side":"positive","candidate_scores":[{"score":list(q[0]),"location":list(q[1]),"target":list(q[2]),"lens":q[3]} for q in checked]}
    def setup_seating(self):
        # Same measured seat support height, same actor marks; strengthen the
        # physical raised bench silhouette and keep the fountain where it is.
        SceneUnit.setup_seating(self);self.prev_phase={}
        root=bpy.data.objects["Saying Hi story-local wall and seats"]
        bench=self.bench;cx,cy,_=bench.location;top=self.bench_top
        trim=material("Round3 dark timber bench apron",(.19,.075,.025))
        for y in (cy-1.25,cy+1.25):
            cube("Round3 visible timber bench leg",(cx-.22,y,(top-.14)/2),(.16,.19,top-.14),trim,root,bevel=.012)
        cube("Round3 raised bench front apron",(cx-.38,cy,top-.18),(.07,3.1,.12),trim,root,bevel=.01)
        # Sample all poses on normal lenses. Keep eye-height viewpoints and
        # move dog only within adjacent clear paving when visibility demands.
        options=[];target=V((4.6,-.87,1.0))
        for lens in (35,40,45,50):
            for x in (-2,-.5,1,2,3):
                for y in (-8,-6,-4,3,5,7):
                    loc=V((x,y,1.48))
                    frame(self.scene,self.cam,loc,target,lens)
                    self.dog[0].location=(4.10,-1.28,0)
                    self.prev_feet={};self.prev_hip={};self.prev_phase={}
                    m=self.update_seating(43,.5,.5,True)
                    if not all(.035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965 and p[4]>0 for p in m["actor_bounds"].values()):continue
                    cov=min(p[3]-p[2] for p in m["actor_bounds"].values())
                    options.append((cov,loc.copy(),lens))
        checked=[]
        for _,loc,lens in sorted(options,key=lambda q:-q[0])[:30]:
            frame(self.scene,self.cam,loc,target,lens)
            for mark in ((4.10,-1.28,0),(3.95,-1.45,0),(3.75,-1.55,0),(4.00,-.7,0),(3.70,-.8,0)):
                self.dog[0].location=mark;rows=[]
                for u in (0,.24,.40,.57,.75,1):
                    self.prev_feet={};self.prev_hip={};self.prev_phase={}
                    rows.append(self.update_seating(43,u,u,True))
                dog=[m["dog_visibility"] for m in rows]
                actor_safe=all(.035<=p[0]<=p[1]<=.965 and .035<=p[2]<=p[3]<=.965 and p[4]>0 for m in rows for p in m["actor_bounds"].values())
                w=min(d["bounds"][1]-d["bounds"][0] for d in dog);h=min(d["bounds"][3]-d["bounds"][2] for d in dog)
                score=(not actor_safe,max(d["blocked"] for d in dog),not all(d["safe"] and d["samples"]>0 for d in dog),max(0,.12-w),max(0,.055-h),-w)
                checked.append((score,loc.copy(),lens,mark,w,h))
        if not checked:raise RuntimeError("No full-body normal-lens seating framing candidate")
        score,loc,lens,mark,w,h=min(checked,key=lambda q:q[0]);self.dog[0].location=mark;frame(self.scene,self.cam,loc,target,lens)
        self.payoff_camera={"position":list(loc),"target":list(target),"lens":lens,"dog_mark":list(mark),"minimum_dog_width_proxy":w,"minimum_dog_height_proxy":h,"candidate_scores":[{"score":list(q[0]),"position":list(q[1]),"lens":q[2],"dog_mark":list(q[3])} for q in checked]}
        self.prev_feet={};self.prev_hip={};self.prev_phase={}

base_gate=runner.evaluate_gate
def evaluate_gate(unit,driver,rows):
    g=base_gate(unit,driver,rows);checks=g["checks"]
    def add(k,v,limit,ok):checks[k]={"value":v,"limit":limit,"pass":bool(ok)}
    if unit=="crossing":
        root=driver.lock.pos;mark=driver.end
        e=math.hypot(root.x-mark.x,root.y-mark.y)
        add("root_stop_error_xy",e,.05,e<=.05)
        gap=abs(driver.lock.records[-1]["contact_gap"])
        add("final_plant_contact_gap",gap,.02,gap<=.02)
        cov=checks["narrator_vertical_coverage"]["value"]
        add("round3_narrator_vertical_coverage",cov,.25,cov>=.25)
        add("no_settle_blend",max(r["settle"] for r in driver.lock.records),0,all(r["settle"]==0 for r in driver.lock.records))
    if unit=="seating":
        add("normal_lens_mm",driver.cam.data.lens,[35,50],35<=driver.cam.data.lens<=50)
        drift=checks["continuing_planted_foot_drift"]["value"]
        add("round3_planted_drift",drift,0,drift==0)
        d=[m["metrics"]["dog_visibility"]["bounds"] for m in rows]
        w=min(x[1]-x[0] for x in d);h=min(x[3]-x[2] for x in d)
        add("dog_min_width_fraction",w,.12,w>=.12);add("dog_min_height_fraction",h,.055,h>=.055)
    g["pass"]=all(x["pass"] for x in checks.values());return g

if __name__=="__main__":
    runner.CorrectedUnit=Round3Unit;runner.evaluate_gate=evaluate_gate
    runner.main()
