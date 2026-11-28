"""Compile a data-driven film, render independent native chunks, and assemble.
Technical integrity is mandatory; measured artistic QC is advisory.
"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from fractions import Fraction
from film_qc import evaluate as evaluate_qc, flow_report
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+"\n")
def run(cmd):subprocess.run(cmd,check=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def probe(p):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(p)],text=True))
def video(p):return next(x for x in probe(p)["streams"] if x["codec_type"]=="video")
def check_video(p,n):
    v=video(p)
    assert int(v["nb_read_frames"])==n and Fraction(v["avg_frame_rate"])==30 and Fraction(v["r_frame_rate"])==30 and (v["width"],v["height"])==(540,960),(p,v)
    return v
def compile_tasks(c):
    p=read(c["plan"]);shots=p["shots"];fps=p["fps"];assert fps==30
    tasks=[];cursor=0
    for s in shots:
        st=round(s["edit_in"]*fps);en=round(s["edit_out"]*fps)
        assert st==cursor and en>st;cursor=en
        segs=c["staged_shots"][s["id"]];pos=st
        for i,seg in enumerate(segs):
            a=st+round((en-st)*seg.get("fraction_start",0));b=st+round((en-st)*seg.get("fraction_end",1))
            assert a==pos and b>a;pos=b
            if "reuse" in seg:
                tasks.append({"key":f'{s["id"]}-{a}',"shot":s["id"],"start":a,"end":b,"reuse":seg["reuse"],"offset":seg["offset"],"provenance":seg["provenance"]});continue
            ua,ub=seg.get("unit_frame_window",[a,b]);assert ua<=a<b<=ub
            ids=seg.get("sentence_ids",s["sentence_ids"]);ids=[int(n) for n in ids]
            for lo in range(a,b,c.get("chunk_frames",24)):
                tasks.append({"key":f'{s["id"]}-{lo}',"shot":s["id"],"start":lo,"end":min(b,lo+c.get("chunk_frames",24)),"unit_start":ua,"unit_end":ub,"sentence_ids":ids,"stage":seg["stage"]})
        assert pos==en
    assert cursor==round(p["audio_duration"]*fps) and set(c["staged_shots"])=={s["id"] for s in shots}
    return tasks
def chunk(c,t,config,out,local_map):
    out.mkdir(parents=True,exist_ok=True)
    with (out/"render.log").open("w") as f:
        subprocess.run(["timeout","--kill-after=20s","42m","blender","-b","--python-exit-code","1","--python","scripts/render_film_unit.py","--","--config",config,"--task",json.dumps(t),"--map",local_map,"--output",str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
    m=read(out/"manifest.json");start,end=t["start"],t["end"];frames=sorted(out.glob("frame_*.png"))
    assert [p.name for p in frames]==[f"frame_{i:05d}.png" for i in range(start,end)]
    assert [x["frame"] for x in m["rendered"]]==list(range(start,end)) and m["render_sampling_hz"]==30 and m["engine"]=="EEVEE" and m["denoising"] is False
    write(out/"source_hashes.json",{p.name:sha(p) for p in frames})
    run(["ffmpeg","-y","-v","error","-framerate","30","-start_number",str(start),"-i",str(out/"frame_%05d.png"),"-frames:v",str(end-start),"-c:v","libx264","-crf","17","-pix_fmt","yuv420p",str(out/"clip.mp4")])
    check_video(out/"clip.mp4",end-start)
    # Retain original source sample images as permanent review evidence; all
    # other frames are represented by the native clip and per-frame hashes.
    for i,p in enumerate(frames):
        if i in (0,len(frames)//2,len(frames)-1):p.rename(out/("sample_"+p.name))
        else:p.unlink()
def assemble(c,tasks,chunks,out):
    out.mkdir(parents=True,exist_ok=True);work=out/"segments";work.mkdir(exist_ok=True)
    ledger=[];missing=[];qc={};samples={};plan=read(c["plan"])
    for t in tasks:
        n=t["end"]-t["start"];key=t["key"];target=work/(key+".mp4")
        q=qc.setdefault(t["shot"],{"start":t["start"],"end":t["end"],"frames":0,"flags":[],"chunks":[]})
        q["end"]=t["end"]
        if "reuse" in t:
            path=Path(t["reuse"]);proof=read(t["provenance"])
            assert proof["source_render_sampling_hz"]==30 and proof["encoded_fps"]==30 and proof["sha256"]==sha(path)
            check_video(path,proof["encoded_frame_count"])
            assert t["offset"]+n<=proof["encoded_frame_count"]
            run(["ffmpeg","-y","-v","error","-i",str(path),"-vf",f'trim=start_frame={t["offset"]}:end_frame={t["offset"]+n},setpts=PTS-STARTPTS',"-an","-c:v","libx264","-crf","17","-pix_fmt","yuv420p",str(target)])
            row={"source":str(path),"source_offset":t["offset"],"source_sha256":sha(path),"type":"approved_native_reuse","frames":n}
            q["chunks"].append(row)
        else:
            source=chunks/t["key"]
            if not (source/"clip.mp4").is_file() or not (source/"manifest.json").is_file():missing.append(key);q["flags"].append("missing native chunk "+key);continue
            m=read(source/"manifest.json");check_video(source/"clip.mp4",n)
            samples.setdefault(t["shot"],[]).extend(m["rows"])
            assert [x["frame"] for x in m["rendered"]]==list(range(t["start"],t["end"]))
            target=source/"clip.mp4";dark=max(x["near_black_percent"] for x in m["rendered"])
            if dark>2:q["flags"].append(f"{key}: near-black {dark:.5f}% >2%")
            for cid in sorted({cid for x in m["rows"] for cid in x["actor_qc"]}):
                vals=[x["actor_qc"][cid] for x in m["rows"] if cid in x["actor_qc"]]
                ext=max(x["face_external"]["blocked"] for x in vals);own=max(x["own_ray_difference"] for x in vals);cov=min(x["vertical_coverage"] for x in vals)
                q["chunks"].append({"key":key,"actor":cid,"external_blocked_max":ext,"own_ray_difference_max":own,"min_vertical_coverage":cov,"safe_all":all(x["safe"] for x in vals)})
                if ext or not all(x["safe"] for x in vals):q["flags"].append(f"{key} {cid}: external blocked={ext}, safe={all(x['safe'] for x in vals)}, coverage={cov:.4f}")
            if m["missing_props"]:q["flags"].append("missing props: "+str(m["missing_props"]))
            if m["extra"].get("walk",{}).get("complete_unit"):
                w=m["extra"]["walk"];q["chunks"].append({"walk":w})
                for k,v,limit in [("root_stop",w["root_stop_error_to_plant"],.05),("plant_stop",w["final_contact_error"],.05),("backward",w["metrics"]["backward_frames"],0),("stance_rms",w["metrics"]["stance_velocity_rms"],.03)]:
                    if v>limit:q["flags"].append(f"{k} {v} > {limit}")
                if not w["final_plant"]:q["flags"].append("last source sample not support transition")
            row={"source":str(target),"sha256":sha(target),"type":"new_native","frames":n,"max_near_black_percent":dark}
        check_video(target,n);q["frames"]+=n;ledger.append({**row,"key":key,"start":t["start"],"end":t["end"],"path":str(target.resolve())})
    for s in plan["shots"]:
        q=qc[s["id"]];q["flags"]+=c.get("known_weaknesses",{}).get(s["id"],[])
        if c.get("grade_preset"):
            rs=samples.get(s["id"],[])
            windows={}
            for row in rs:
                key=tuple(row.get("unit_window",[q["start"],q["end"]]))
                windows.setdefault(key,[]).append(row)
            if len(windows)>1:
                parts=[]
                for key,rr in sorted(windows.items()):
                    first=max(q["start"],key[0]);last=min(q["end"],key[1])
                    parts.append({"start":first,"end":last,"direction":flow_report(rr,expected_frames=last-first)})
                q["direction"]={"status":"numeric_pass" if sum(x["end"]-x["start"] for x in parts)==q["end"]-q["start"] and all(x["direction"]["status"]=="numeric_pass" for x in parts) else "flag","segments":parts}
            else:q["direction"]=flow_report(rs, expected_frames=q["end"]-q["start"])
            if q["direction"]["status"]!="numeric_pass":q["flags"].append("direction QC: "+q["direction"]["status"])
        q["measurements"]=evaluate_qc(samples.get(s["id"],[]),c.get("qc_rules",{}).get(s["id"],[]))
        for m in q["measurements"]:
            if m["status"]!="pass":q["flags"].append(f"{m['name']}: {m['value']} (limit {m['operator']} {m['limit']}; {m['status']})")
        q["flags"]=list(dict.fromkeys(q["flags"]))
    write(out/"qc.json",{"shot_count":len(qc),"sampling_hz":30,"encoded_target_fps":30,"missing":missing,"shots":qc})
    write(out/"timeline.json",ledger)
    if missing:raise RuntimeError("Technical incompleteness; no substitute frames: "+str(missing))
    concat=out/"concat.txt";concat.write_text("".join("file '"+x["path"]+"'\n" for x in ledger))
    film=out/c["film_name"]
    run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(concat),"-i",plan["narration_audio"],"-map","0:v:0","-map","1:a:0","-vf","setpts=N/(30*TB)","-fps_mode","passthrough","-c:v","libx264","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-movflags","+faststart",str(film)])
    total=round(plan["audio_duration"]*30);check_video(film,total)
    ff=probe(film);audio=next(x for x in ff["streams"] if x["codec_type"]=="audio")
    assert abs(float(audio["duration"])-plan["audio_duration"])<.08
    write(out/"film_validation.json",{"frame_count":total,"duration":plan["audio_duration"],"source_sampling_hz":30,"encoded_fps":30,"sha256":sha(film),"bytes":film.stat().st_size,"ffprobe":ff})
def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("command",choices=["matrix","chunk","assemble"]);p.add_argument("--task");p.add_argument("--map");p.add_argument("--output",default="film-output");p.add_argument("--chunks",default="film-chunks");a=p.parse_args();c=read(a.config);ts=compile_tasks(c)
    if a.command=="matrix":print(json.dumps({"include":[{"key":t["key"],"task":json.dumps(t,separators=(",",":"))} for t in ts if "reuse" not in t]},separators=(",",":")))
    elif a.command=="chunk":chunk(c,json.loads(a.task),a.config,Path(a.output),a.map)
    else:assemble(c,ts,Path(a.chunks),Path(a.output))
if __name__=="__main__":main()
