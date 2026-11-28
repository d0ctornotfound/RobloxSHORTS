"""Record actual committed Round 4 evidence and strict release state.
No supervisor visual approval is inferred from geometry or encoding."""
import json,os,subprocess,hashlib
from pathlib import Path
ROOT=Path("assets/saying_hi_review/corrections")
PRE=ROOT/"round4_precheck";NATIVE=ROOT/"round4_native";OUT=ROOT/"round4_release_audit"
OUT.mkdir(parents=True,exist_ok=True)
units=("crossing","june_question","june_answer","seating")
plan=json.loads(Path("stories/saying_hi_plan.json").read_text())
review=json.loads(Path("docs/saying_hi_round3_release_review.json").read_text())
review["round"]="Round 4: all replacements require actual native clips and supervisor visual approval"
lines=["","## Round 4 terminal CI evidence",f"Precheck run 46123443558; downstream run {os.environ.get('GITHUB_RUN_ID','unknown')}.",""]
ready=True
for unit in units:
    p=PRE/unit;gp=p/"gate.json";native=NATIVE/unit;video=native/(unit+".mp4")
    info=review["units"][unit];info.update(disposition="hold",geometry_path=str(p),video_path=str(video))
    if gp.is_file():
        g=json.loads(gp.read_text());lines.append(f"### {unit}: {g['samples']} samples, geometry {'PASS' if g['pass'] else 'FAIL'}")
        for k,v in g["checks"].items():lines.append(f"- {k}: {v['value']} (limit {v['limit']}; {'PASS' if v['pass'] else 'FAIL'})")
        if "low_camera" in g:lines.append("- Separate low camera: "+json.dumps(g["low_camera"]))
        if "walk_solution" in g:lines.append("- Selected support-point solution: "+json.dumps(g["walk_solution"]))
        if "remaining_face_failures" in g:lines.append("- Remaining face failures by frame/object: "+json.dumps(g["remaining_face_failures"]))
    else:
        g={};lines.append(f"### {unit}: no completed geometry gate; see render.log")
    m=native/"manifest.json";e=native/"encode_validation.json"
    real=False
    if g.get("pass") and video.is_file() and m.is_file() and e.is_file():
        man=json.loads(m.read_text());enc=json.loads(e.read_text());ids=plan["proof_units"][unit];start=round(plan["shots"][ids[0]-1]["edit_in"]*30);end=round(plan["shots"][ids[-1]-1]["edit_out"]*30)
        real=(man.get("mode")=="motion" and man.get("actual_rendered_frames")==end-start and man.get("rendered_temporal_samples_per_second")==30 and enc.get("encoded_frame_count")==end-start and enc.get("encoded_fps")==30 and enc.get("sha256")==hashlib.sha256(video.read_bytes()).hexdigest())
    ready=ready and real
    info["reason"]="Native numerical evidence present; supervisor visual review pending" if real else "No complete passing Round 4 native proof"
    lines.append("- Native delivery: "+("verified file, visual review pending" if real else "not delivered"))
rp=Path("docs/saying_hi_round4_release_review.json");rp.write_text(json.dumps(review,indent=2)+"\n")
def run(args,name):
    with (OUT/name).open("w") as f:return subprocess.run(args,stdout=f,stderr=subprocess.STDOUT).returncode
p=run(["python3","scripts/validate_shot_plan.py","stories/saying_hi_plan.json"],"plan_validation.log")
proof=run(["python3","scripts/validate_saying_hi_correction_release.py","--review",str(rp),"--phase","proof"],"proof_gate.log")
anim=run(["python3","scripts/validate_saying_hi_correction_release.py","--review",str(rp),"--phase","animatic"],"animatic_gate.log")
export=None
if ready and p==0:
    export=run(["python3","scripts/export_shot_animatic.py","stories/saying_hi_plan.json","--output",str(ROOT/"round4_animatic.mp4")],"animatic_export.log")
lines+=["",f"Plan exit {p}; proof audit exit {proof}; animatic audit exit {anim}; export exit {export} (None means not invoked).","No supervisor visual approval inferred. Prior six native proofs and historical seating remain intact. No full-film render or paid voice. No gate lowered.","ROUND 4 RELEASE BLOCKED until visual review and all strict checks pass." if proof or anim or export!=0 else "Round 4 audit passed."]
(OUT/"workflow_provenance.txt").write_text(f"workflow_run_id={os.environ.get('GITHUB_RUN_ID')}\nprecheck_run=46123443558\nsource_commit={os.environ.get('GITHUB_SHA')}\nproof_exit={proof}\nanimatic_exit={anim}\nexport_exit={export}\n")
doc=Path("docs/saying_hi_review.md");doc.write_text(doc.read_text()+"\n".join(lines)+"\n")
inv=Path("docs/saying_hi_deliverable_paths.txt");paths=set(inv.read_text().splitlines());paths.update(str(x) for d in (PRE,NATIVE,OUT) if d.exists() for x in d.rglob("*") if x.is_file());paths.update([str(rp),"scripts/report_saying_hi_round4.py",".github/workflows/saying-hi-round4-native.yml"]);a=ROOT/"round4_animatic.mp4"
if a.is_file():paths.add(str(a))
inv.write_text("\n".join(sorted(paths))+"\n")
raise SystemExit(1 if proof or anim or export not in (0,None) else 0)
