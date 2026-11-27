#!/usr/bin/env python3
"""Create paired frame strips showing face and body acting across both beats."""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

LEAD=[(1,"NEUTRAL"),(12,"NEUTRAL HOLD"),(20,"SURPRISE START"),(32,"SURPRISE"),(44,"SURPRISE END"),(46,"LAUGH START"),(68,"LAUGH"),(96,"LAUGH END")]
FRIEND=[(97,"NEUTRAL"),(108,"NEUTRAL HOLD"),(112,"EMBARRASSED START"),(126,"EMBARRASSED"),(144,"EMBARRASSED"),(156,"EMBARRASSED END")]

def make(root,picks,label,out):
    tile=(400,225);header=58;footer=32;cols=4;rows=(len(picks)+cols-1)//cols
    board=Image.new("RGB",(cols*tile[0],header+rows*(tile[1]+42)+footer),(22,26,31))
    draw=ImageDraw.Draw(board)
    try:
        title=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",27)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",17)
    except OSError:title=font=ImageFont.load_default()
    draw.text((16,12),label.upper()+" — HEAD / BODY REACTION",font=title,fill=(255,255,255))
    for i,(frame,stage) in enumerate(picks):
        p=root/("frame_%06d.png"%frame)
        if not p.is_file():raise FileNotFoundError(p)
        with Image.open(p) as im:im=im.convert("RGB").resize(tile,Image.Resampling.LANCZOS)
        x=(i%cols)*tile[0];y=header+(i//cols)*(tile[1]+42)
        board.paste(im,(x,y))
        draw.rectangle((x,y+tile[1],x+tile[0],y+tile[1]+42),fill=(9,13,18))
        draw.text((x+10,y+tile[1]+10),f"FRAME {frame}  •  {stage}",font=font,fill=(255,255,255))
    out.parent.mkdir(parents=True,exist_ok=True);board.save(out)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output-dir",required=True);args=ap.parse_args()
    root=Path(args.input);out=Path(args.output_dir)
    lead=make(root,LEAD,"Lead: neutral → surprise → laugh",out/"lead_emotional_strip.png")
    friend=make(root,FRIEND,"Friend: neutral → embarrassed",out/"friend_emotional_strip.png")
    # One paired overview, preserving the two separate performance strips as well.
    tile=(400,225);board=Image.new("RGB",(tile[0]*4,(tile[1]+42)*4),(22,26,31))
    picks=[(root/f"frame_{n:06d}.png",f"Lead {stage} · {n}") for n,stage in LEAD[:4]]
    picks += [(root/f"frame_{n:06d}.png",f"Lead {stage} · {n}") for n,stage in LEAD[4:]]
    for i,(p,label) in enumerate(picks):
        with Image.open(p) as im:im=im.convert("RGB").resize(tile,Image.Resampling.LANCZOS)
        x=(i%4)*tile[0];y=(i//4)*(tile[1]+42);board.paste(im,(x,y))
        d=ImageDraw.Draw(board);d.rectangle((x,y+tile[1],x+tile[0],y+tile[1]+42),fill=(9,13,18))
        d.text((x+10,y+tile[1]+10),label,fill=(255,255,255))
    board.save(out/"lead_emotional_overview.png")
    print(f"EMOTIONAL_STRIPS lead={lead} friend={friend}",flush=True)
if __name__=="__main__":main()
