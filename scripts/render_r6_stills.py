"""Approval-only supplied R6 stills. Never renders a short."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_stills import configure
from render_demo import cube,empty,point_at
from stage_a_cafe import light,set_visible
from quality_cafe import build as cafe
from classroom_set import build as classroom
from stage_c_props import build_plate_and_slice
from r6_character import R6Character,matte,mesh_points,group_points,ASSET,SOURCE_SHA256
from stage_b_interaction import GripAttachment

SHOTS=("00_lineup","01_cafe_two","02_classroom_two")
def smoke(actor):
    rest=[v.copy() for ob in actor.skinned for v in mesh_points(ob)]
    before=group_points(actor.body,actor.arms[1].name)
    grip=actor.grips[1];start=grip.matrix_world.translation.copy()
    actor.aim_arm(1,(.08,-.95,-.15))
    after=group_points(actor.body,actor.arms[1].name)
    delta=max((a-b).length for a,b in zip(before,after))
    socket_delta=(grip.matrix_world.translation-start).length
    assert delta>.15 and socket_delta>.15,(delta,socket_delta)
    prop=empty("Temporary bone grip test",(0,0,0));attach=GripAttachment(prop,grip)
    err=attach.bind(1);assert err<1e-5
    bpy.data.objects.remove(prop,do_unlink=True)
    face_before=actor.face.matrix_world.translation.copy()
    actor.set_bone("head",(.17,.08,.11))
    face_delta=(actor.face.matrix_world.translation-face_before).length
    assert face_delta>.005,face_delta
    actor.reset()
    restored=[v for ob in actor.skinned for v in mesh_points(ob)]
    reset_error=max((a-b).length for a,b in zip(rest,restored))
    assert reset_error<1e-5,reset_error
    return {"bind_reset_error":reset_error,"arm_vertex_displacement":delta,"grip_socket_displacement":socket_delta,"attachment_error":err,"head_decal_displacement":face_delta}

def camera(scene,pos,target,lens,ortho=False):
    bpy.ops.object.camera_add(location=pos);cam=bpy.context.object
    cam.name="Approval camera";cam.data.sensor_fit="HORIZONTAL"
    cam.data.type="ORTHO" if ortho else "PERSP"
    if ortho:cam.data.ortho_scale=lens
    else:cam.data.lens=lens
    point_at(cam,target);scene.camera=cam
    return cam

def actor_bounds(scene,cam,actor,head_only=False):
    objects=[actor.head]+[o for o in actor.accessories if "head " in o.name] if head_only else actor.meshes
    vv=[world_to_camera_view(scene,cam,v) for ob in objects for v in mesh_points(ob)]
    return [min(v.x for v in vv),max(v.x for v in vv),min(v.y for v in vv),max(v.y for v in vv)]

def main():
    p=argparse.ArgumentParser();p.add_argument("--shot",choices=SHOTS,required=True);p.add_argument("--output",default="render/r6")
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene=configure("preview");scene.cycles.samples=96;scene.cycles.adaptive_threshold=.035
    scene.view_settings.view_transform="AgX";scene.view_settings.look="AgX - Medium High Contrast";scene.view_settings.exposure=.25
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.48,.46,.43,1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.35
    if a.shot=="00_lineup":
        scene.render.resolution_x,scene.render.resolution_y=1600,900
        gray=matte("Neutral studio",(.33,.34,.36))
        cube("Neutral studio floor",(0,0,-.08),(35,35,.16),gray,bevel=0)
        cube("Neutral studio backdrop",(0,4,4),(35,.2,9),gray,bevel=0)
        light("Studio key",(-3,-4,5),(0,0,1.25),700,4,(1,.96,.91))
        light("Studio fill",(3,-4,3.2),(0,0,1.25),470,5,(.91,.96,1))
        light("Studio rim",(0,2.8,4.8),(0,0,1.25),320,3,(1,1,1))
        roles=("lead","friend","teacher");positions=((-1.98,0,0),(0,0,0),(1.98,0,0))
        cam=camera(scene,(0,-8,2.0),(0,0,1.28),6.25,True)
    elif a.shot=="01_cafe_two":
        scene.render.resolution_x,scene.render.resolution_y=720,1280
        for drink in cafe():set_visible(drink,False)
        roles=("lead","friend");positions=((-1.00,.85,0),(1.00,.85,0))
        plate,cake=build_plate_and_slice(.29);plate.location=(.04,-.03,1.18);cake.location=(.04,-.03,1.245)
        light("R6 cafe frontal bounce",(0,-3.0,3.4),(0,.85,1.65),340,4.2,(1,.95,.88))
        cam=camera(scene,(0,-3.55,2.22),(0,.85,1.75),56)
    else:
        scene.render.resolution_x,scene.render.resolution_y=720,1280
        classroom()
        roles=("lead","teacher");positions=((-1.0,-5.45,0),(1.0,-5.45,0))
        light("R6 classroom front key",(0,-2.1,3.65),(0,-5.45,1.62),450,4,(1,.94,.86))
        cam=camera(scene,(0,-1.15,2.20),(0,-5.45,1.68),55)
    actors=[R6Character(role,role) for role in roles]
    checks={actor.role:smoke(actor) for actor in actors}
    for i,(actor,pos) in enumerate(zip(actors,positions)):
        actor.root.location=pos
        if a.shot=="02_classroom_two":actor.root.rotation_euler.z=math.pi
        if a.shot=="00_lineup":actor.pose("happy" if actor.role!="teacher" else "unimpressed")
        elif a.shot=="01_cafe_two":
            actor.pose("happy" if i==0 else "shocked")
            actor.aim_arm(1 if i==0 else 0,(.12 if i==0 else -.12,-.84,-.53))
        else:
            actor.pose("shocked" if i==0 else "unimpressed")
            actor.aim_arm(0 if i==0 else 1,(-.1 if i==0 else .1,-.55,-.83))
    bpy.context.view_layer.update()
    for _ in range(30):
        protected=[actor_bounds(scene,cam,x,a.shot!="00_lineup") for x in actors]
        if all(.035<=r[0] and r[1]<=.965 and .035<=r[2] and r[3]<=.965 for r in protected):break
        if cam.data.type=="ORTHO":cam.data.ortho_scale*=1.035
        else:cam.data.lens*=.97
    else:raise RuntimeError(("camera failed",protected))
    if a.shot=="00_lineup":
        assert all(b[3]-b[2]>.60 for b in protected),("not upright",protected)
    rec={"shot":a.shot,"source_sha256":SOURCE_SHA256,"source_size":ASSET.stat().st_size,"samples":scene.cycles.samples,
         "resolution":[scene.render.resolution_x,scene.render.resolution_y],
         "characters":[{"role":x.role,"bones":list(x.armature.pose.bones.keys()),"skinned_mesh_count":len(x.skinned),"measurements":x.measurements,
                        "scale":x.scale,"face_material":x.face.data.materials[0].name,"protected_bounds":r,
                        "whole_body_bounds":actor_bounds(scene,cam,x),"smoke_test":checks[x.role]} for x,r in zip(actors,protected)]}
    for actor in actors:
        for ob in actor.accessories:assert ob.parent==actor.armature and ob.parent_type=="BONE"
    scene.render.filepath=str(out/(a.shot+".png"))
    (out/(a.shot+".json")).write_text(json.dumps(rec,indent=2)+"\n")
    print("R6_APPROVAL_VALIDATED",json.dumps(rec),flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(a.shot+".blend")))
    bpy.ops.render.render(write_still=True)
if __name__=="__main__":main()
