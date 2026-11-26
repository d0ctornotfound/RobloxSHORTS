"""Render-time-independent caption, original sound synthesis and final MP4 edit."""
import argparse
from array import array
from fractions import Fraction
import json
import math
from pathlib import Path
import random
import subprocess
import wave

RATE=48000


def run(cmd):
    subprocess.run([str(x) for x in cmd],check=True)


def wav(path,data):
    samples=array("h",(round(max(-1,min(1,x))*32767) for x in data))
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(samples.tobytes())


def music(duration):
    """Original generative warm electric-piano-like arpeggio, no recordings."""
    data=array("f",[0])*round(duration*RATE)
    # Original, deliberately understated chord voicings and pattern.
    chords=[(48,55,59,64),(45,52,55,60),(50,57,60,65),(43,50,53,59)]
    for k in range(math.ceil(duration/.375)):
        t=k*.375
        chord=chords[(k//8)%len(chords)]
        notes=[chord[(0,2,1,3,1,2,3,1)[k%8]]]
        if k%4==0:
            notes.append(chord[0]-12)
        for midi in notes:
            hz=440*2**((midi-69)/12)
            first=round(t*RATE)
            for j in range(min(round(.95*RATE),len(data)-first)):
                dt=j/RATE
                envelope=min(1,dt/.018)*math.exp(-dt*4.8)*min(1,(.95-dt)/.08)
                tone=math.sin(math.tau*hz*dt)+.23*math.sin(math.tau*2*hz*dt)+.08*math.sin(math.tau*3*hz*dt)
                data[first+j]+=.053*envelope*tone
    for i in range(len(data)):
        t=i/RATE
        data[i]*=min(1,t/.18,(duration-t)/.40)
    return data


def effects(spec):
    data=array("f",[0])*round(spec["duration"]*RATE)
    rng=random.Random(81)
    lengths={"ding":.47,"slide":.72,"whoosh":.42,"thud":.36}
    for event in spec["sfx"]:
        kind=event["kind"]
        first=round(event["time"]*RATE)
        length=lengths[kind]
        noise=0
        for i in range(min(round(length*RATE),len(data)-first)):
            t=i/RATE
            noise=.82*noise+.18*rng.uniform(-1,1)
            attack=min(1,t/.009)
            tail=max(0,1-t/length)
            if kind=="ding":
                v=.14*(math.sin(math.tau*880*t)+.43*math.sin(math.tau*1320*t))*math.exp(-t*7)
            elif kind=="slide":
                v=.22*noise*math.sin(math.pi*t/length)**2+.036*math.sin(math.tau*(330*t-90*t*t))*tail
            elif kind=="whoosh":
                v=.19*noise*math.sin(math.pi*t/length)**2
            else:
                v=.26*math.sin(math.tau*(100*t-85*t*t))*math.exp(-t*18)+.16*noise*math.exp(-t*15)
            data[first+i]+=attack*tail*v
    return data


def ass_time(frame,fps):
    # Round down to centiseconds so a cue becomes active at its intended frame.
    cs=frame*100//fps
    return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"


def captions(spec,fps,output):
    events=[]
    words=[]
    for slot in spec["captions"]:
        tokens=slot["text"].split()
        first,last=round(slot["start"]*fps),round(slot["end"]*fps)
        assert last-first>=len(tokens)
        for i,word in enumerate(tokens):
            start=first+(last-first)*i//len(tokens)
            end=first+(last-first)*(i+1)//len(tokens)
            events.append(f"Dialogue: 0,{ass_time(start,fps)},{ass_time(end,fps)},Default,,0,0,0,,{word}")
            words.append({"word":word,"first_frame":start+1,"last_frame":end,"start":start/fps,"end":end/fps})
    assert " ".join(x["word"] for x in words)==spec["narration"]
    assert words[0]["first_frame"]==1 and words[-1]["last_frame"]==round(spec["duration"]*fps)
    assert all(a["last_frame"]+1==b["first_frame"] for a,b in zip(words,words[1:]))
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 360
PlayResY: 640
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,12,12,94,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (output/"captions.ass").write_text(header+"\n".join(events)+"\n")
    (output/"word_timing.json").write_text(json.dumps(words,indent=2)+"\n")


def probe(path):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)]))


