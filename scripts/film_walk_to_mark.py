"""Generic deterministic walk-to-mark construction on the locked stride layer.
The destination is calibrated from the final evaluated plant, not root-snapped.
"""
import math
from mathutils import Vector
from library_locomotion import StrideLock

def construct(ret,start,direction,frames,fps=30,cycles=1):
    start=Vector(start); direction=Vector(direction); yaw=math.atan2(direction.x,-direction.y)
    duration=ret.clips["walk_cycle"]["duration"]
    # Observe the chronological support transitions once, at a fixed source
    # phase grid. No destination-fit or candidate ranking.
    probe=StrideLock(ret,"walk_cycle",fps,duration*fps/120,start,yaw)
    for i in range(241):probe.step(i/fps)
    transitions=[i for i in range(1,241) if probe.records[i]["support"]!=probe.records[i-1]["support"]]
    phase=transitions[0]/120 if transitions else 0.
    rate=duration*cycles*fps/max(1,frames-1)
    offset=phase*duration/rate
    replay=StrideLock(ret,"walk_cycle",fps,rate,start,yaw)
    for i in range(frames):replay.step(offset+i/fps)
    rows=replay.records
    planted=Vector(rows[-1]["contact_world"])
    root=Vector(rows[-1]["root"])
    info={"cycle_count":cycles,"phase":phase,"rate":rate,"offset_seconds":offset,"start_support":rows[0]["support"],"final_support":rows[-1]["support"],"same_foot":rows[0]["support"]==rows[-1]["support"],"final_plant":rows[-1]["support"]!=rows[-2]["support"],"destination":list(planted),"root_destination":list(root),"source_transition_indices":transitions,"method":"fixed phase-grid transition observation, whole-cycle playback; no endpoint fit"}
    return StrideLock(ret,"walk_cycle",fps,rate,start,yaw),info
