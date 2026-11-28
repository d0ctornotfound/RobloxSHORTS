"""First-frame-only smoke and cast/group review on the pinned Itlay scene."""
import argparse,json,math,sys,time,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ.setdefault("R6_KNEE_BLEND","1")
import bpy
from mathutils import Vector
from PIL import Image
import numpy as np
from render_demo import point_at,area_light,cube,material
from library_camera import create,project
from library_atmosphere import Atmosphere
from r6_character import mesh_points,bounds
from character_motion_correction import apply_corrected,rear_hip
from chapter1_articulation import Articulation
from chapter1_round2 import neutral_feet,seat_setup,pose as sit_pose
from clothing_articulation import ArticulatedClothes
from saying_hi_cast import build_cast_actor
from saying_hi_square import build_square
ROOT=Path(__file__).resolve().parents[1]

def load():
    c=json.loads((ROOT/"stories/saying_hi_cast.json").read_text());s=json.loads((ROOT/"stories/saying_hi_staging.json").read_text())
    return c,s

def setup(width,height):
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine="BLENDER_EEVEE";scene.eevee.taa_render_samples=32
    scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100
    scene.render.fps=30;scene.render.image_settings.file_format="PNG";scene.render.image_settings.color_mode="RGB"
    scene.world.use_nodes=True;scene.view_settings.view_transform="AgX";scene.render.film_transparent=False
    return scene

def frame(scene,camera,location,target,lens=35,ortho=None):
    camera.location=location;point_at(camera,Vector(target));camera.data.lens=lens
    if ortho:camera.data.type="ORTHO";camera.data.ortho_scale=ortho
    else:camera.data.type="PERSP"
    camera.data.clip_end=3500;bpy.context.view_layer.update()

def actor_points(a):
    return [v for ob in a.meshes+a.accessories if ob.type=="MESH" and not ob.hide_render for v in mesh_points(ob)]

def seat_actor(a,mark):
    # The locked sit adapter establishes the actual hip height and planted soles.
    # Articulate legs only to retain story-specific long sleeve cutoffs.
    yaw=math.radians(mark["yaw_deg"]);art=Articulation(a,legs=True,arms=False)
    clothes=ArticulatedClothes(a,art);feet=neutral_feet(a,art,yaw);seat=seat_setup(a,art,yaw,feet)
    sit_pose(a,art,"sit",1,1.97,yaw,feet,None,seat);art.shift(Vector(mark["xyz"]));clothes.sync()
    return art,clothes,{"hip_z":float(rear_hip(a)[0]),"foot_plane_gaps":[float(v.z) for v in art.soles()]}

def render(scene,out,name):
    path=out/(name+".png");scene.render.filepath=str(path)
    start=time.monotonic();print("SAYING_HI_SMOKE_START",name,flush=True);bpy.ops.render.render(write_still=True)
    pixels=np.asarray(Image.open(path).convert("RGB"))
    result={"file":path.name,"render_seconds":time.monotonic()-start,"resolution":[scene.render.resolution_x,scene.render.resolution_y],"near_black_percent":100*float(np.mean(np.max(pixels,axis=2)<=24))}
    print("SAYING_HI_SMOKE_DONE",json.dumps(result),flush=True);return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--kind",choices=["lineup","square"],required=True);p.add_argument("--map");p.add_argument("--output",required=True)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    c,s=load();scene=setup(2200,1200) if args.kind=="lineup" else setup(1440,1080)
    camera=create(scene);manifest={"kind":args.kind,"engine":"EEVEE","denoising":False,"eevee_spatial_samples":32,"temporal_samples":1,"status":"candidate smoke","cast":{}}
    if args.kind=="square":
        _,provenance=build_square(s,args.map);manifest["scenery"]=provenance
        Atmosphere(scene,target=(0,4,1)).apply("midday");area_light("Group bounce",(0,-4,8),850,10,(1,.9,.8))
        for cid,record in c["actors"].items():
            a=build_cast_actor(cid,record);mark=s["marks"][("wall_" if cid in s["layouts"]["initial"]["wall"] else "well_")+cid]
            art,clothes,metrics=seat_actor(a,mark);a.pose("happy" if cid in s["layouts"]["initial"]["well"] else "neutral")
            manifest["cast"][cid]={"scale":record["scale"],"mark":mark,"contact":metrics,"bounds":list(project(scene,camera,actor_points(a))) if False else None}
        frame(scene,camera,(13.5,-15.5,11.8),(0,4,1.05),35)
        manifest["image"]=render(scene,out,"square_group_smoke")
    else:
        floor=material("neutral studio floor",(.19,.21,.23));cube("studio support",(0,0,-.08),(22,11,.16),floor,bevel=.01)
        scene.world.color=(.45,.45,.45);area_light("Key",(0,-6,8),1800,12,(1,.92,.82));area_light("Fill",(-7,-3,5),1200,10,(.85,.94,1));area_light("Rim",(6,3,6),1100,9,(1,.85,.70))
        # One shot per sex for readable comparison. Combine two true rendered rows in a single PNG.
        rows=[]
        for label,ids in (("girls",c["girls"]),("boys",c["boys"])):
            actors=[];before=set(bpy.data.objects)
            for i,cid in enumerate(ids):
                a=build_cast_actor(cid,c["actors"][cid]);apply_corrected(a,"idle",.5,.5,((i-4.5)*1.30,0,0),0);a.pose("neutral");actors.append(a)
                lo,hi=bounds(actor_points(a));manifest["cast"][cid]={"height_with_hair":hi.z-lo.z,"scale":c["actors"][cid]["scale"]}
            frame(scene,camera,(0,-15,2.0),(0,0,1.28),50,ortho=14.2)
            scene.render.resolution_x=2200;scene.render.resolution_y=620
            rows.append(render(scene,out,"lineup_"+label))
            for ob in set(bpy.data.objects)-before:
                ob.hide_render=True
        from PIL import ImageDraw,ImageFont
        board=Image.new("RGB",(2200,1370),"#20262a");draw=ImageDraw.Draw(board);font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",26)
        for j,(label,ids) in enumerate((("girls",c["girls"]),("boys",c["boys"]))):
            y=j*685;board.paste(Image.open(out/("lineup_"+label+".png")).convert("RGB"),(0,y))
            for i,cid in enumerate(ids):draw.text((110+i*219,y+641),cid.title(),font=font,fill="white",anchor="mm")
        board.save(out/"cast_lineup.png");manifest["images"]=rows;manifest["board"]="cast_lineup.png"
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
if __name__=="__main__":main()
