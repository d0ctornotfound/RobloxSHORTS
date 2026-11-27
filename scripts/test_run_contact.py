"""Numerical run-speed regression; uses approved source GLB and imported cycles."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_library_showcase import fresh
from library_character import character
from r6_imported_cycles import Retarget
from library_locomotion import StrideLock
fresh(360,640,16)
actor=character("Regression actor","lead");ret=Retarget(actor)
results={}
for name in ("walk_cycle","run_cycle"):
    lock=StrideLock(ret,name,30,.72,(0,0,0),.30)
    for f in range(181):lock.step(f/30)
    results[name]=lock.report()
out=Path("render/run_contact");out.mkdir(parents=True,exist_ok=True)
(out/"regression.json").write_text(json.dumps(results,indent=2)+"\n")
print("RUN_CONTACT_REGRESSION",json.dumps({k:{a:b for a,b in v.items() if a!="records"} for k,v in results.items()}),flush=True)
assert all(v["pass"] for v in results.values())
assert results["run_cycle"]["mean_forward_speed"]>results["walk_cycle"]["mean_forward_speed"],"run must be faster at equal playback rate for these clips"
