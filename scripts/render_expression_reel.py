"""Chapter 2 facial expression, blink and paired-reaction review reel."""
import argparse,json,math,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from PIL import Image,ImageDraw,ImageFont
from mathutils import Vector
from render_stills import configure
from render_demo import cube,material,point_at
from stage_a_cafe import light
from library_character import character
from r6_character import R6Character,EXPRESSIONS
from facial_expressions import enable_blinking,disable_blinking
from library_acting import act,sustained_laugh
from library_animation import pose as motion_pose

REQUIRED={"neutral","happy","laughing","surprised","embarrassed","sad","angry","worried","sleep_closed"}
FPS=24
HOLD=9
ACTOR_SPECS=[
    ("lead","Lead", "variant"),
    ("friend","Friend","variant"),
    ("teacher","Teacher","variant"),
    ("dad","Dad","variant"),
    ("librarian","Librarian","recipe"),
    ("patron_green","Student Green","standard"),
    ("patron_blue","Student Blue","standard"),
]

def studio():
    scene=configure("preview")
    scene.render.engine="CYCLES"
    scene.render.resolution_percentage=100
    scene.render.resolution_x=1280;scene.render.resolution_y=720
    scene.render.fps=FPS;scene.render.fps_base=1
    scene.cycles.samples=24;scene.cycles.use_denoising=False
    scene.cycles.adaptive_threshold=.025;scene.cycles.max_bounces=5
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=0
    world=scene.world.node_tree.nodes.get("Background")
    world.inputs[0].default_value=(.32,.34,.37,1);world.inputs[1].default_value=.55
    gray=material("Expression reel neutral grey studio",(.34,.36,.39))
    cube("Expression reel floor",(0,0,-.12),(200,200,.24),gray,bevel=0)
    cube("Expression reel backdrop",(0,5,5),(200,.12,15),gray,bevel=0)
    light("Neutral key",(-3,-5,6),(0,0,1.5),780,5,(1,.99,.97))
    light("Neutral fill",(4,-4,4),(0,0,1.4),390,5,(.96,.98,1))
    light("Neutral rim",(0,3,5),(0,0,1.6),310,4,(1,1,1))
    bpy.ops.object.camera_add(location=(0,-3.4,2.15))
    cam=bpy.context.object;cam.name="Expression reel camera"
    cam.data.lens=85;cam.data.sensor_fit="HORIZONTAL"
    point_at(cam,(0,0,2.05));scene.camera=cam
    assert not scene.cycles.use_denoising
    return scene,cam

def build_actors(scene):
    actors={}
    for key,label,kind in ACTOR_SPECS:
        if kind=="variant":actor=character("Reel "+label,key)
        elif kind=="recipe":actor=character("Reel "+label,key)
        else:actor=R6Character("Reel "+label,key)
        actor.root.location=(0,0,0);actor.root.rotation_euler=(0,0,0)
        missing=REQUIRED-set(actor.face_materials)
        if missing:raise RuntimeError((label,"missing required decals",sorted(missing)))
        if set(EXPRESSIONS)-set(actor.face_materials):raise RuntimeError((label,"expression inventory incomplete"))
        actors[key]=actor
    return actors

def visible(actor,value):
    for ob in actor.meshes:ob.hide_render=not value

def head_only(actor):
    keep={actor.head,actor.face}
    for ob in actor.accessories:
        name=ob.name.lower()
        if any(k in name for k in ("head","hair","beanie","glasses","bun")):
            keep.add(ob)
    for ob in actor.meshes:ob.hide_render=ob not in keep

def set_camera(cam,scene,mode):
    if mode=="close":
        cam.data.type="PERSP";cam.data.lens=85
        cam.location=(0,-3.4,2.15);point_at(cam,(0,0,2.05))
    elif mode=="emotion":
        cam.data.type="PERSP";cam.data.lens=60
        cam.location=(0,-4.2,2.05);point_at(cam,(0,0,1.28))
    else:
        cam.data.type="ORTHO";cam.data.ortho_scale=8.4
        cam.location=(0,-14,2.0);point_at(cam,(0,0,2.0))
    scene.camera=cam
    bpy.context.view_layer.update()

def render(scene,path):
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    p=Path(path)
    if not p.is_file() or p.stat().st_size<1000:raise RuntimeError("Missing or empty render: "+str(p))

