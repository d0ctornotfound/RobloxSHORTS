"""Attributed MCRD Blender catalogue and dressed office review."""
import argparse,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_library_showcase import fresh,studio,render
from library_character import character
from library_animation import pose
from render_demo import cube,empty,material,point_at
from stage_a_cafe import light
from quality_cafe import text
from library_camera import create,apply,metrics

def import_asset(path,name,pos=(0,0,0),scale=.456,yaw=0):
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path))
    objs=set(bpy.data.objects)-before;assert objs
    root=empty(name,pos)
    for obj in objs:
        if obj.parent is None:obj.parent=root
    root.scale=(scale,)*3;root.rotation_euler.z=yaw;bpy.context.view_layer.update()
    return root

def main():
    p=argparse.ArgumentParser();p.add_argument("--assets",required=True,type=Path);p.add_argument("--output",required=True,type=Path);a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);a.output.mkdir(parents=True,exist_ok=True)
    files=sorted(a.assets.glob("*/*.glb"));assert len(files)==10
    scene=fresh(1920,1440,32);cam=studio(scene,28)
    for i,path in enumerate(files):
        x=(i%5-2)*5.4;y=(i//5)*6-3
        # Catalogue only: normalize to show all objects; dressed scene preserves common scale.
        root=import_asset(path,path.stem,(x,y,0),1)
        mesh=[o for o in root.children_recursive if o.type=="MESH"]
        verts=[o.matrix_world@Vector(v) for o in mesh for v in o.bound_box]
        span=max(max(v[k] for v in verts)-min(v[k] for v in verts) for k in range(3));root.scale=(3.8/span,)*3
        text(path.stem,path.stem.replace("_"," ").upper(),(x,y-2,.12),.26,material("Label "+path.stem,(.80,.85,.90)))
    cam.location=(0,-22,19);point_at(cam,(0,0,1));render(scene,a.output,"catalogue")
    scene=fresh(1080,1920,48)
    wall=material("Office warm plaster",(.56,.48,.38));floor=material("Office floor",(.28,.31,.32))
    cube("Floor",(0,0,-.12),(10,8,.24),floor);cube("Back wall",(0,3.8,2.4),(10,.18,4.8),wall)
    import_asset(a.assets/"furniture/office_desk.glb","Harvest desk",(-.45,1.0,0),.456)
    import_asset(a.assets/"furniture/garage_shelf.glb","Harvest shelf",(3.5,1.3,0),.456,yaw=math.pi/2)
    import_asset(a.assets/"architecture/metal_door.glb","Harvest door",(-3.0,3.65,0),.456)
    import_asset(a.assets/"architecture/window_frame_a.glb","Harvest window",(1.7,3.65,1.35),.456)
    lead=character("Office lead","lead");friend=character("Office friend","friend")
    pose(lead,"idle",.5,(-.72,-1.15,0),.18);pose(friend,"idle",.5,(.65,-.9,0),-.18);lead.pose("happy");friend.pose("happy")
    light("Warm key",(-3,-5,6),(0,0,1.2),1200,5,(1,.86,.70));light("Fill",(4,-3,4),(0,0,1.2),850,5,(.82,.91,1))
    scene.render.resolution_x=1200;scene.render.resolution_y=900
    cam=create(scene);apply(cam,"static",0,(.1,-9.5,4.7),(0,1.1,1.85),35);render(scene,a.output,"dressed_office")
    for im in bpy.data.images:
        if im.source in ("GENERATED","FILE") and not im.packed_file:im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/"dressed_office.blend"))
if __name__=="__main__":main()
