#!/usr/bin/env python3
"""Pixel-level expression duplicate audit on the rendered face region."""
import argparse
import itertools
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops

EXPRESSIONS=["neutral","happy","smug","tired","worried","laughing","shocked","surprised","sad","unimpressed","embarrassed","angry","sleep_closed"]
# Fixed normalized crop covers brows, eyes and mouth while excluding most hair,
# shoulders and studio background that would dilute face-only differences.
CROP=(.30,.28,.70,.82)
NEAR_MAE_MAX=2.8
NEAR_CHANGED_FRACTION_MAX=.03
PIXEL_THRESHOLD=10

def load_face(path):
    with Image.open(path) as im:
        rgb=im.convert("RGB")
        w,h=rgb.size
        box=(round(CROP[0]*w),round(CROP[1]*h),round(CROP[2]*w),round(CROP[3]*h))
        return rgb.crop(box).resize((256,346),Image.Resampling.LANCZOS)

def compare(a,b):
    aa=np.asarray(a,dtype=np.int16);bb=np.asarray(b,dtype=np.int16)
    delta=np.abs(aa-bb)
    mae=float(delta.mean())
    changed=float((delta.max(axis=2)>PIXEL_THRESHOLD).mean())
    return {"mae_rgb":round(mae,5),"changed_pixel_fraction":round(changed,6),
            "max_channel_delta":int(delta.max()),"exact":bool(not np.any(delta))}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--actor",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    root=Path(args.input);out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    images={}
    missing=[]
    for expr in EXPRESSIONS:
        path=root/(args.actor+"_"+expr+".png")
        if path.is_file():images[expr]=load_face(path)
        else:missing.append(expr)
    exact=[];near=[]
    for left,right in itertools.combinations(images,2):
        m=compare(images[left],images[right])
        row={"left":left,"right":right,**m}
        if m["exact"]:exact.append(row)
        elif m["mae_rgb"]<=NEAR_MAE_MAX and m["changed_pixel_fraction"]<=NEAR_CHANGED_FRACTION_MAX:
            near.append(row)
    report={"actor":args.actor,"expressions_expected":len(EXPRESSIONS),"expressions_rendered":len(images),
        "missing_expressions":missing,"face_crop_normalized":[256,346],"near_duplicate_thresholds":{
            "mean_absolute_rgb_error_max":NEAR_MAE_MAX,"changed_pixel_fraction_max":NEAR_CHANGED_FRACTION_MAX,
            "per_pixel_channel_threshold":PIXEL_THRESHOLD},
        "exact_duplicate_pairs":exact,"near_duplicate_pairs":near,
        "pass":len(images)==len(EXPRESSIONS) and not exact}
    out.write_text(json.dumps(report,indent=2)+"\n")
    print("EXPRESSION_PIXEL_QA "+json.dumps({"actor":args.actor,"rendered":len(images),
        "exact_duplicates":len(exact),"near_duplicates":len(near),"missing":missing},sort_keys=True),flush=True)
    for pair in exact+near:print("EXPRESSION_PAIR_FLAG "+json.dumps(pair,sort_keys=True),flush=True)
    if not report["pass"]:raise SystemExit(1)
if __name__=="__main__":main()
