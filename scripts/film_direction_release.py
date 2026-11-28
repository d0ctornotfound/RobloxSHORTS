"""Fail-closed full-film direction gate. No story IDs or fixed pilot paths.
A numerical pilot pass AND explicit committed visual review are required.
This validates evidence presence, not the truth of a human artistic judgment."""
import argparse, hashlib, json
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def validate_selected_sources(config,release):
    """A replacement pilot may supersede one group without rerendering others.
    Keep numerical gates, hashes and independent decode mandatory. Explicit
    reviewer-accepted visual residuals are recorded, never relabeled as passes.
    The strict legacy single-source contract remains unchanged."""
    review_path=Path(release["visual_review"])
    if not review_path.is_file() or sha(review_path)!=release["visual_review_sha256"]:
        raise ValueError("missing or mismatched visual review")
    review=read(review_path)
    if review.get("release_disposition") not in ("accepted","accepted_with_residuals"):
        raise ValueError("pilot review not accepted")
    required={"scale_correct","faces_readable","motion_coverage","no_long_holds","grade_warm_vs_baseline","continuity_and_contacts"}
    residual_allowed={"scale_correct","continuity_and_contacts"}
    shot_ids=set()
    for source in release["sources"]:
        qc_path=Path(source["pilot_qc"]);audit_path=Path(source["independent_audit"])
        if not qc_path.is_file() or sha(qc_path)!=source["pilot_qc_sha256"]:
            raise ValueError("pilot QC digest mismatch")
        if not audit_path.is_file() or sha(audit_path)!=source["independent_audit_sha256"]:
            raise ValueError("pilot audit digest mismatch")
        qc=read(qc_path);audit=read(audit_path)
        if qc.get("numerical_pass") is not True or audit["qc_sha256"]!=sha(qc_path) or audit["evidence_commit"]!=source["pilot_publication_commit"]:
            raise ValueError("native pilot gate or independent provenance failed")
        if set(audit["clips"])!=set(qc["groups"]) or not all(v["full_decode"]=="pass" for v in audit["clips"].values()):
            raise ValueError("pilot independent decode not verified")
        staged=read(source["pilot_config"])["staged_shots"]
        for name in source["groups"]:
            group=qc["groups"][name];verified=audit["clips"][name]
            if group.get("missing_chunks") or not group.get("clip") or sha(group["clip"])!=group["sha256"] or verified["sha256"]!=group["sha256"]:
                raise ValueError("missing or mismatched selected native clip")
            for sid,row in group["shots"].items():
                if sid in shot_ids:raise ValueError("duplicate selected pilot shot "+sid)
                shot_ids.add(sid);verdict=review["shots"][sid]
                if verdict["pilot_qc_sha256"]!=sha(qc_path):
                    raise ValueError("review not linked to selected QC "+sid)
                if row["direction"]["status"]!="numeric_pass" or any(v!=0 for v in row["external_face_ray_blocks_max"].values()):
                    raise ValueError("selected pilot numeric gate failed "+sid)
                if staged[sid]!=config["staged_shots"][sid]:
                    raise ValueError("full-film staging differs from selected native pilot "+sid)
                failed={k for k in required if verdict.get(k) is not True}
                residuals=verdict.get("accepted_residuals",{})
                if failed!=set(residuals) or not failed.issubset(residual_allowed):
                    raise ValueError("unaccepted visual checklist failure "+sid)
                if failed and (review["release_disposition"]!="accepted_with_residuals" or not review.get("reviewer_authorization") or not all(isinstance(v,str) and v.strip() for v in residuals.values())):
                    raise ValueError("visual residual requires explicit reviewer authorization "+sid)
                frames=verdict.get("reviewed_frames",[])
                if not frames or not all(Path(p).is_file() for p in frames):
                    raise ValueError("missing committed reviewed frame "+sid)
                if not set(frames).issubset(audit["shots"][sid]["review_frames"]):
                    raise ValueError("review frames not from independent committed decode "+sid)
    if set(review["shots"])!=shot_ids or set(release["required_pilot_shots"])!=shot_ids:
        raise ValueError("selected pilot coverage mismatch")
    return shot_ids

