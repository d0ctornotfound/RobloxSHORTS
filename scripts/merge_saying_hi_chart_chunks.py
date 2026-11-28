"""Assemble exact independently rendered native chart frame chunks; no interpolated frames."""
import argparse,json,shutil
from pathlib import Path
from encode_saying_hi_proof import sha

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--unit",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    src=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    manifests=[]
    for path in sorted(src.glob("*/manifest.json")):
        m=json.loads(path.read_text())
        if m.get("unit")!=a.unit:continue
        assert m["mode"]=="motion" and m["rendered_temporal_samples_per_second"]==30
        assert m["actual_rendered_frames"]==m["expected_rendered_frames"]
        manifests.append((m,path.parent))
    if not manifests:raise ValueError("No completed chunks")
    manifests.sort(key=lambda v:v[0]["frame_window"][0])
    unit_start,unit_end=manifests[0][0]["unit_frame_window"];cursor=unit_start;rendered=[];metrics=[];chunk_info=[]
    for m,path in manifests:
        start,end=m["frame_window"];assert start==cursor and m["unit_frame_window"]==[unit_start,unit_end]
        assert [v["frame"] for v in m["rendered"]]==list(range(start,end))
        for i in range(start,end):
            filename=f"frame_{i:05d}.png";source=path/filename
            assert source.is_file() and not (out/filename).exists()
            shutil.copyfile(source,out/filename)
        rendered.extend(m["rendered"]);metrics.extend(row for row in m["metrics"] if start<=row["global_frame"]<end)
        chunk_info.append({"frame_window":[start,end],"manifest_sha256":sha(path/"manifest.json")})
        shutil.copyfile(path/"manifest.json",out/f"chunk_{start:05d}_{end:05d}.json")
        if (path/"render.log").is_file():shutil.copyfile(path/"render.log",out/f"chunk_{start:05d}_{end:05d}.log")
        cursor=end
    assert cursor==unit_end and len(rendered)==unit_end-unit_start
    assert [r["global_frame"] for r in metrics]==list(range(unit_start,unit_end))
    m=manifests[0][0];m.update(frame_window=[unit_start,unit_end],actual_rendered_frames=len(rendered),expected_rendered_frames=len(rendered),rendered=rendered,metrics=metrics,chunks=chunk_info)
    (out/"manifest.json").write_text(json.dumps(m,indent=2)+"\n")
if __name__=="__main__":main()
