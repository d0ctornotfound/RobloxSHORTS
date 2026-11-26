"""Author original classic R6 black-ink expression decals (transparent PNG).
Run with system Python + Pillow. No external image service/assets."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

EXPRESSIONS=("neutral","happy","shocked","sad","unimpressed","laughing")

def build_faces(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    S=2048
    black=(10,10,12,255)
    for expr in EXPRESSIONS:
        im=Image.new("RGBA",(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
        def box(x0,y0,x1,y1):return tuple(round(x*S) for x in (x0,y0,x1,y1))
        def oval(x,y,w,h,fill=black):d.ellipse(box(x-w/2,y-h/2,x+w/2,y+h/2),fill=fill)
        def curve(start,control,end,width=.048):
            pts=[((1-t)**2*start[0]+2*t*(1-t)*control[0]+t*t*end[0],
                  (1-t)**2*start[1]+2*t*(1-t)*control[1]+t*t*end[1]) for t in (i/40 for i in range(41))]
            d.line([(round(x*S),round(y*S)) for x,y in pts],fill=black,width=round(width*S),joint="curve")
            for x,y in (pts[0],pts[-1]):oval(x,y,width,width)
        if expr=="laughing":
            for x in (.34,.66):curve((x-.075,.39),(x,.23),(x+.075,.39),.047)
            oval(.5,.655,.36,.245);d.rounded_rectangle(box(.36,.566,.64,.606),radius=round(.018*S),fill=(255,255,255,255))
        elif expr=="unimpressed":
            for x in (.34,.66):
                oval(x,.365,.079,.125)
                curve((x-.072,.322),(x,.322),(x+.072,.322),.036)
            curve((.37,.65),(.5,.65),(.63,.65),.048)
        else:
            for x in (.34,.66):oval(x,.365,.081,.171 if expr!="shocked" else .215)
            if expr=="shocked":oval(.5,.675,.21,.225)
            elif expr=="sad":curve((.29,.76),(.50,.44),(.71,.76),.050)
            elif expr=="happy":curve((.27,.59),(.50,.94),(.73,.59),.055)
            else:curve((.31,.64),(.50,.77),(.69,.64),.048)
        im.resize((1024,1024),Image.Resampling.LANCZOS).save(output/(expr+".png"),optimize=True)
    return [output/(name+".png") for name in EXPRESSIONS]

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default="assets/r6_faces");a=p.parse_args();build_faces(a.output)