def validate(config):
    release=config.get("direction_release")
    if not release:raise ValueError("full film requires direction_release evidence")
    if "sources" in release:
        shot_ids=validate_selected_sources(config,release)
    else:
        qc_path=Path(release["pilot_qc"]);review_path=Path(release["visual_review"])
        if not qc_path.is_file() or not review_path.is_file():raise ValueError("missing committed pilot evidence")
        if sha(qc_path)!=release["pilot_qc_sha256"] or sha(review_path)!=release["visual_review_sha256"]:raise ValueError("pilot evidence digest mismatch")
        qc=read(qc_path);review=read(review_path)
        if qc.get("numerical_pass") is not True:raise ValueError("native pilot numerical gate not passed")
        if review.get("pilot_qc_sha256")!=sha(qc_path) or review.get("visual_pass") is not True:raise ValueError("visual review not passed or not tied to this exact QC")
        audit_path=Path(release["independent_audit"])
        if not audit_path.is_file() or sha(audit_path)!=release["independent_audit_sha256"]:raise ValueError("missing or mismatched committed pilot audit")
        audit=read(audit_path)
        if audit["qc_sha256"]!=sha(qc_path) or audit["evidence_commit"]!=release["pilot_publication_commit"]:raise ValueError("independent audit not linked to exact pilot")
        if set(audit["clips"])!=set(qc["groups"]) or not all(v["full_decode"]=="pass" for v in audit["clips"].values()):raise ValueError("pilot independent decode not verified")
        required={"scale_correct","faces_readable","motion_coverage","no_long_holds","grade_warm_vs_baseline","continuity_and_contacts"}
        shot_ids=set()
        for group in qc["groups"].values():
            if group.get("missing_chunks") or not group.get("clip"):raise ValueError("missing native pilot clip")
            if sha(group["clip"])!=group["sha256"]:raise ValueError("pilot clip hash mismatch")
            for sid,row in group["shots"].items():
                shot_ids.add(sid);verdict=review["shots"][sid]
                if row["direction"]["status"]!="numeric_pass":raise ValueError("pilot direction flag: "+sid)
                if any(v!=0 for v in row["external_face_ray_blocks_max"].values()):raise ValueError("pilot occlusion: "+sid)
                if not all(verdict.get(k) is True for k in required):raise ValueError("visual checklist incomplete: "+sid)
                frames=verdict.get("reviewed_frames",[])
                if not frames or not all(Path(p).is_file() for p in frames):raise ValueError("missing committed reviewed frame: "+sid)
        if set(review["shots"])!=shot_ids:raise ValueError("review/pilot shot mismatch")
    plan=read(config["plan"])
    if set(config["staged_shots"])!={s["id"] for s in plan["shots"]}:raise ValueError("incomplete film staging")
    for sid,segments in config["staged_shots"].items():
        for segment in segments:
            if "reuse" in segment:
                if not segment.get("direction_reuse_reason") or not segment.get("direction_reuse_qc"):raise ValueError("uncertified direction reuse: "+sid)
                if not Path(segment["direction_reuse_qc"]).is_file():raise ValueError("missing reuse direction QC: "+sid)
            else:
                spec=segment["stage"].get("direction")
                if not spec or not spec.get("beat_type") or not spec.get("camera_move"):raise ValueError("missing direction staging: "+sid)
                if spec["camera_move"]=="locked" and not spec.get("lock_reason"):raise ValueError("unmotivated lock: "+sid)
    return {"pilot_shots":sorted(shot_ids),"planned_shots":len(plan["shots"]),"release_evidence":"validated; visual judgment remains reviewer responsibility"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);a=p.parse_args()
    print(json.dumps(validate(read(a.config)),indent=2))
if __name__=="__main__":main()