def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).is_file():return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def label_still(src,dst,top,bottom):
    with Image.open(src) as raw:
        im=raw.convert("RGB")
    d=ImageDraw.Draw(im,"RGBA")
    d.rectangle((0,im.height-76,im.width,im.height),fill=(13,17,22,205))
    f1=font(25);f2=font(20)
    d.text((28,im.height-66),top,font=f1,fill=(255,255,255,255))
    d.text((28,im.height-34),bottom.upper().replace("_"," "),font=f2,fill=(224,229,234,255))
    im.save(dst,quality=95)

def copy_sequence(stills,sequence,actors):
    sequence.mkdir(parents=True,exist_ok=True);n=1
    for key,label,kind in ACTOR_SPECS:
        for expr in EXPRESSIONS:
            src=stills/(key+"_"+expr+".png")
            for _ in range(HOLD):
                shutil.copy2(src,sequence/("frame_%06d.png"%n));n+=1
    return n-1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="render/expressions")
    ap.add_argument("--smoke",action="store_true")
    args=ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,cam=studio()
    scene.frame_start=1;scene.frame_end=240
    actors=build_actors(scene)
    names=list(actors)
    schedules=enable_blinking(scene,list(actors.values()),seed=20261127)
    for key,label,kind in ACTOR_SPECS:
        rows=schedules["Reel "+label]
        if len(rows)<2:raise RuntimeError((label,"less than two blinks in 10 seconds",rows))
        for row in rows:
            if not .12<=row["closed_seconds"]<=.15:raise RuntimeError(("blink duration",label,row))
        gaps=[]
        for left,right in zip(rows,rows[1:]):
            gap=right["start_seconds"]-left["end_seconds"]
            if not 2.0<=gap<=5.0:raise RuntimeError(("blink interval",label,gap))
            gaps.append(gap)
        if any(abs(gaps[i]-gaps[i-1])<.45 for i in range(1,len(gaps))):
            raise RuntimeError(("near-metronomic blink intervals",label,gaps))
    if args.smoke:
        for actor in actors.values():visible(actor,False)
        visible(actors["lead"],True)
        scene.frame_set(35);actors["lead"].pose("surprised")
        render(scene,out/"smoke.png")
        (out/"smoke.json").write_text(json.dumps({"pass":True,"denoising":scene.cycles.use_denoising,
            "characters":names,"expressions":list(EXPRESSIONS),"required":sorted(REQUIRED),
            "blink_schedules":schedules},indent=2)+"\n")
        print("FACIAL_EXPRESSION_SMOKE_PASS",flush=True)
        return

    stills=out/"stills";stills.mkdir(exist_ok=True)
    labelled=out/"labelled";labelled.mkdir(exist_ok=True)
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.cycles.samples=24
    disable_blinking(scene,list(actors.values()))
    for key,label,kind in ACTOR_SPECS:
        for other in actors.values():visible(other,False)
        actor=actors[key];visible(actor,True)
        actor.root.location=(0,0,0);actor.root.rotation_euler=(0,0,0)
        set_camera(cam,scene,"close")
        for expr in EXPRESSIONS:
            scene.frame_set(1);actor.pose(expr);bpy.context.view_layer.update()
            src=stills/(key+"_"+expr+".png")
            render(scene,src)
            label_still(src,labelled/src.name,label,expr)
    expression_frames=out/"expression_frames"
    expression_count=copy_sequence(labelled,expression_frames,actors)

    # Ten-second, seven-character neutral close-up grid. Every actor has an
    # independent irregular blink schedule; only head groups are shown so
    # eyelid movement stays legible at reel scale.
    scene.frame_start=1;scene.frame_end=10*FPS
    scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.cycles.samples=24
    set_camera(cam,scene,"grid")
    positions={
        "lead":(-3.0,.70),"friend":(-1.0,.70),"teacher":(1.0,.70),"dad":(3.0,.70),
        "librarian":(-2.0,-.70),"patron_green":(0.0,-.70),"patron_blue":(2.0,-.70)}
    for key,actor in actors.items():
        actor.root.location=(positions[key][0],0,positions[key][1])
        actor.root.rotation_euler=(0,0,0);actor.pose("neutral");head_only(actor)
    neutral_blink_schedules=enable_blinking(scene,list(actors.values()),seed=20261127)
    blink_dir=out/"blink_frames";blink_dir.mkdir(exist_ok=True)
    blink_labels=[("Lead",274,540),("Friend",731,540),("Teacher",1189,540),("Dad",1646,540),
                  ("Librarian",503,855),("Student Green",960,855),("Student Blue",1417,855)]
    for f in range(1,10*FPS+1):
        scene.frame_set(f);bpy.context.view_layer.update()
        path=blink_dir/("frame_%06d.png"%f);render(scene,path)
        with Image.open(path) as raw:im=raw.convert("RGB")
        draw=ImageDraw.Draw(im,"RGBA")
        for label,x,y in blink_labels:
            box=(x-104,y-5,x+104,y+38);draw.rounded_rectangle(box,radius=10,fill=(12,16,20,190))
            bb=draw.textbbox((0,0),label,font=font(22));draw.text((x-(bb[2]-bb[0])/2,y),label,font=font(22),fill=(255,255,255,255))
        im.save(path,quality=95)

    # Two paired expression/body performances. The acting helper drives head,
    # torso and arms together with the face; no major decal-only change.
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.cycles.samples=24
    beat_dir=out/"beat_frames";beat_dir.mkdir(exist_ok=True)
    start=10*FPS+1;first_len=4*FPS;second_len=round(2.5*FPS)
    scene.frame_start=start;scene.frame_end=start+first_len+second_len-1
    emotion_blink_schedules=enable_blinking(scene,list(actors.values()),seed=20261128)
    lead=actors["lead"];friend=actors["friend"]
    for other in actors.values():visible(other,False)
    visible(lead,True);lead.root.location=(0,0,0);lead.root.rotation_euler=(0,0,0)
    set_camera(cam,scene,"emotion")
    for f in range(start,start+first_len):
        scene.frame_set(f);t=(f-start)/FPS
        if t<.65:
            motion_pose(lead,"idle",t,(0,0,0),0);lead.pose("neutral")
            phase={"beat":"neutral","expression":"neutral","reaction":"none"}
        elif t<1.85:
            phase=act(lead,"surprise",(t-.65)/1.20,(0,0,0),0)
            phase["reaction"]="head_recoil_torso_lean"
        else:
            phase=sustained_laugh(lead,t-1.85,(0,0,0),0)
            phase["reaction"]="head_tilt_torso_rock_shoulder_bounce"
        bpy.context.view_layer.update()
        render(scene,beat_dir/("frame_%06d.png"%(f-start+1)))
    for other in actors.values():visible(other,False)
    visible(friend,True);friend.root.location=(0,0,0);friend.root.rotation_euler=(0,0,0)
    for f in range(start+first_len,start+first_len+second_len):
        scene.frame_set(f);t=(f-(start+first_len))/FPS
        if t<.5:
            motion_pose(friend,"idle",t,(0,0,0),0);friend.pose("neutral")
            phase={"beat":"neutral","expression":"neutral","reaction":"none"}
        else:
            phase=act(friend,"embarrassed",(t-.5)/2.0,(0,0,0),0)
            phase["reaction"]="head_down_torso_fold_arms_in"
        bpy.context.view_layer.update()
        render(scene,beat_dir/("frame_%06d.png"%(first_len+f-(start+first_len)+1)))
    manifest={
        "title":"Chapter 2 — Facial Expressions",
        "resolution":[1280,720],"fps":FPS,"denoising":False,"cycles_samples":24,
        "characters":[{"key":k,"label":label,"kind":kind,"expressions":list(EXPRESSIONS)} for k,label,kind in ACTOR_SPECS],
        "required_expression_set":sorted(REQUIRED),
        "expression_stills":len(list(stills.glob("*.png"))),
        "expression_sequence_frames":expression_count,"expression_hold_frames":HOLD,
        "neutral_blink_frames":10*FPS,"neutral_blink_seconds":10,
        "neutral_blink_schedules":neutral_blink_schedules,
        "emotion_blink_schedules":emotion_blink_schedules,
        "paired_beats":[{"name":"neutral_to_surprise_to_laugh","character":"lead","frames":first_len},
                        {"name":"neutral_to_embarrassed","character":"friend","frames":second_len}],
        "blink_contract":{"interval_seconds":[2.0,5.0],"closed_seconds":[.12,.15],
                          "irregular_per_actor":True,"minimum_consecutive_interval_difference_seconds":.45,"expression_override":"sleep_closed"},
    }
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("FACIAL_EXPRESSION_REEL_RENDERED",json.dumps({k:v for k,v in manifest.items() if k!="blink_schedules"}),flush=True)

if __name__=="__main__":main()
