#!/usr/bin/env python3
"""Build a partial-safe 13-expression contact sheet from whatever stills landed."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

EXPRESSIONS = ["neutral","happy","smug","tired","worried","laughing","shocked","surprised","sad","unimpressed","embarrassed","angry","sleep_closed"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="render/lead-pilot/stills")
    ap.add_argument("--output",default="render/lead-pilot/lead_expression_contact_sheet.png")
    args=ap.parse_args()
    root=Path(args.input);out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    tile=(320,180);cols=4;rows=4
    board=Image.new("RGB",(cols*tile[0],rows*(tile[1]+36)),(25,29,34))
    draw=ImageDraw.Draw(board)
    try:font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",18)
    except OSError:font=ImageFont.load_default()
    found=0
    for i,expr in enumerate(EXPRESSIONS):
        p=root/("lead_"+expr+".png")
        x=(i%cols)*tile[0];y=(i//cols)*(tile[1]+36)
        if p.is_file():
            with Image.open(p) as im:
                im=im.convert("RGB");im.thumbnail(tile,Image.Resampling.LANCZOS)
                canvas=Image.new("RGB",tile,(12,15,18));canvas.paste(im,((tile[0]-im.width)//2,(tile[1]-im.height)//2))
                board.paste(canvas,(x,y))
            found+=1
        else:
            draw.rectangle((x,y,x+tile[0],y+tile[1]),fill=(48,52,58))
            draw.text((x+14,y+72),"NOT RENDERED",font=font,fill=(235,190,110))
        draw.rectangle((x,y+tile[1],x+tile[0],y+tile[1]+36),fill=(10,13,17))
        draw.text((x+10,y+tile[1]+7),expr.upper(),font=font,fill=(255,255,255))
    draw.text((10,rows*(tile[1]+36)-28),f"LEAD EXPRESSION PILOT — {found}/13 stills completed",font=font,fill=(255,255,255))
    board.save(out)
    print(f"PILOT_CONTACT_SHEET {out} completed={found}/13",flush=True)
    if found==0: raise SystemExit("No stills available for contact sheet")
if __name__=="__main__":main()
