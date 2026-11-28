"""Story-local source-time schedule search. The imported pose data and
StrideLock.step/report are unmodified. Only source playback times vary;
actual root displacement remains the locked support-point compensation."""
import math,json
import numpy as np
from mathutils import Vector,Matrix
from library_locomotion import StrideLock
from r6_imported_cycles import Retarget
FPS=30
def ease(u):u=max(0,min(1,u));return u*u*(3-2*u)

class PhaseStrideLock(StrideLock):
    def __init__(self,ret,rate,start,yaw,schedule):
        self.phase_schedule=schedule
        super().__init__(ret,"walk_cycle",FPS,rate,start,yaw)
    def sample_local(self,t,settle=0):
        i=round(t*FPS)
        if not 0<=i<len(self.phase_schedule):raise ValueError("Phase schedule exhausted")
        phase=self.phase_schedule[i]
        return super().sample_local(phase*self.ret.clips[self.name]["duration"]/self.rate,settle)

def search_walk_warp(actor,start,end,nframes,pickup):
    ret=Retarget(actor);duration=ret.clips["walk_cycle"]["duration"];sample=StrideLock(ret,"walk_cycle",FPS,.2,start,0)
    N=480;levels=(0,.25,.5,.75,1.);table=np.empty((5,N,2,3))
    for j,s in enumerate(levels):
        for i in range(N):table[j,i]=np.array([list(v) for v in sample.sample_local(i/N*duration/.2,s)])
        print("WARP_SOLE_TABLE",j,N,flush=True)
    movement=nframes-pickup;hold=4;dist=(end-start).length
    rates=np.arange(.145,.281,.004);phases=np.arange(N)
    rr,pp=np.meshgrid(rates,phases,indexing="ij");rr=rr.ravel();pp=pp.ravel();K=len(rr);ix=np.arange(K)
    nominal=rr/(FPS*duration)*N;predicted=[]
    # Each candidate advances by a positive integer source-phase interval.
    # No repeated source time before the final neutral hold; no root warp.
    for settle_len in (5,8,12,16,20,26,32):
        paths=np.empty((K,movement),np.int32);paths[:,0]=pp
        pos=np.zeros((K,2));phase=pp.copy();local=table[0,phase%N];low=local[:,:,2].min(axis=1);support=local[:,:,2].argmin(axis=1)
        prev_inc=nominal.copy();backward=np.zeros(K,dtype=int);rms=np.zeros(K);count=np.zeros(K);gap=np.zeros(K);cost_total=np.zeros(K)
        for i in range(1,movement):
            s=ease((i-(movement-hold-settle_len))/max(1,settle_len-1));j=min(3,int(s*4));fy=s*4-j
            bestcost=np.full(K,1e30);chosen_inc=np.zeros(K,dtype=int);chosen_new=np.zeros(K,dtype=int);chosen_local=np.zeros((K,2,3));chosen_delta=np.zeros((K,2));chosen_vel=np.zeros(K);chosen_gap=np.zeros(K)
            for inc in range(1,12):
                # Playback-rate bounds stay moderate around each candidate.
                allowed=(inc>=np.maximum(1,nominal*.48))&(inc<=nominal*1.70+1)
                nxt=(phase+inc)%N;candidate=(1-fy)*table[j,nxt]+fy*table[j+1,nxt];nl=candidate[:,:,2].min(axis=1)
                eligible=candidate[:,:,2]<=nl[:,None]+.018
                sweep=(candidate[:,:,1]-local[:,:,1])*FPS;sweep[ix,support]+=.12;sweep[~eligible]=-1e8
                new=sweep.argmax(axis=1);delta=local[ix,new,:2]-candidate[ix,new,:2];speed=-delta[:,1]*FPS
                contact_gap=candidate[ix,new,2]-nl
                velocity=((candidate[ix,new,2]-nl)-(local[ix,new,2]-low))*FPS
                same=new==support
                # Hard-priority zero backward; stance velocity cost is based
                # on continuing support only, exactly as the locked gate.
                remaining=(movement-i-1);progress=-pos[:,1]-delta[:,1]
                goal=dist*(i/(movement-1))
                score=(speed<-.01)*10000+np.maximum(0,contact_gap-.02)*10000+same*velocity**2*45+abs(inc-nominal)*.025+abs(inc-prev_inc)*.014+abs(progress-goal)*.32
                score[~allowed]+=1e5
                take=score<bestcost
                bestcost[take]=score[take];chosen_inc[take]=inc;chosen_new[take]=new[take];chosen_local[take]=candidate[take];chosen_delta[take]=delta[take];chosen_vel[take]=velocity[take];chosen_gap[take]=contact_gap[take]
            same=chosen_new==support
            rms+=same*chosen_vel**2;count+=same;backward+=(-chosen_delta[:,1]*FPS<-.01);gap=np.maximum(gap,chosen_gap)
            phase+=chosen_inc;paths[:,i]=phase;pos+=chosen_delta;local=chosen_local;low=local[:,:,2].min(axis=1);support=chosen_new;prev_inc=chosen_inc;cost_total+=bestcost
        foot=pos+local[ix,support,:2];err=abs(np.linalg.norm(foot,axis=1)-dist);rms=np.sqrt(rms/np.maximum(1,count));angles=np.arctan2(foot[:,0],-foot[:,1])
        penalty=backward*1000+np.maximum(0,rms-.03)*200+np.maximum(0,gap-.02)*1000+np.maximum(0,abs(angles)-.24)*100+err+cost_total/np.maximum(1,movement)*.00005
        for idx in np.argsort(penalty)[:20]:
            predicted.append((float(penalty[idx]),float(rr[idx]),settle_len,float(err[idx]),int(backward[idx]),float(rms[idx]),paths[idx].copy().tolist()))
        print("WARP_PREDICTED",settle_len,"best",float(penalty.min()),flush=True)
    predicted.sort(key=lambda q:q[0]);actual=[];chosen=None;seen=set()
    for score,rate,settle_len,pe,pb,pr,path in predicted:
        signature=(path[0]//8,round(rate,2),settle_len,path[-1]//8)
        if signature in seen:continue
        seen.add(signature)
        schedule=[x/N for x in path]
        l=PhaseStrideLock(ret,rate,start,0,schedule)
        for i in range(movement):
            s=ease((i-(movement-hold-settle_len))/max(1,settle_len-1));l.step(i/FPS,settle=s)
        report=l.report();last=l.records[-1];d=Vector(last["contact_world"])-start
        goal=end-start;desired=math.atan2(goal.x,-goal.y)
        yaw=(desired-math.atan2(d.x,-d.y)+math.pi)%(2*math.pi)-math.pi
        contact=start+Matrix.Rotation(yaw,3,"Z")@d;err=(contact-end).length
        back=sum(x["forward_speed"]<-.01 for x in l.records);rows=[x for x in l.records if x["continuing"]];rms=math.sqrt(sum(x["velocity"]**2 for x in rows)/len(rows))
        drift=max((Vector(x["contact_world"])-Vector(last["contact_world"])).length for x in l.records[-hold:])
        row={"rate":rate,"phase":schedule[0],"phase_schedule":schedule,"settle_frames":settle_len,"hold_frames":hold,"yaw":yaw,"predicted_error":pe,"predicted_backward":pb,"predicted_rms":pr,"stop_error":err,"locked_pass":report["pass"],"backward_frames":back,"stance_rms":rms,"locked_stance_rms":report["stance_velocity_rms"],"settled_contact_drift":drift,"max_contact_gap":report["max_contact_gap"],"source_time_remapped":True}
        row["pass"]=report["pass"] and back==0 and rms<=.03 and report["stance_velocity_rms"]<=.03 and err<=.05 and abs(yaw)<=.24 and drift<=.005
        actual.append(row);print("WARP_EXACT",json.dumps({k:v for k,v in row.items() if k!="phase_schedule"}),flush=True)
        if row["pass"]:chosen=row;break
        if len(actual)>=24:break
    if chosen is None:chosen=min(actual,key=lambda q:(not q["locked_pass"],q["backward_frames"],max(0,q["stance_rms"]-.03),q["stop_error"]))
    return chosen,actual,ret
