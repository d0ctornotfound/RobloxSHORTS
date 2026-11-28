"""Strict exact-text, timing, cast and continuity validator for shot plans."""
import argparse, json, math, re, wave
from pathlib import Path

def read_script(path):
    rows=[]
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m=re.fullmatch(r"(\d+) \[([\d.]+)-([\d.]+)\] (.+)",line)
        if not m: raise ValueError(f"Malformed script line: {line!r}")
        rows.append((m[1],float(m[2]),float(m[3]),m[4]))
    if not rows or len({r[0] for r in rows})!=len(rows):
        raise ValueError("Empty script or duplicate sentence ID")
    return rows

def require(ok,msg):
    if not ok: raise ValueError(msg)

def validate(p,root=Path("."),draft=False):
    rows=read_script(root/p["script_path"])
    cast=json.loads((root/p["cast_path"]).read_text())
    stage=json.loads((root/p["staging_path"]).read_text())
    actors=cast["actors"]
    require(p["narration_source"] in ("temporary","approved"),"invalid narration source")
    require(bool(p["retime_note"]),"missing retime note")
    require(p["fps"]>0,"invalid fps")
    expect=[r[0] for r in rows]; by_id={r[0]:r for r in rows}
    shots=p["shots"]; seen=set(); used=[]; actual=[]; prior=None; prior_audio=0; prior_edit=0
    fields=("id","sentence_ids","narration","reference_audio_in","reference_audio_out","audio_in","audio_out","edit_in","edit_out","understand","action","cast","set","props","start_state","end_state","camera","cut_cue","dependencies","render_profile","sampling_rate","encoded_fps","still_path")
    for s in shots:
        sid=s.get("id","unknown")
        require(all(k in s for k in fields),f"{sid}: missing required field")
        require(sid not in seen,f"{sid}: duplicate shot")
        ids=s["sentence_ids"];require(bool(ids) and all(x in by_id for x in ids),f"{sid}: unknown or empty narration ID")
        expected=" ".join(by_id[x][3] for x in ids)
        require(s["narration"]==expected,f"{sid}: verbatim narration mismatch")
        require(s["reference_audio_in"]==by_id[ids[0]][1] and s["reference_audio_out"]==by_id[ids[-1]][2],f"{sid}: reference timing mismatch")
        used.extend(ids);actual.append(s["narration"])
        require(all(isinstance(s[k],str) and s[k].strip() for k in ("understand","action","set","start_state","end_state","cut_cue","still_path")),f"{sid}: empty required text")
        require(isinstance(s["cast"],list) and all(x in actors for x in s["cast"]),f"{sid}: unknown cast")
        require(isinstance(s["props"],list),f"{sid}: invalid props")
        require(s["set"]==stage["set"],f"{sid}: unknown set")
        c=s["camera"];require(all(k in c for k in ("size","position","angle","focal_length_mm","subject_kept_in_frame","movement")),f"{sid}: incomplete camera")
        require(c["size"] in ("wide","medium","close","insert") and c["focal_length_mm"]>0,f"{sid}: invalid camera")
        require(all(c[k] for k in ("position","angle","subject_kept_in_frame")),f"{sid}: incomplete framing")
        if c["movement"] is not None:
            require(all(c["movement"].get(k) for k in ("direction","start_framing","end_framing","motivation")),f"{sid}: incomplete camera move")
        require(isinstance(s["dependencies"],list) and all(x in seen for x in s["dependencies"]),f"{sid}: unresolved or forward dependency")
        if prior:
            require(prior["id"] in s["dependencies"],f"{sid}: missing preceding shot dependency")
            require(prior["end_state"]==s["start_state"],f"{sid}: discontinuous state")
        require(s["render_profile"] in ("animatic","motion_proof","final"),f"{sid}: unknown profile")
        require(s["sampling_rate"]>0 and s["encoded_fps"]==p["fps"],f"{sid}: invalid rate")
        if s["render_profile"]=="motion_proof":
            require(s["sampling_rate"]==s["encoded_fps"]==30,f"{sid}: motion proof requires 30 rendered samples per second")
        if not draft:
            a,b,e,f=(s[k] for k in ("audio_in","audio_out","edit_in","edit_out"))
            require(all(isinstance(x,(int,float)) and math.isfinite(x) for x in (a,b,e,f)),f"{sid}: actual narration timings missing")
            require(0<=e<=a<b<=f and a>=prior_audio-1e-6,f"{sid}: overlapping or invalid audio")
            require(abs(e-prior_edit)<1e-6 and f>e,f"{sid}: gap or overlap in edit")
            prior_audio=b;prior_edit=f
        seen.add(sid);prior=s
    require(used==expect,"missing, duplicated or reordered sentence IDs")
    require(" ".join(actual)==" ".join(r[3] for r in rows),"exact narration concatenation mismatch")
    if not draft:
        require(p["status"]=="retimed_actual_audio","plan is not aligned to actual audio")
        require(bool(p["narration_audio"]),"missing narration WAV")
        with wave.open(str(root/p["narration_audio"]),"rb") as w:
            duration=w.getnframes()/w.getframerate()
        require(abs(duration-p["audio_duration"])<1e-6 and abs(prior_edit-duration)<1e-6,"edit does not cover actual audio")
    if p["id"]=="saying_hi":
        chart=stage["chart"]; girls=chart["girls"];boys=chart["boys"];links=chart["initial_links"]
        require(len(girls)==len(set(girls))==len(boys)==len(set(boys))==10 and not set(girls)&set(boys),"chart roster must be 10+10")
        require(set(girls+boys)==set(actors) and boys[-1]=="narrator","chart roster mismatch")
        require(len(links)==10 and sorted(x["from"] for x in links)==sorted(girls),"chart requires one link per girl")
        require({x["to"] for x in links}=={"brody","chase","kai"},"wrong initial destinations")
        require({"from":"june","to":"kai"} in links and {"from":"narrator","to":"june"} in chart["replacement_links"],"missing critical chart links")
        require(chart["author"]=="otis","chart must belong to Otis")
        require(all(x["from"] in actors and x["to"] in actors for x in chart["replacement_links"]),"bad replacement links")
    return {"mode":"draft_only" if draft else "actual_audio","sentences":len(rows),"shots":len(shots),"words":len(" ".join(actual).split()),"audio_duration":None if draft else duration}

def main():
    p=argparse.ArgumentParser();p.add_argument("plan");p.add_argument("--root",default=".");p.add_argument("--draft",action="store_true");p.add_argument("--demonstrate-failure",action="store_true");a=p.parse_args()
    root=Path(a.root);plan=json.loads((root/a.plan).read_text())
    if a.demonstrate_failure: plan["shots"][0]["narration"]+=" WRONG"
    try: print(json.dumps(validate(plan,root,a.draft),indent=2))
    except (ValueError,KeyError,TypeError,OSError) as e: p.exit(1,f"SHOT PLAN FAIL: {e}\n")
if __name__=="__main__":main()
