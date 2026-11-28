"""Story chart artwork using actual rendered cast portraits, not substitute icons.
Identical coordinates for Otis's first and replacement charts.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from shot_chart_links import dashed_arrow
import math

W,H=1080,1920
def portrait_crop(path,index):
    im=Image.open(path).convert("RGB")
    # Smoke lineup camera is orthographic, width 14.2 units; 1.30-unit spacing.
    center=im.width*(.5+(index-4.5)*1.30/14.2)
    # Common crop includes head/upper chest even for uniformly shorter Brody.
    r=(round(center-im.width*.043),round(im.height*.16),round(center+im.width*.043),round(im.height*.50))
    return im.crop(r).resize((100,112),Image.Resampling.LANCZOS)

def portrait_board(stage,lineup_dir,mode,progress=1.0):
    chart=stage["chart"];p=Path(lineup_dir)
    im=Image.new("RGB",(W,H),"#f5ebd6");d=ImageDraw.Draw(im)
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    title=ImageFont.truetype(font,52);label=ImageFont.truetype(font,35);small=ImageFont.truetype(font,27)
    replacement=mode=="replacement";d.text((540,70),chart["title_final" if replacement else "title_initial"],font=title,fill="#182536",anchor="mt")
    d.text((540,150),"DRAWN BY OTIS",font=small,fill="#614a40",anchor="mt")
    d.text((160,242),"GIRLS",font=label,fill="#182536",anchor="mm");d.text((920,242),"BOYS",font=label,fill="#182536",anchor="mm")
    positions={}
    for col,(ids,sex) in enumerate(((chart["girls"],"girls"),(chart["boys"],"boys"))):
        for i,cid in enumerate(ids):
            yy=330+145*i;xx=165 if col==0 else 915
            if mode=="columns" and (i+10*col)>=max(1,math.ceil(20*progress)):continue
            x=xx-150;d.rounded_rectangle((x,yy-61,xx+150,yy+61),radius=12,fill="#fffaf0",outline="#6b675d",width=2)
            portrait=portrait_crop(p/("lineup_"+sex+".png"),i)
            im.paste(portrait,(x+4 if col==0 else xx+46,yy-56))
            d.text((xx+51 if col==0 else xx-49,yy),"Me" if cid=="narrator" else cid.title(),font=label,fill="#182536",anchor="mm")
            positions[cid]=(xx+154 if col==0 else xx-154,yy)
    links=chart["replacement_links" if replacement else "initial_links"]
    count=0 if mode=="columns" else min(len(links),max(0,math.floor(len(links)*progress+1e-8)))
    palette=("#376e9e","#b04f3e","#4c8161","#8d5b97")
    # Separate arrowheads when several arrows meet one row; same cast endpoint.
    total={};seen={}
    for link in links:total[link["to"]]=total.get(link["to"],0)+1
    for i,link in enumerate(links[:count]):
        src,tgt=link["from"],link["to"];x,y=positions[tgt]
        idx=seen.get(tgt,0);seen[tgt]=idx+1
        adjusted=dict(positions);adjusted[tgt]=(x,y+(idx-(total[tgt]-1)/2)*13)
        dashed_arrow(d,adjusted,src,tgt,palette[i%len(palette)],width=6,dash=18,gap=9)
    if mode=="zero":
        for cid in chart["boys"][3:]:
            x,y=positions[cid];d.text((x-15,y),"0",font=label,fill="#b04f3e",anchor="rm")
    if mode=="me":
        x,y=positions["narrator"];d.rounded_rectangle((x+1,y-65,1070,y+65),radius=14,outline="#db7a20",width=8)
        d.text((x-15,y),"0",font=label,fill="#b04f3e",anchor="rm")
    d.text((540,1830),f"{count} links",font=label,fill="#182536",anchor="mm")
    return im,{"arrows":count,"links":links[:count],"mode":mode,"progress":progress,"portrait_source":"actual smoke lineup row PNG crops"}
