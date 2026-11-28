#!/usr/bin/env python3
"""Publish source render PNG sheets without resampling; combine two clearance strips losslessly."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

R2 = (
    "teacher-hair-default-none", "teacher-hair-rounded_bob-none",
    "dad-hair-default-none", "dad-hair-short_crew-none", "dad-hair-side_part-none",
    "librarian-hair-default-none", "librarian-hair-rounded_bob-none",
    "patron_green-hair-messy_fringe-none", "patron_blue-hair-curly_crop-none",
    "lead-outfit-forest_bomber-none", "dad-outfit-charcoal_suit-none",
    "teacher-outfit-navy_formal-none", "librarian-outfit-plum_blazer-none",
    "librarian-outfit-teal_cardigan-none", "patron_green-outfit-school_polo-none",
    "patron_blue-outfit-sports_kit-none", "lead-clearance-forest_bomber-walk",
    "lead-clearance-forest_bomber-sit", "friend-clearance-rugby_polo-walk",
    "friend-clearance-rugby_polo-sit",
)
R3 = (
    "teacher-hair-default-none", "teacher-hair-rounded_bob-none",
    "lead-outfit-forest_bomber-none", "lead-clearance-forest_bomber-walk",
    "lead-clearance-forest_bomber-sit",
)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run():
    root=Path("assets/chapter4_review")
    ledger=[]
    for round_name,src,items,run_id in (
        ("round2",Path(sys.argv[1]),R2,"46096074284"),
        ("round3",Path(sys.argv[2]),R3,sys.argv[3])):
        dest=root/round_name
        dest.mkdir(parents=True,exist_ok=True)
        for item in items:
            source=src/("chapter4-"+item)
            if not source.is_dir(): raise RuntimeError("Missing artifact: "+str(source))
            manifest=source/"manifest.json"
            data=json.loads(manifest.read_text())
            png=dest/(item+".png")
            if "-clearance-" in item:
                files=[source/"front_strip.png",source/"side_strip.png"]
                ims=[Image.open(p).convert("RGB") for p in files]
                board=Image.new("RGB",(max(i.width for i in ims),sum(i.height for i in ims)),(28,31,35))
                y=0
                for im in ims:
                    board.paste(im,(0,y));y+=im.height
                board.save(png,format="PNG",compress_level=6)
            else:
                files=[source/("hair_contact_sheet.png" if "-hair-" in item else "clothing_contact_sheet.png")]
                shutil.copyfile(files[0],png)
            with Image.open(png) as im:
                if im.format!="PNG": raise RuntimeError("Non PNG: "+str(png))
                size=list(im.size);im.verify()
            record={"path":str(png),"run_id":run_id,"artifact":"chapter4-"+item,
                    "sha256":digest(png),"size":size,"source_pngs":{p.name:digest(p) for p in files},
                    "manifest":data}
            ledger.append(record)
            print("PUBLISHED",png,size,record["sha256"],flush=True)
        assert len(list(dest.glob("*.png")))==len(items), f"Unexpected board count: {dest}"
    assert len(ledger)==25
    (root/"manifest.json").write_text(json.dumps(ledger,indent=2)+"\n")
    (root/"README.md").write_text("# Chapter 4 actual render evidence\n\nRound 2: 20 boards; Round 3: 5 boards. Original static PNGs copied without resampling; clearance front and side strips stacked losslessly at native resolution. See manifest.json for source run, artifact, hashes, sizes and original manifests. Supervisor review is required; file publication is not approval.\n")
if __name__=="__main__":
    run()
