"""Author original classic R6 black-ink expression decals (transparent PNG).
Run with system Python + Pillow. No external image service/assets."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

EXPRESSIONS=("neutral","happy","smug","tired","worried","laughing","shocked","surprised","sad","unimpressed","embarrassed","angry","sleep_closed")

def build_faces(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    S=2048
    ink=(10,10,12,255);blush=(205,83,91,105)
    for expr in (*EXPRESSIONS,"blink_half"):
        im=Image.new("RGBA",(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
        def box(x0,y0,x1,y1):return tuple(round(x*S) for x in (x0,y0,x1,y1))
        def oval(x,y,w,h,fill=ink):d.ellipse(box(x-w/2,y-h/2,x+w/2,y+h/2),fill=fill)
        def curve(start,control,end,width=.035,fill=ink):
            pts=[((1-t)**2*start[0]+2*t*(1-t)*control[0]+t*t*end[0],
                  (1-t)**2*start[1]+2*t*(1-t)*control[1]+t*t*end[1]) for t in (i/48 for i in range(49))]
            d.line([(round(x*S),round(y*S)) for x,y in pts],fill=fill,width=round(width*S),joint="curve")
            for x,y in (pts[0],pts[-1]):oval(x,y,width,width,fill)
        for i,x in enumerate((.34,.66)):
            sign=-1 if i==0 else 1
            if expr=="blink_half":
                curve((x-.075,.365),(x,.385),(x+.075,.365),.027)
                oval(x,.397,.036,.050)
            elif expr=="sleep_closed":
                curve((x-.075,.385),(x,.435),(x+.075,.385),.027)
            elif expr=="laughing":
                curve((x-.075,.405),(x,.275),(x+.075,.405),.036)
            elif expr=="tired":
                # Heavy, low upper lid and small pupil: visibly drowsy.
                oval(x+.012,.405,.070,.070)
                curve((x-.090,.365),(x,.402),(x+.090,.365),.052)
                curve((x-.065,.475),(x,.495),(x+.065,.475),.014,(95,76,68,150))
            elif expr=="unimpressed":
                # Half-lids remain flatter and more level than tired lids.
                oval(x,.39,.075,.085)
                curve((x-.088,.350),(x,.352),(x+.088,.350),.034)
            elif expr=="smug":
                oval(x+.02,.39,.065,.09)
                curve((x-.075,.34),(x,.315),(x+.075,.345),.026)
            elif expr=="embarrassed":
                oval(x-.018*sign,.415,.066,.090)
                curve((x-.078,.34),(x,.325),(x+.078,.34),.026)
            elif expr=="angry":
                oval(x,.39,.071,.085)
                if i==0:curve((x-.09,.285),(x,.305),(x+.09,.345),.045)
                else:curve((x-.09,.345),(x,.305),(x+.09,.285),.045)
            elif expr=="shocked":
                oval(x,.39,.112,.215)
                oval(x-.018,.35,.024,.034,(255,255,255,235))
                curve((x-.095,.205),(x,.175),(x+.095,.205),.025)
            elif expr=="surprised":
                oval(x,.39,.083,.165)
                oval(x-.012,.365,.018,.025,(255,255,255,235))
                curve((x-.09,.275),(x,.245),(x+.09,.275),.025)
            else:
                oval(x,.39,.078,.115)
                if expr in ("worried","sad"):
                    if i==0:curve((x-.09,.325),(x,.285),(x+.09,.305),.032)
                    else:curve((x-.09,.305),(x,.285),(x+.09,.325),.032)
                else:
                    curve((x-.09,.315),(x,.30),(x+.09,.315),.025)
        if expr=="embarrassed":
            oval(.235,.565,.12,.065,blush);oval(.765,.565,.12,.065,blush)
        if expr=="laughing":
            oval(.5,.675,.37,.255)
            d.rounded_rectangle(box(.355,.585,.645,.625),radius=round(.016*S),fill=(255,255,255,255))
            oval(.5,.755,.13,.05,(175,64,68,255))
        elif expr=="shocked":
            oval(.5,.68,.265,.305)
            oval(.5,.765,.155,.060,(175,64,68,255))
        elif expr=="surprised":
            oval(.5,.68,.205,.235)
            oval(.5,.742,.12,.045,(175,64,68,255))
        elif expr=="happy":
            curve((.27,.615),(.50,.86),(.73,.615),.052)
        elif expr=="sad":
            curve((.30,.735),(.50,.525),(.70,.735),.048)
        elif expr=="angry":
            curve((.32,.69),(.50,.575),(.68,.69),.045)
        elif expr=="worried":
            curve((.32,.735),(.50,.59),(.68,.735),.038)
        elif expr=="embarrassed":
            curve((.405,.68),(.50,.73),(.595,.68),.028)
        elif expr=="smug":
            curve((.34,.69),(.55,.70),(.69,.625),.042)
        elif expr=="unimpressed":
            # Flat, slightly sideways line: restrained disapproval, not fatigue.
            curve((.34,.675),(.51,.675),(.67,.665),.034)
        elif expr=="tired":
            # Slack, softly open mouth with a small relaxed lower lip.
            oval(.50,.685,.105,.060)
            curve((.445,.742),(.50,.754),(.555,.742),.012,(90,70,62,180))
        else:
            curve((.35,.66),(.50,.69),(.65,.66),.035)
        im.resize((1024,1024),Image.Resampling.LANCZOS).save(output/(expr+".png"),optimize=True)
    return [output/(name+".png") for name in EXPRESSIONS]

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default="assets/r6_faces");a=p.parse_args();build_faces(a.output)
