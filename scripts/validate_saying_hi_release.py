"""Fail closed on actual reviewed preflight blockers and missing motion inputs."""
import argparse,json,sys
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--review",required=True);ap.add_argument("--phase",choices=["proof","animatic"],default="proof");a=ap.parse_args()
    review=json.loads(Path(a.review).read_text());failures=[]
    for unit,info in review["units"].items():
        root=Path(info["path"])
        try:
            m=json.loads((root/"manifest.json").read_text())
            assert m["unit"]==unit and m["actual_rendered_frames"]==1 and (root/"held_pose.png").is_file()
        except (OSError,ValueError,AssertionError,KeyError) as e:
            failures.append(f"{unit}: missing/invalid actual preflight {root}: {e}");continue
        if unit=="crossing" and not m["stride"]["pass"]:
            s=m["stride"];failures.append(f"{unit}: LOCKED STRIDE FAIL in {root/'manifest.json'}: backward_frames={s['backward_frames']}, stance_rms={s['stance_velocity_rms']:.6f}, stop_error={m['target_stop_error']:.6f}")
        if unit=="otis_eyes":
            overlap=max(x["head_arm_overlap_pairs"] for row in m["metrics"] for x in row["metrics"]["eyes"])
            if overlap:failures.append(f"{unit}: head-arm surface overlap max={overlap} in {root/'manifest.json'}; no approved contact exception")
        if info["disposition"]=="hold":
            failures.append(f"{unit}: VISUAL HOLD: {info['reason']}; {root/'held_pose.png'}")
    if a.phase=="animatic":
        plan=json.loads(Path("stories/saying_hi_plan.json").read_text())
        for s in plan["shots"]:
            for x in s.get("animatic_segments") or [{"still_path":s["still_path"]}]:
                media=Path(x.get("video_path") or x["still_path"])
                if not media.is_file():failures.append(f"{s['id']}: missing actual media {media}")
    for line in failures:print("FAIL",line)
    if failures:
        print(f"RELEASE BLOCKED: {len(failures)} failed checks; no release marker authorized")
        sys.exit(1)
    print("All selected preflight checks pass; explicit release marker still required")
if __name__=="__main__":main()
