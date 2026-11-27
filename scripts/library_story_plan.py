"""Validate narration-first long-form plans, not a generic video renderer."""
import argparse,json
from pathlib import Path
def validate(s):
    duration=s["duration"];fps=s["fps"];shots=s["shots"]
    assert 105<=duration<=135 and fps in (12,24)
    assert s["narration"].strip() and 210<=len(s["narration"].split())<=330
    assert 0<s["hook_end"]<=3 and s["callbacks"]
    assert shots[0]["start"]==0 and shots[-1]["end"]==duration
    words=[]
    for i,shot in enumerate(shots):
        assert 1<=shot["end"]-shot["start"]<=3
        if i:assert shot["start"]==shots[i-1]["end"]
        assert all(shot[k] for k in ("location","camera","action","narration_beat","characters"))
        assert isinstance(shot["props"],list)
        assert shot["camera"] in ("wide","medium","close","insert")
        words.extend(shot["narration_beat"].split())
    assert words==s["narration"].split(),"shot narration join mismatch"
    for c in s["callbacks"]:assert 0<=c["setup"]<c["payoff"]<=duration and c["detail"]
    return {"duration":duration,"words":len(words),"shots":len(shots),"frames":round(duration*fps),"locations":sorted(set(x["location"] for x in shots)),"callbacks":len(s["callbacks"])}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("plan");a=p.parse_args();print(json.dumps(validate(json.loads(Path(a.plan).read_text())),indent=2))
