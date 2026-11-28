"""Verify one independently rendered 30-fps proof, encode and record actual stream rate."""
import argparse, hashlib,json,subprocess
from fractions import Fraction
from pathlib import Path

def sha(path):
    with path.open("rb") as f:
        h=hashlib.sha256()
        while chunk:=f.read(1024*1024):h.update(chunk)
        return h.hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument("directory");args=a.parse_args();p=Path(args.directory)
    m=json.loads((p/"manifest.json").read_text())
    if m["mode"]!="motion" or m["engine"]!="EEVEE" or m["denoising"] is not False:raise ValueError("Not native EEVEE motion proof")
    start,end=m["frame_window"];expected=end-start
    frames=sorted(p.glob("frame_*.png"))
    if [x.name for x in frames]!=[f"frame_{i:05d}.png" for i in range(start,end)]:raise ValueError("Missing or repeated source sample")
    if expected!=m["actual_rendered_frames"] or expected!=len(m["rendered"]) or [x["frame"] for x in m["rendered"]]!=list(range(start,end)):raise ValueError("Manifest/source frame mismatch")
    if m["rendered_temporal_samples_per_second"]!=30:raise ValueError("Wrong source rate")
    hashes=[sha(x) for x in frames]
    out=p/(m["unit"]+".mp4")
    subprocess.run(["ffmpeg","-nostdin","-y","-v","error","-framerate","30","-start_number",str(start),"-i",str(p/"frame_%05d.png"),"-frames:v",str(expected),"-c:v","libx264","-crf","17","-pix_fmt","yuv420p","-movflags","+faststart",str(out)],check=True)
    ff=json.loads(subprocess.run(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(out)],check=True,capture_output=True,text=True).stdout)
    v=next(x for x in ff["streams"] if x["codec_type"]=="video")
    if Fraction(v["avg_frame_rate"])!=30 or Fraction(v["r_frame_rate"])!=30 or int(v["nb_read_frames"])!=expected:raise ValueError("Incorrect encoded sample count/rate")
    info={"unit":m["unit"],"source_render_sampling_hz":30,"encoded_fps":float(Fraction(v["avg_frame_rate"])),"source_render_count":len(frames),"encoded_frame_count":int(v["nb_read_frames"]),"identical_adjacent_png_pairs":sum(x==y for x,y in zip(hashes,hashes[1:])),"unique_png_hashes":len(set(hashes)),"sha256":sha(out),"source_frame_hashes":dict(zip((x.name for x in frames),hashes)),"ffprobe":ff,"review":"Independent render samples may be visually identical for stationary poses; no frame duplication used by encoder."}
    (p/"encode_validation.json").write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps({k:v for k,v in info.items() if k not in ("source_frame_hashes","ffprobe")},indent=2))
if __name__=="__main__":main()
