"""Compose a revised pilot only from previously committed, independently
decoded native sequences. No render, interpolation, or synthetic replacement."""
import argparse,json,hashlib,subprocess
from pathlib import Path
from film_direction_compare import sha,read
from film_timeline import write

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);a=p.parse_args()
    c=read(a.config);out=Path(c["output_dir"]);out.mkdir(parents=True,exist_ok=True)
    report={"groups":{},"visual_review_required":True,"full_render_authorized":False,"sources":{}}
    for name,s in c["merge_groups"].items():
        qp=Path(s["qc"]);ap=Path(s["audit"]);q=read(qp);audit=read(ap)
        if sha(qp)!=audit["qc_sha256"]:raise ValueError("independent QC hash mismatch "+name)
        g=q["groups"][s["group"]]
        clip=Path(g["clip"]);digest=sha(clip)
        proof=audit["clips"][s["group"]]
        if digest!=g["sha256"] or digest!=proof["sha256"] or proof["full_decode"]!="pass" or g["missing_chunks"]:raise ValueError("unverified native group "+name)
        if not all(r["direction"]["status"]=="numeric_pass" and all(v==0 for v in r["external_face_ray_blocks_max"].values()) and r["native_near_black_max_percent"] is not None and r["native_near_black_max_percent"]<=2 and r["gait_gate"] is not False for r in g["shots"].values()):raise ValueError("failed numerical group "+name)
        report["groups"][name]=g
        report["sources"][name]={"qc":str(qp),"qc_sha256":sha(qp),"audit":str(ap),"audit_sha256":sha(ap),"source_publication":audit["evidence_commit"]}
    ids=[sid for g in report["groups"].values() for sid in g["shots"]]
    assert len(ids)==len(set(ids)) and set(ids)=={sid for g in c["pilot_groups"] for sid in g["shots"]}
    report["numerical_pass"]=True
    write(out/"pilot_qc.json",report)
    (out/"SHA256SUMS").write_text(sha(out/"pilot_qc.json")+"  "+str(out/"pilot_qc.json")+"\n")
if __name__=="__main__":main()
