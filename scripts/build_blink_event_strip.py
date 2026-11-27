#!/usr/bin/env python3
"""Create four-stage strips around every scheduled Lead blink event."""
import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--manifest",required=True)
    ap.add_argument("--actor",default="lead")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    root=Path(args.input);manifest=json.loads(Path(args.manifest).read_text())
    schedules=manifest["neutral_blink_schedules"]
    actor_label=next((x["label"] for x in manifest.get("characters",[]) if x["key"]==args.actor),"Lead")
    schedule_key="Reel "+actor_label
    events=schedules.get(schedule_key)
    if not events:raise RuntimeError("No blink events found for "+schedule_key)
    fps=int(manifest.get("fps",24));total=int(manifest.get("neutral_blink_frames",fps*10))
    stages=("OPEN","CLOSING","CLOSED","OPEN")
    tile=(400,225);header=64;row_h=tile[1]+48
    board=Image.new("RGB",(tile[0]*4,header+row_h*len(events)),(22,26,31))
    draw=ImageDraw.Draw(board)
    try:
        title=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",17)
    except OSError:title=font=ImageFont.load_default()
    draw.text((16,14),f"{actor_label.upper()} — BLINK EVENT FRAMES",font=title,fill=(255,255,255))
    rows=[]
    for i,event in enumerate(events,1):
        first_closed=math.ceil(float(event["start_seconds"])*fps)+1
        first_open=math.ceil(float(event["end_seconds"])*fps)+1
        frame_ids=[max(1,first_closed-2),max(1,first_closed-1),
                   min(total,first_closed),min(total,first_open+1)]
        row={"event":i,"start_seconds":event["start_seconds"],"end_seconds":event["end_seconds"],
             "frames":frame_ids,"stages":list(stages)}
        rows.append(row)
        y=header+(i-1)*row_h
        for col,(frame,stage) in enumerate(zip(frame_ids,stages)):
            p=root/"blink_frames"/("frame_%06d.png"%frame)
            if not p.is_file():raise FileNotFoundError(f"Blink frame missing: {p}")
            with Image.open(p) as im:
                im=im.convert("RGB").resize(tile,Image.Resampling.LANCZOS)
            x=col*tile[0];board.paste(im,(x,y))
            draw.rectangle((x,y+tile[1],x+tile[0],y+tile[1]+48),fill=(9,13,18))
            draw.text((x+10,y+tile[1]+5),f"{stage}  •  FRAME {frame}",font=font,fill=(255,255,255))
            draw.text((x+10,y+tile[1]+27),f"event {i}  •  {event['closed_seconds']:.3f}s",font=font,fill=(192,204,215))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);board.save(out)
    (out.with_suffix(".json")).write_text(json.dumps({"actor":args.actor,"fps":fps,"events":rows},indent=2)+"\n")
    print(f"BLINK_EVENT_STRIP events={len(events)} output={out}",flush=True)
if __name__=="__main__":main()
