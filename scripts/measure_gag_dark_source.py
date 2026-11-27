"""Intersect exact baseline single-frame H264 dark mask with registered IDs.
Report all object/material pairs and mutually exclusive region totals.
Ground/house categories identify dark surfaces, not proven shadow causation."""
import json,subprocess,hashlib
from pathlib import Path
from PIL import Image
import numpy as np
from collections import Counter

def region(o,m):
    t=(o+" "+m).lower()
    if o=="BACKGROUND":return "background / no object ID"
    if any(k in t for k in ("strand lock","directional strands","fitted hair cap","head hair","head fringe")):return "hair"
    if "lead / pants" in t:return "trousers"
    if "lead / shirt" in t or "lead / sleeve" in t:return "hoodie / sleeves (includes exposed hand texture)"
    if any(k in t for k in ("sidewalk","concrete","asphalt","road dash","paving joint","lawn","road")):return "ground / ground shadow"
    if any(k in t for k in ("house","gable","roof","door.","window","siding","facade","brick")):return "house / house shadow"
    if any(k in t for k in ("face","skin","head")):return "face / skin / head other"
    if any(k in t for k in ("gift","ball","ribbon","bow")):return "gift / ball"
    if any(k in t for k in ("fence","lamp","tree","hedge","plant","car")):return "street props / vegetation"
    return "other"
def encode(p):
    video=p.with_suffix(".mp4")
    subprocess.run(["ffmpeg","-v","error","-y","-framerate","30","-i",str(p),"-frames:v","1","-c:v","libx264","-crf","17","-pix_fmt","yuv420p",str(video)],check=True)
    rgb=np.asarray(Image.open(p).convert("RGB"))
    raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(video),"-f","rawvideo","-pix_fmt","rgb24","-"])
    return np.frombuffer(raw,dtype=np.uint8).reshape(rgb.shape)
def main():
    out=Path("render/tests");baseline=Path("render/baseline")
    summaries=[]
    for f in (61,166):
        name=f"test_{f:04d}.png";orig=baseline/name;rep=out/name
        assert orig.exists() and rep.exists()
        encoded=encode(orig);repeat=encode(rep)
        dark=encoded.max(axis=2)<=24
        ids=np.load(out/f"ids_{f:04d}.npz")
        ob,ma=ids["object"],ids["material"]
        assert ob.shape==ma.shape==dark.shape
        mapping=json.loads((out/f"ids_{f:04d}.json").read_text())
        total=dark.size;count=int(dark.sum())
        names={int(k):v["name"] for k,v in mapping["objects"].items()}
        mats={int(k):v for k,v in mapping["materials"].items()}
        pairs=Counter(zip(ob[dark].tolist(),ma[dark].tolist()))
        regions=Counter();detail=[]
        def pct(n):return n/total*100
        for (o,m),n in pairs.most_common():
            on=names.get(o,"BACKGROUND" if o==0 else f"unknown object {o}")
            mn=mats.get(m,"NO MATERIAL ID" if m==0 else f"unknown material {m}")
            reg=region(on,mn);regions[reg]+=n
            detail.append({"object":on,"material":mn,"region":reg,"pixels":n,"percent_frame":pct(n),"percent_near_black":n/max(1,count)*100})
        assert sum(regions.values())==count
        # Overlay is diagnostic only: magenta marks every encoded dark pixel.
        vis=encoded.copy();vis[dark]=[255,0,180]
        Image.fromarray(vis).save(out/f"dark_mask_{f:04d}.png")
        Image.fromarray((dark*255).astype(np.uint8)).save(out/f"mask_{f:04d}.png")
        summary={"frame":f,"baseline_sha256":hashlib.sha256(orig.read_bytes()).hexdigest(),"rerender_sha256":hashlib.sha256(rep.read_bytes()).hexdigest(),"encoded_exact_match":bool(np.array_equal(encoded,repeat)),"encoded_pixel_agreement_percent":float(np.all(encoded==repeat,axis=2).mean()*100),"encoded_dark_mask_disagreement_percent":float((dark!=(repeat.max(axis=2)<=24)).mean()*100),"total_pixels":total,"near_black_pixels":count,"near_black_percent":pct(count),"required_reduction_percentage_points":max(0,pct(count)-2),"regions":[{"region":k,"pixels":n,"percent_frame":pct(n),"percent_near_black":n/max(1,count)*100} for k,n in regions.most_common()],"object_material_pairs":detail,"method":"Original encoded Variant B pixel mask; hard un-antialiased Blender frontmost IDs from repeat of same scene. Edge attribution approximate. Surface category is not proof of shadow causation."}
        summaries.append(summary)
        print("DARK_SOURCE",json.dumps({k:v for k,v in summary.items() if k!="object_material_pairs"}),flush=True)
        print("DARK_SOURCE_TOP_PAIRS",json.dumps({"frame":f,"pairs":detail[:20]}),flush=True)
    (out/"dark_source_analysis.json").write_text(json.dumps(summaries,indent=2)+"\n")
if __name__=="__main__":main()
