"""Supervisor release audit. Existing supervisor-accepted chart media remain
immutable; every other unit requires a numeric PASS, visual review, and real
native clip. Earlier failed audits are intentionally preserved."""
import argparse,hashlib,json,subprocess,sys
from fractions import Fraction
from pathlib import Path
from validate_shot_plan import validate
ROOT=Path(".")
def read(p):return json.loads(Path(p).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    a=argparse.ArgumentParser();a.add_argument("--review",required=True);a.add_argument("--phase",choices=["proof","animatic"],required=True);a.add_argument("--plan",default="stories/saying_hi_plan.json");args=a.parse_args()
    plan=read(args.plan);print("PLAN",json.dumps(validate(plan,ROOT,False)))
    review=read(args.review);fail=[];ok=[]
    def require(condition,msg):
        if not condition:fail.append(msg)
        return bool(condition)
    for unit,ids in plan["proof_units"].items():
        info=review["units"][unit];start=round(plan["shots"][ids[0]-1]["edit_in"]*30);end=round(plan["shots"][ids[-1]-1]["edit_out"]*30)
        expected=end-start
        if unit not in ("chart_initial","chart_final"):
            gp=Path(info["geometry_path"])/"gate.json"
            if not gp.is_file():
                fail.append(f"{unit}: no complete gate.json at {gp}; {info.get('reason','unverified')}")
            else:
                g=read(gp)
                require(g.get("samples")==expected and g.get("sampling_hz")==30,f"{unit}: missing all-frame geometry samples")
                for key,x in g["checks"].items():
                    require(x["pass"],f"{unit}: {key} FAIL value={x['value']} limit={x['limit']} at {gp}")
                require(g["pass"],f"{unit}: geometry gate not passed")
            require(info["disposition"]=="reviewed_pass",f"{unit}: VISUAL HOLD: {info.get('reason','visual review missing')}")
        else:
            require(info["disposition"]=="supervisor_accepted",f"{unit}: chart approval absent")
        path=Path(info["video_path"]);manifest=path.parent/"manifest.json";enc=path.parent/"encode_validation.json"
        if not (path.is_file() and manifest.is_file() and enc.is_file()):
            fail.append(f"{unit}: native proof missing: {path}");continue
        m=read(manifest);e=read(enc)
        require(m["mode"]=="motion" and m["engine"]=="EEVEE" and m["denoising"] is False and m["eevee_spatial_samples"]==32,f"{unit}: incorrect render profile")
        require(m["frame_window"]==[start,end] and m["actual_rendered_frames"]==expected and m["rendered_temporal_samples_per_second"]==30,f"{unit}: incorrect native samples")
        require([r["frame"] for r in m["rendered"]]==list(range(start,end)),f"{unit}: source sample sequence not complete")
        require(e["source_render_count"]==e["encoded_frame_count"]==expected and e["source_render_sampling_hz"]==e["encoded_fps"]==30,f"{unit}: incorrect encoded sample count/rate")
        require(e["sha256"]==sha(path),f"{unit}: encoded file SHA mismatch")
        require(len(e["source_frame_hashes"])==expected,f"{unit}: source frame hash count wrong")
        if unit not in ("chart_initial","chart_final"):
            require(m.get("geometry_gate",{}).get("pass") is True,f"{unit}: native render lacks repeated geometry pass")
        ok.append({"unit":unit,"frames":expected,"sha256":e["sha256"],"path":str(path)})
    if args.phase=="animatic":
        for s in plan["shots"]:
            for seg in s.get("animatic_segments") or [{"still_path":s["still_path"]}]:
                path=seg.get("video_path") or seg["still_path"]
                require(Path(path).is_file(),f"{s['id']}: required actual media missing {path}")
                if seg.get("video_path"):
                    units=[k for k,ids in plan["proof_units"].items() if int(s["sentence_ids"][0]) in ids]
                    require(len(units)==1 and review["units"][units[0]]["video_path"]==path,f"{s['id']}: not the reviewed corrected native proof path")
    print("VALIDATED_NATIVE",json.dumps(ok))
    for line in fail:print("FAIL",line)
    if fail:
        print(f"RELEASE BLOCKED: {len(fail)} checks failed")
        sys.exit(1)
    print("RELEASE PASS: full evidence and inputs")
if __name__=="__main__":main()
