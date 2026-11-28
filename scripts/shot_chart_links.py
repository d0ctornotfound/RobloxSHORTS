"""Inspectably draw chart links by cast ID; design board only, not an R6 render."""
import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def dashed_arrow(draw,positions,source,target,color,width=5,dash=15,gap=9):
    x,y=positions[source];u,v=positions[target];dx,dy=u-x,v-y;length=math.hypot(dx,dy)
    if length<1:raise ValueError("coincident link endpoints")
    nx,ny=dx/length,dy/length
    for t in range(0,int(length)-18,dash+gap):
        end=min(t+dash,length-18)
        draw.line((x+nx*t,y+ny*t,x+nx*end,y+ny*end),fill=color,width=width)
    draw.polygon([(u,v),(u-20*nx+9*ny,v-20*ny-9*nx),(u-20*nx-9*ny,v-20*ny+9*nx)],fill=color)

def board(cast,chart,replacement=False,limit=None):
    im=Image.new("RGB",(1080,1920),"#f5ebd6");d=ImageDraw.Draw(im)
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    title=ImageFont.truetype(font,50);label=ImageFont.truetype(font,37);small=ImageFont.truetype(font,25)
    d.text((540,65),chart["title_final" if replacement else "title_initial"],font=title,fill="#182536",anchor="mt")
    d.text((540,138),"DESIGN BOARD — ID LABELS, NOT CAST RENDERS",font=small,fill="#614a40",anchor="mt")
    d.text((180,240),"GIRLS",font=label,fill="#182536",anchor="mm");d.text((900,240),"BOYS",font=label,fill="#182536",anchor="mm")
    positions={};left=set(chart["girls"])
    for col,ids in enumerate((chart["girls"],chart["boys"])):
        for i,cid in enumerate(ids):
            yy=330+145*i;xx=180 if col==0 else 900
            d.rounded_rectangle((xx-135,yy-45,xx+135,yy+45),radius=18,fill="#fffaf0",outline="#6b675d",width=3)
            d.text((xx,yy),"Me" if cid=="narrator" else cid.title(),font=label,fill="#182536",anchor="mm")
            positions[cid]=(xx+140 if col==0 else xx-140,yy)
    links=chart["replacement_links" if replacement else "initial_links"]
    if limit is not None:links=links[:limit]
    for i,link in enumerate(links):
        color=("#376e9e","#b04f3e","#4c8161","#8d5b97")[i%4]
        dashed_arrow(d,positions,link["from"],link["to"],color)
    d.text((540,1830),f"{len(links)} links • authored by Otis",font=label,fill="#182536",anchor="mm")
    return im

def main():
    a=argparse.ArgumentParser();a.add_argument("--cast",required=True);a.add_argument("--staging",required=True);a.add_argument("--output",required=True);args=a.parse_args()
    c=json.loads(Path(args.cast).read_text());s=json.loads(Path(args.staging).read_text());out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    for name,rep in (("chart_initial_design",False),("chart_replacement_design",True)):
        board(c,s["chart"],rep).save(out/(name+".png"))
if __name__=="__main__":main()
