"""Publish a film build's permanent evidence without rewriting earlier history."""
import argparse,json,hashlib,os,subprocess
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--config",required=True);ap.add_argument("--chunks",required=True);a=ap.parse_args();c=json.loads(Path(a.config).read_text());out=Path(c["output_dir"]);out.mkdir(parents=True,exist_ok=True)
    from shutil import copytree,copy2
    chunks=Path(a.chunks)
    if chunks.exists():copytree(chunks,out/"chunks",dirs_exist_ok=True)
    # The complete rendered clip and source evidence are preserved. On an
    # interrupted render keep partial original PNGs and partial manifests.
    film=out/c["film_name"]
    lines=["","## Full-film workflow run "+os.environ.get("GITHUB_RUN_ID","local"),""]
    qc=out/"qc.json";val=out/"film_validation.json"
    if val.exists() and film.exists():
        v=json.loads(val.read_text());lines.append(f"Technical master verified: {v['duration']:.2f}s, {v['frame_count']} frames, source sampling {v['source_sampling_hz']} Hz, encoded {v['encoded_fps']} fps, SHA-256 {v['sha256']}. Visual approval pending.")
        if film.stat().st_size>95_000_000:
            subprocess.run(["split","-b","90000000","-d","-a","3",str(film),str(film)+".part"],check=True)
            parts=sorted(out.glob(film.name+".part*"));assert sum(p.stat().st_size for p in parts)==film.stat().st_size
            film.unlink();lines.append("Large-file preservation: concatenate "+", ".join(str(p) for p in parts)+" in order; verify master SHA-256 above.")
        else:lines.append("Master: "+str(film))
    else:lines.append("No technically verified complete master exists in this run. Preserve all partial evidence; no substitute footage.")
    if qc.exists():
        q=json.loads(qc.read_text())
        lines.extend(["","| Shot | Timeline (s) | Native frames delivered | Measured flags / specific known fixes |","|---|---|---:|---|"])
        for shot,s in q["shots"].items():
            flags="; ".join(s["flags"]) or "No flagged measurement; human visual review pending."
            vals="; ".join(f"{m['name']}={m['value']} ({m['status']}, n={m['samples']})" for m in s.get("measurements",[]))
            if vals:flags+="; Measurements: "+vals
            lines.append(f"| {shot} | {s['start']/30:.2f}–{s['end']/30:.2f} | {s['frames']} | {flags.replace('|','/')} |")
    else:lines.append("Per-shot QC report absent; inspect partial render logs.")
    lines.append("\nSource motion sampling is independent at 30 Hz, EEVEE 32 spatial samples, denoising off. Artistic QC is advisory; missing or invalid native media is a technical failure.")
    with Path(c["review_path"]).open("a") as f:f.write("\n".join(lines)+"\n")
    (out/"workflow_provenance.txt").write_text("run_id="+os.environ.get("GITHUB_RUN_ID","local")+"\nsource_commit="+os.environ.get("GITHUB_SHA","local")+"\n")
    evidence=[p for p in out.rglob("*") if p.is_file() and p.name!="SHA256SUMS"]
    with (out/"SHA256SUMS").open("w") as f:
        for p in sorted(evidence):
            h=hashlib.sha256()
            with p.open("rb") as stream:
                while b:=stream.read(1024*1024):h.update(b)
            f.write(h.hexdigest()+"  "+str(p)+"\n")
    with Path(c["inventory_path"]).open("a") as f:f.write("\nFull-film run "+os.environ.get("GITHUB_RUN_ID","local")+" exact evidence paths:\n"+"\n".join(str(p) for p in sorted(evidence+[out/"SHA256SUMS"]))+"\n")
if __name__=="__main__":main()
