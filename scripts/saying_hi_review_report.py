"""Generate evidence-backed numerical review from actual proof manifests.
Visual defects still require actual decoded-frame review; never infer approval.
"""
import argparse,json,math
from pathlib import Path

def extrema(values):
    v=[x for x in values if isinstance(x,(int,float)) and math.isfinite(x)]
    return {"min":min(v),"max":max(v),"count":len(v)} if v else None
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default="assets/saying_hi_review");a=p.parse_args();root=Path(a.root)
    units=("chart_initial","crossing","otis_eyes","june_question","june_answer","dog_name","seating","empty_wall","chart_final","closing")
    result={}
    for unit in units:
        base=root/"proofs"/unit;m=base/"manifest.json";e=base/"encode_validation.json"
        if not m.is_file():
            result[unit]={"status":"not rendered / missing manifest"};continue
        data=json.loads(m.read_text());metrics=[row["metrics"] for row in data["metrics"]]
        x={"status":"candidate / visual review required","source_samples":data["actual_rendered_frames"],"source_rate":data["rendered_temporal_samples_per_second"],"encoded":json.loads(e.read_text()) if e.is_file() else None,
           "darkness_percent":extrema([row["near_black_percent"] for row in data["rendered"]]),"scenery":data.get("scenery")}
        if x["encoded"]:x["encoded"]={k:v for k,v in x["encoded"].items() if k not in ("source_frame_hashes","ffprobe")}
        charts=[row["chart"] for row in metrics if "chart" in row]
        if charts:x["chart"]={"arrow_count":extrema([v["arrows"] for v in charts]),"final_links":charts[-1]["links"],"scope":"source artwork, verify visible arrowheads in actual PNG"}
        for prop in ("chart","pencil"):
            obs=[row[prop+"_contact"] for row in metrics if prop+"_contact" in row]
            if obs:x[prop+"_contact"]={"sampled_min_surface_gap":extrema([v["sampled_min_arm_surface_gap"] for v in obs]),"overlap_pairs":extrema([v["arm_prop_overlap_pairs"] for v in obs]),"scope":"rigid whole-arm surface; not signed distal-hand penetration"}
        if "stride" in data:x["stride"]={k:v for k,v in data["stride"].items() if k!="records"};x["target_stop_error"]=data["target_stop_error"]
        eye=[v for row in metrics for v in row.get("eyes",[])]
        if eye:x["eye_cover"]={"hand_target_gap":extrema([v["hand_target_gap"] for v in eye]),"head_arm_overlap_pairs":extrema([v["head_arm_overlap_pairs"] for v in eye])}
        for who in ("june","narrator"):
            seat=[row["seat_contacts"][who] for row in metrics if "seat_contacts" in row]
            if seat:
                settled=[v for v in seat if v["seated_fraction_command"]>=.999]
                x[who+"_seat"]={"settled_hip_gap":extrema([v["signed_rear_hip_gap"] for v in settled]),"all_foot_plane_gap":extrema([g for v in seat for g in v["signed_foot_gaps"]]),"per_sample_foot_drift":extrema([g for v in seat for g in (v["foot_step_drift"] or [])])}
        dogs=[row["waffle"]["evaluated_min_z"] for row in metrics if row.get("waffle")]
        if dogs:x["dog_ground_min_z"]=extrema(dogs)
        result[unit]=x
    output=root/"proof_measurements.json";output.write_text(json.dumps(result,indent=2)+"\n")
    print(str(output))
if __name__=="__main__":main()
