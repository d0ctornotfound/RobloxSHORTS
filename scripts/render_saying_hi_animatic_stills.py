"""Run independent bounded held-pose processes for the animatic's actual still sources."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument("--group",type=int,required=True);p.add_argument("--groups",type=int,required=True);p.add_argument("--map",required=True);p.add_argument("--lineup",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    plan=json.loads(Path("stories/saying_hi_plan.json").read_text());items=[]
    for s in plan["shots"]:
        segs=s.get("animatic_segments") or [{"still_path":s["still_path"]}]
        for x in segs:
            if x.get("still_path"):items.append((int(s["sentence_ids"][0]),x.get("variant"),Path(x["still_path"]).name))
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True);failed=[]
    for i,(shot,variant,name) in enumerate(items):
        if i%a.groups!=a.group:continue
        work=output/("detail_"+Path(name).stem);work.mkdir(exist_ok=True)
        cmd=["timeout","--kill-after=20s","8m","blender","-b","--python-exit-code","1","--python","scripts/render_saying_hi_shot.py","--","--shot",str(shot),"--mode","still","--map",a.map,"--lineup",a.lineup,"--output",str(work)]
        if variant:cmd+=["--variant",variant]
        with (work/"render.log").open("w") as log:
            r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        if r.returncode or not (work/"held_pose.png").is_file():failed.append({"shot":shot,"variant":variant,"exit_code":r.returncode});continue
        shutil.copyfile(work/"held_pose.png",output/name)
        print("ACTUAL STILL",name,flush=True)
    (output/f"group_{a.group}_status.json").write_text(json.dumps({"failed":failed},indent=2)+"\n")
    if failed:sys.exit(1)
if __name__=="__main__":main()