def mix(output,spec,narration=None):
    """Keep narration at unity gain and duck music under it, not the SFX."""
    duration=spec["duration"]
    cmd=["ffmpeg","-y","-hide_banner","-loglevel","error","-i",output/"music.wav","-i",output/"sfx.wav"]
    if narration:
        cmd+=["-i",narration]
        # The supplied take stays at unity gain, with a conservative music duck
        # throughout the narration slot. Limiter only catches actual clipping.
        graph="[0:a]volume=0.28[m];[2:a]aformat=sample_rates=48000:channel_layouts=mono,apad[n];[m][1:a][n]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.95:level=false[a]"
    else:
        graph="[0:a][1:a]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95:level=false[a]"
    run(cmd+["-filter_complex",graph,"-map","[a]","-t",str(duration),"-ar",str(RATE),"-ac","1",output/"mix.wav"])


def verify_narration_slot(output,spec):
    """Exercise optional narration mix with a synthetic test tone, never ship it."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for name in ("music.wav","sfx.wav"):
            (tmp/name).write_bytes((output/name).read_bytes())
        tone=array("f",(.13*math.sin(math.tau*440*i/RATE) for i in range(RATE)))
        wav(tmp/"test.wav",tone)
        mix(tmp,spec,tmp/"test.wav")
        result=probe(tmp/"mix.wav")
        assert abs(float(result["format"]["duration"])-spec["duration"])<.02
        assert (tmp/"mix.wav").read_bytes()!=(output/"mix.wav").read_bytes()
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--story",default="stories/the_last_slice.json")
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--frames",default="render/story")
    p.add_argument("--output",default="render/final")
    p.add_argument("--narration",type=Path)
    p.add_argument("--verify-slot",action="store_true")
    a=p.parse_args()
    spec=json.loads(Path(a.story).read_text())
    output=Path(a.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    frames=Path(a.frames).resolve()
    fps,w,h=(12,432,768) if a.profile=="preview" else (24,1080,1920)
    count=round(spec["duration"]*fps)
    assert {f.name for f in frames.glob("frame_*.png")}=={f"frame_{i:04d}.png" for i in range(1,count+1)}
    captions(spec,fps,output)
    wav(output/"music.wav",music(spec["duration"]))
    wav(output/"sfx.wav",effects(spec))
    mix(output,spec,a.narration)
    slot_tested=verify_narration_slot(output,spec) if a.verify_slot else False
    # Local output directory avoids filter path escaping issues.
    import os
    os.chdir(output)
    filename=spec["id"]+".mp4"
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-framerate",fps,"-start_number","1",
         "-i",frames/"frame_%04d.png","-i","mix.wav","-vf","hqdn3d=2.5:2:3:2.5,ass=captions.ass","-map","0:v:0","-map","1:a:0",
         "-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
         "-t",spec["duration"],"-movflags","+faststart",filename])
    data=probe(filename)
    video=next(s for s in data["streams"] if s["codec_type"]=="video")
    audio=next(s for s in data["streams"] if s["codec_type"]=="audio")
    assert (video["width"],video["height"])==(w,h)
    assert Fraction(video["avg_frame_rate"])==fps
    assert int(video["nb_frames"])==count
    assert abs(float(data["format"]["duration"])-spec["duration"])<.05
    assert audio["codec_name"]=="aac"
    data["edit"]={"narration_included":bool(a.narration),"narration_slot_tested":slot_tested,
        "caption_mode":"single word, burned in","caption_words":len(spec["narration"].split()),
        "music":"original procedural","sfx":spec["sfx"]}
    Path("metadata.json").write_text(json.dumps(data,indent=2)+"\n")
    print("STAGE_C_EDIT_VALIDATED",json.dumps({"resolution":[w,h],"fps":fps,"duration":spec["duration"],
        "frames":count,"audio_codec":audio["codec_name"],**data["edit"]}),flush=True)


if __name__=="__main__":
    main()
