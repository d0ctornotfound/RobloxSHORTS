"""Generic deterministic walk-to-mark construction on the locked stride layer.
The destination is calibrated from the final evaluated plant, not root-snapped.
"""
import math
import numpy as np
from mathutils import Vector
from library_locomotion import StrideLock

def construct(ret,start,direction,frames,fps=30,cycles=1,phase_strategy='transition'):
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
    elif phase_strategy!="transition":raise ValueError("unknown sampling phase strategy")
    offset=phase*duration/rate
    replay=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
    for i in range(frames):replay.step(offset+i/fps)
    rows=replay.records
    planted=Vector(rows[-1]["contact_world"])
    root=Vector(rows[-1]["root"])
    info={"cycle_count":cycles,"phase":phase,"rate":rate,"offset_seconds":offset,"start_support":rows[0]["support"],"final_support":rows[-1]["support"],"same_foot":rows[0]["support"]==rows[-1]["support"],"final_plant":rows[-1]["support"]!=rows[-2]["support"],"destination":list(planted),"root_destination":list(root),"source_transition_indices":transitions,"method":"fixed phase-grid transition observation, whole-cycle playback; no endpoint fit" if phase_strategy=="transition" else "native gait-only phase search and exact replay; no endpoint fit","phase_strategy":phase_strategy,"phase_diagnostics":phase_diagnostics}
    return StrideLock(ret,"walk_cycle",fps,rate,start,yaw),info
