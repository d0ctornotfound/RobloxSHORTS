"""Create a temporary narration with local eSpeak NG; never use a paid voice API."""
import argparse, json, subprocess, tempfile, wave, math
from pathlib import Path
from validate_shot_plan import read_script,validate

def paced_pcm(src,data,rate,target_samples):
    """Fit local synthesized sentence to reference window without truncating speech.
    FFmpeg tempo changes preserve pitch; actual output PCM length is measured.
    Padding, if needed, is appended after the complete processed sentence.
    """
    desired=target_samples/rate;original=len(data)/2/rate
    ratio=max(.5,original/desired*1.045)
    for attempt in range(8):
        filters=[];v=ratio
        while v>2:filters.append("atempo=2");v/=2
        while v<.5:filters.append("atempo=0.5");v*=2
        filters.append("atempo="+str(v))
        result=subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(src),"-af",",".join(filters),"-f","s16le","-ac","1","-ar",str(rate),"-"],check=True,stdout=subprocess.PIPE).stdout
        if len(result)//2<=target_samples:
            pad=target_samples-len(result)//2
            return result+b"\0\0"*pad,{"original_seconds":original,"tempo_ratio":ratio,"processed_seconds":len(result)/2/rate,"padding_seconds":pad/rate}
        ratio*=1.08
    raise RuntimeError("Could not fit complete sentence in reference window")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("plan");ap.add_argument("--wav",required=True);ap.add_argument("--speed",type=int,default=175);ap.add_argument("--match-reference",action="store_true");a=ap.parse_args()
    root=Path(".");path=root/a.plan;p=json.loads(path.read_text())
    validate(p,root,draft=True)
    rows=read_script(root/p["script_path"])
    pcm=[];n=0;rate=None;last_ref=0;times={};pace=[]
    with tempfile.TemporaryDirectory() as tmp:
        for sid,ref_in,ref_out,words in rows:
            wpath=Path(tmp)/f"{sid}.wav"
            subprocess.run(["espeak-ng","-v","en-us","-s",str(a.speed),"-w",str(wpath),"--stdin"],input=words,text=True,check=True)
            with wave.open(str(wpath),"rb") as w:
                assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getcomptype()=="NONE"
                if rate is None: rate=w.getframerate()
                assert rate==w.getframerate()
                data=w.readframes(w.getnframes())
            if a.match_reference:
                gap=round(ref_in*rate)-n
                if gap<0:raise ValueError("Reference intervals overlap")
                data,details=paced_pcm(wpath,data,rate,round(ref_out*rate)-round(ref_in*rate))
                pace.append(dict(sentence_id=sid,**details))
            else:gap=round(max(0,ref_in-last_ref)*rate)
            pcm.append(b"\0\0"*gap);n+=gap
            start=n/rate;pcm.append(data);n+=len(data)//2
            times[sid]=(start,n/rate);last_ref=ref_out
    wav=root/a.wav;wav.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(wav),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b"".join(pcm))
    for i,s in enumerate(p["shots"]):
        s["audio_in"]=times[s["sentence_ids"][0]][0];s["audio_out"]=times[s["sentence_ids"][-1]][1]
        s["edit_in"]=0 if i==0 else s["audio_in"]
    for i,s in enumerate(p["shots"]):
        s["edit_out"]=p["shots"][i+1]["edit_in"] if i+1<len(p["shots"]) else n/rate
    p.update(status="retimed_actual_audio",narration_source="temporary",narration_audio=a.wav,audio_duration=n/rate,retime_note="Free eSpeak NG en-us, independently synthesized sentence WAVs at speed "+str(a.speed)+". Inter-sentence reference gaps preserved; sentence bounds measured from PCM chunk lengths (including natural TTS padding), not word-level alignment. Reference duration 101.20 s is not the actual audio duration. Replace with approved recording and retime before final rendering.")
    if a.match_reference:
        p["retime_note"]="Free eSpeak NG en-us at "+str(a.speed)+"; each complete sentence locally tempo-adjusted using FFmpeg atempo and padded at the end to its reference window, no speech truncation; actual PCM chunks measured. Proof timing only; re-align approved recording."
        wav.with_name("temporary_pacing.json").write_text(json.dumps(pace,indent=2)+"\n")
    result=validate(p,root)
    path.write_text(json.dumps(p,indent=2)+"\n")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
