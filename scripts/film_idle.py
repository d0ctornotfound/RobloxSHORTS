"""Film-process-only idle overlay. Never change the locked Chapter 1 sources.
Action poses are evaluated without idle, sampled, then secondary motion is
added to safe unoccupied joints for the actual render. No camera motion counts.
"""
import hashlib, math
PROFILE = {
    "name":"calm_film_v1","torso_breath_rad":.013,"torso_sway_rad":.020,
    "head_breath_rad":.015,"head_sway_rad":.014,"head_glance_rad":.060,
    "breath_hz":.25,"sway_hz":.15,"background_pitch_rad":.028,
    "background_yaw_rad":.052,"glance_interval_s":[3,6],"glance_duration_s":1.2,
    "continuous_background_oscillation":False,
}
def install_neutral_idle():
    # This function is called only inside the opt-in isolated Blender film process.
    # Preserve all action branches and the held prop's purposeful arm transition.
    import character_motion_correction as chapter
    from mathutils import Vector
    original=chapter.corrected_params
    def neutral(name,u,t):
        p=original(name,u,t)
        if name=="idle" or name.startswith("hold_"):
            hold=chapter.ramp(u,0,.27) if name!="idle" else 1
            p["torso"]=(0,0,0);p["head"]=(0,0,0)
            p["arms"]=[chapter.mix(chapter.D,v,hold) for v in chapter.parameters(name,.5)["arms"]]
            p["legs"]=[(-.08,0,-1),(.08,0,-1)]
        return p
    chapter.corrected_params=neutral
    return original

def state(cid,spec,geometry):
    direction=spec.get("direction",{})
    seat=geometry.get("seat_contacts",{}).get(cid)
    if seat is not None:
        phase=seat.get("phase")
        if phase in ("rise","step","sit"):return "action"
        if phase in ("standing","seated","initial_seated"):return "intentional_stillness"
        return "unmeasured"
    if cid in direction.get("performance",{}) or cid in spec.get("actors",{}).keys() or cid in direction.get("action_actors",[]):
        return "action"
    if cid in direction.get("intentional_stillness",[]):return "intentional_stillness"
    if cid in direction.get("background",[]):return "idle"
    # A listener explicitly staged without reaction is allowed to listen.
    if cid in direction.get("listeners",[]):return "intentional_stillness"
    return "unmeasured"

def values(cid,seconds,background=False):
    # Deterministic per-actor phase, continuous in global film time.
    seed=int.from_bytes(hashlib.sha256(cid.encode()).digest()[:8],"big")
    fraction=(seed%10000)/10000
    interval=3+3*fraction
    phase=(seconds+interval*((seed//10000)%10000)/10000)%interval
    pulse=math.sin(math.pi*phase/PROFILE["glance_duration_s"])**2 if phase<PROFILE["glance_duration_s"] else 0
    b=math.sin(math.tau*(seconds*.25+fraction))
    s=math.sin(math.tau*(seconds*.15+fraction))
    sign=1 if seed%2 else -1
    if background:
        return (0,0,0),(-.015*b+.028*pulse, .014*s, sign*.052*pulse)
    return (.013*b,.020*s,.012*pulse),(-.015*b,.014*s,sign*.060*pulse-.020*s)

class FilmIdle:
    def __init__(self):
        self.saved=[]
    def restore(self):
        import bpy
        for bone,basis in self.saved:bone.matrix_basis=basis
        if self.saved:bpy.context.view_layer.update()
        self.saved=[]
    def apply(self,actors,spec,geometry,seconds,signature):
        import bpy
        from mathutils import Euler
        records={}
        for cid,a in actors.items():
            mode=state(cid,spec,geometry)
            records[cid]={"action_state":mode,"action_pose":signature(a),"idle_profile":PROFILE["name"],"idle_applied_rad":{}}
            if mode not in ("idle","intentional_stillness"):continue
            # Seat/contact adapters and declared seated groups are head-only.
            # Do not move load-bearing hips or attached hands to create idle.
            seated=cid in spec.get("declared_scene",{}).get("seated",[]) or cid in geometry.get("seat_contacts",{})
            bg=cid in spec.get("direction",{}).get("background",[])
            torso,head=values(cid,seconds,bg)
            for name,angles in (("torso",torso),("head",head)):
                if name=="torso" and (seated or bg):continue
                bone=a.bones[name];basis=bone.matrix_basis.copy()
                self.saved.append((bone,basis))
                bone.matrix_basis=basis @ Euler(angles).to_matrix().to_4x4()
                records[cid]["idle_applied_rad"][name]=list(angles)
        bpy.context.view_layer.update()
        return records
