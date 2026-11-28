#!/usr/bin/env python3
"""Isolated Chapter 4 static candidate render + unchanged clearance replay."""
import argparse,json,sys,os,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from PIL import Image,ImageDraw
from render_clothing_character import studio,render_view,contact_sheet,font
from chapter4_wardrobe import build_character,WARDROBE
from chapter4_hair import DEFAULTS,HAIR
from facial_expressions import disable_blinking
from r6_character import bounds,mesh_points

def actor(role,hair="default",outfit="default"):
    a=build_character("Chapter 4 "+role,role,hair,outfit)
    a.root.location=(0,0,0);a.root.rotation_euler=(0,0,0);a.pose("neutral")
    disable_blinking(bpy.context.scene,[a])
    bpy.context.view_layer.update()
    return a

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--actor",choices=tuple(DEFAULTS),required=True)
    ap.add_argument("--kind",choices=("hair","outfit","clearance"),required=True)
    ap.add_argument("--item",required=True)
    ap.add_argument("--motion",choices=("walk","sit"))
    ap.add_argument("--output",required=True)
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if args.kind=="clearance":
        import render_clothing_clearance as replay
        # Inject only the new actor factory; motion/replay implementation remains locked.
        replay.build_actor=lambda role:actor(role,outfit=args.item)
        sys.argv=[sys.argv[0],"--","--actor",args.actor,"--motion",args.motion,"--output",str(out)]
        replay.main()
        p=out/"manifest.json";m=json.loads(p.read_text());m["outfit"]=args.item
        p.write_text(json.dumps(m,indent=2)+"\n")
        return
    scene,cam,walls=studio()
    a=actor(args.actor,hair=args.item if args.kind=="hair" else "default",
            outfit=args.item if args.kind=="outfit" else "default")
    if args.kind=="hair":
        lo,hi=bounds(v for ob in a.meshes if "head ch4 hair" in ob.name or "beanie" in ob.name
                     for v in mesh_points(ob))
        headlo,headhi=a.head_bounds
        z=(min(headlo.z,lo.z)+hi.z)/2
        scale=max(1.05,(hi.z-min(headlo.z,lo.z))*1.22)
        views=[("front",(0,-6,z),(0,0,z),scale),("side",(6,0,z),(0,0,z),scale)]
    else:
        views=[("front",(0,-6,1.2),(0,0,1.2),3.0),("side",(6,0,1.2),(0,0,1.2),3.0),
               ("back",(0,6,1.2),(0,0,1.2),3.0),("detail",(0,-4,1.38),(0,0,1.38),1.05)]
    timings={}
    for name,loc,target,scale in views:
        timings[name]=render_view(scene,cam,walls,a,out/(name+".png"),name,loc,target,scale)
    label=args.actor+" / "+args.item
    if args.kind=="outfit":
        sheet=contact_sheet(out,label)
    else:
        board=Image.new("RGB",(2048,1100),(28,31,35));draw=ImageDraw.Draw(board)
        draw.text((20,15),label.upper()+" — HAIR REVIEW",font=font(34),fill="white")
        for i,(name,*_) in enumerate(views):
            with Image.open(out/(name+".png")) as im:board.paste(im.convert("RGB"),(i*1024,76))
            draw.text((i*1024+15,80),name.upper(),font=font(26),fill="white")
        sheet=out/"hair_contact_sheet.png";board.save(sheet)
    m={"actor":args.actor,"kind":args.kind,"item":args.item,"engine":"EEVEE","denoising":False,
       "views":list(timings),"seconds":timings,"sheet":sheet.name,
       "body_vertices":len(a.body.data.vertices),"bones":len(a.armature.data.bones),
       "hair":getattr(a,"chapter4_hair","beanie"),"outfit":a.chapter4_outfit,
       "clothing":a.clothing_report}
    (out/"manifest.json").write_text(json.dumps(m,indent=2)+"\n")
    print("CHAPTER4_REVIEW_COMPLETE "+json.dumps(m),flush=True)
if __name__=="__main__":main()
