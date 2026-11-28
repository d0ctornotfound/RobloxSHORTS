"""Generic deterministic walk-to-mark construction on the locked stride layer.
The destination is calibrated from the final evaluated plant, not root-snapped.
"""
import math
import numpy as np
from mathutils import Vector
from library_locomotion import StrideLock

def construct(ret,start,direction,frames,fps=30,cycles=1,phase_strategy='transition',fixed=None):
    start=Vector(start); direction=Vector(direction); yaw=math.atan2(direction.x,-direction.y)
    duration=ret.clips["walk_cycle"]["duration"]
    # Observe the chronological support transitions once, at a fixed source
    # phase grid. No destination-fit or candidate ranking.
    probe=StrideLock(ret,"walk_cycle",fps,duration*fps/120,start,yaw)
    for i in range(241):probe.step(i/fps)
    transitions=[i for i in range(1,241) if probe.records[i]["support"]!=probe.records[i-1]["support"]]
    phase=transitions[0]/120 if transitions else 0.
    rate=duration*cycles*fps/max(1,frames-1)
    phase_diagnostics=None
    if phase_strategy=="gait_gate":
        # Search only the native cycle's sampling phase, NOT the destination.
        # The table is evaluated from unchanged rig/retarget/StrideLock poses.
        # Exact replay below decides pass; the search never clamps a root or
        # fabricates an intermediate pose.
        if cycles!=1:raise ValueError("gait-gate sampling requires one whole cycle")
        n=frames-1;sub=8;grid=n*sub
        sampler=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
        table=np.array([[list(v) for v in sampler.sample_local(i*duration/(grid*rate))] for i in range(grid)])
        candidates=[]
        for phase_i in range(grid):
            ids=(phase_i+np.arange(frames)*sub)%grid
            values=table[ids];support=int(values[0,:,2].argmin());initial=support
            backwards=0;gaps=[];swaps=[];speed=0.
            for k in range(1,frames):
                prev,cur=values[k-1],values[k]
                valid=cur[:,2]<=cur[:,2].min()+.018
                score=(cur[:,1]-prev[:,1])*fps
                score[support]+=.12;score[~valid]=-1e9
                new=int(score.argmax());v=float((cur[new,1]-prev[new,1])*fps)
                backwards+=v<-.01;speed+=v
                gaps.append(float(cur[new,2]-cur[:,2].min()));swaps.append(new!=support);support=new
            candidates.append({"phase":phase_i/grid,"predicted_backwards":int(backwards),"predicted_same_foot":support==initial,"predicted_final_plant":bool(swaps[-1]),"predicted_max_gap":max(gaps),"predicted_forward_speed":speed/n})
        rank=lambda x:(x["predicted_backwards"],not x["predicted_final_plant"],not x["predicted_same_foot"],x["predicted_max_gap"],-x["predicted_forward_speed"])
        exact=[]
        for candidate in sorted(candidates,key=rank)[:8]:
            ph=candidate["phase"];test=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
            for k in range(frames):test.step(ph*duration/rate+k/fps)
            m=test.report();r=test.records
            exact.append({**candidate,"exact_backwards":m["backward_frames"],"exact_rms":m["stance_velocity_rms"],"exact_gap":m["max_contact_gap"],"exact_pass":m["pass"],"exact_same_foot":r[0]["support"]==r[-1]["support"],"exact_final_plant":r[-1]["support"]!=r[-2]["support"]})
        best=min(exact,key=lambda x:(not x["exact_pass"],x["exact_backwards"],not x["exact_final_plant"],not x["exact_same_foot"],max(0,x["exact_rms"]-.03),x["exact_gap"]))
        phase=best["phase"];phase_diagnostics={"grid":grid,"selected":best,"exact_candidates":exact}
    elif phase_strategy=="gait_timing":
        # Native playback rate/phase may be chosen for an edit window that cuts
        # in motion; no destination matching, time-warp within a cycle, or
        # root correction. The exact locked replay is always authoritative.
        n=frames-1;grid=720
        sampler=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
        table=np.array([[list(v) for v in sampler.sample_local(i*duration/(grid*rate))] for i in range(grid)])
        factors=np.arange(.82,1.181,.01)
        phases=np.arange(grid)/grid
        ff,pp=np.meshgrid(factors,phases,indexing="ij");ff=ff.ravel();pp=pp.ravel();K=len(ff)
        backward=np.zeros(K,dtype=int);gap=np.zeros(K);speed=np.zeros(K);support=None;prev=None
        for k in range(frames):
            ix=(pp+k*ff/n)%1*grid;j=ix.astype(int);frac=(ix-j)[:,None,None]
            cur=table[j]*(1-frac)+table[(j+1)%grid]*frac
            low=cur[:,:,2].min(axis=1)
            if prev is None:support=cur[:,:,2].argmin(axis=1);initial=support.copy()
            else:
                scores=(cur[:,:,1]-prev[:,:,1])*fps;scores[np.arange(K),support]+=.12
                scores[cur[:,:,2]>low[:,None]+.018]=-1e9
                new=scores.argmax(axis=1);v=(cur[np.arange(K),new,1]-prev[np.arange(K),new,1])*fps
                backward+=v<-.01;speed+=v;gap=np.maximum(gap,cur[np.arange(K),new,2]-low);swapped=new!=support;support=new
            prev=cur
        order=np.lexsort((gap,abs(ff-1),~swapped,backward))
        exact=[]
        for i in order[:18]:
            ph=float(pp[i]);ra=float(rate*ff[i]);test=StrideLock(ret,"walk_cycle",fps,ra,start,yaw)
            for k in range(frames):test.step(ph*duration/ra+k/fps)
            m=test.report();r=test.records
            exact.append({"phase":ph,"rate":ra,"cycles":float(ff[i]),"predicted_backwards":int(backward[i]),"exact_backwards":m["backward_frames"],"exact_rms":m["stance_velocity_rms"],"exact_gap":m["max_contact_gap"],"exact_pass":m["pass"],"exact_final_plant":r[-1]["support"]!=r[-2]["support"],"distance":float((test.pos-start).length)})
        best=min(exact,key=lambda x:(not x["exact_pass"],x["exact_backwards"],not x["exact_final_plant"],max(0,x["exact_rms"]-.03),abs(x["cycles"]-1),x["exact_gap"]))
        phase=best["phase"];rate=best["rate"];cycles=best["cycles"];phase_diagnostics={"grid":grid,"selected":best,"exact_candidates":exact}
    elif phase_strategy=="fixed":
        if not fixed:raise ValueError("fixed timing requires evaluated phase and rate")
        phase=float(fixed["phase"]);rate=float(fixed["rate"]);cycles=rate*(frames-1)/(duration*fps)
    elif phase_strategy!="transition":raise ValueError("unknown sampling phase strategy")
    offset=phase*duration/rate
    replay=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
    for i in range(frames):replay.step(offset+i/fps)
    rows=replay.records
    planted=Vector(rows[-1]["contact_world"])
    root=Vector(rows[-1]["root"])
    info={"cycle_count":cycles,"phase":phase,"rate":rate,"offset_seconds":offset,"start_support":rows[0]["support"],"final_support":rows[-1]["support"],"same_foot":rows[0]["support"]==rows[-1]["support"],"final_plant":rows[-1]["support"]!=rows[-2]["support"],"destination":list(planted),"root_destination":list(root),"source_transition_indices":transitions,"method":"fixed phase-grid transition observation, whole-cycle playback; no endpoint fit" if phase_strategy=="transition" else "native gait-only phase search and exact replay; no endpoint fit","phase_strategy":phase_strategy,"phase_diagnostics":phase_diagnostics}
    return StrideLock(ret,"walk_cycle",fps,rate,start,yaw),info
