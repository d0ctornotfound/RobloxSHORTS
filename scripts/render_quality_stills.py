"""Three hero stills, independent of the historic animation paths."""
import argparse,json,sys,math,subprocess,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import point_at
from render_stills import configure
from stage_a_cafe import set_visible
from stage_b_interaction import aim_arm
from quality_character import Character,palette
from quality_cafe import build


def arguments():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--shot",choices=("all","01_portrait","02_cup_reaction","03_cafe_wide"),default="all")
    p.add_argument("--output",default="render/quality")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])


def main():
    a=arguments();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    scene=configure(a.profile)
    scene.render.resolution_x,scene.render.resolution_y=(720,1280) if a.profile=="preview" else (1080,1920)
    scene.cycles.samples=128 if a.profile=="preview" else 192
    # Ubuntu Blender 4.0.2 is built without any Cycles denoiser backend.
    # Render clean high-sample input, then use a real spatial denoiser.
    scene.cycles.use_denoising=False
    denoiser="FFmpeg nlmeans (s=3.5:p=7:r=15)"
    scene.cycles.adaptive_threshold=.008
    scene.cycles.max_bounces=7
    scene.cycles.diffuse_bounces=4
    scene.cycles.transparent_max_bounces=10
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.05
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.42,.31,.21,1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.20
    # Mild grade, no glow filter to muddy the faces.
    scene.use_nodes=True
    ns,ls=scene.node_tree.nodes,scene.node_tree.links
    ns.clear()
    src=ns.new("CompositorNodeRLayers")
    grade=ns.new("CompositorNodeHueSat")
    grade.inputs["Saturation"].default_value=1.10
    ls.new(src.outputs["Image"],grade.inputs["Image"])
    outnode=ns.new("CompositorNodeComposite");ls.new(grade.outputs["Image"],outnode.inputs["Image"])
    table_cup,held=build()
    p=palette();lead=Character("Series lead",p,True);friend=Character("Cafe friend",p,False)
    for expr in ("neutral","happy","shocked","sad"):
        lead.expression(expr)
        assert lead.face.data.materials[0]==p["faces"][expr]
        assert p["faces"][expr].node_tree.nodes.get("Image Texture").image.size[:]==(1024,1024)
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
    camera.data.type="PERSP"
    camera.data.sensor_fit="HORIZONTAL"
    records=[]
    def fit(position,target,lens,objects,margin=.035):
        camera.location=position;camera.data.lens=lens;point_at(camera,target)
        for _ in range(45):
            bpy.context.view_layer.update()
            vs=[world_to_camera_view(scene,camera,o.matrix_world@Vector(c)) for o in objects for c in o.bound_box]
            if all(margin<=v.x<=1-margin and margin<=v.y<=1-margin and v.z>0 for v in vs):break
            camera.data.lens*=.97
        else:raise RuntimeError("Could not fit subjects")
        return [min(v.x for v in vs),max(v.x for v in vs),min(v.y for v in vs),max(v.y for v in vs)]
    def render(name,position,target,lens,subjects,dof=False,focus=None,fstop=3.2):
        if a.shot not in ("all",name):return
        bounds=fit(position,target,lens,subjects)
        camera.data.dof.use_dof=dof
        if dof:
            camera.data.dof.focus_distance=(camera.location-Vector(focus)).length
            camera.data.dof.aperture_fstop=fstop
            camera.data.dof.aperture_blades=7
        print("QUALITY_RENDER_BEGIN",name,denoiser,scene.cycles.samples,flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/"raw.png"
            scene.render.filepath=str(raw)
            bpy.ops.render.render(write_still=True)
            subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(raw),
                "-vf","nlmeans=s=3.5:p=7:r=15","-frames:v","1","-threads","1",str(out/(name+".png"))],check=True)
        print("QUALITY_DENOISE_COMPLETE",name,denoiser,flush=True)
        records.append({"file":name+".png","bounds":bounds,"lens":camera.data.lens,"dof":dof})
        print("QUALITY_RENDERED",name,bounds,flush=True)
    def heads(actor):
        return [o for o in actor.meshes if any(k in o.name for k in ("head","hair","beanie","decal"))]
    def upper(actor):
        return [o for o in actor.meshes if not any(k in o.name for k in ("denim leg","sneaker","sole"))]
    lead.root.location=(0,-.55,.025)
    lead.root.rotation_euler.z=-.10
    lead.pose("happy",((-.06,.08,0),(-.10,-.08,0)))
    friend.visible(False);set_visible(held,False)
    render("01_portrait",(.12,-3.05,2.14),(0,-.55,1.92),74,heads(lead),True,(0,-.90,2.02),1.5)
    # Side-by-side, with modest depth stagger; frame both upper bodies and cup.
    lead.root.location=(-.68,-.20,.025);lead.root.rotation_euler.z=-.10
    friend.root.location=(.78,.62,.025);friend.root.rotation_euler.z=.14
    friend.visible(True)
    lead.expression("shocked");friend.expression("happy")
    aim_arm(lead,0,(0,-.10,-.65));aim_arm(lead,1,(-.10,-.54,.23))
    lead.attach_cup(held,1);set_visible(held,True)
    aim_arm(friend,0,(-.18,-.18,-.60));aim_arm(friend,1,(-.10,-.13,-.63))
    table_cup.location=(.32,.12,1.18)
    # Medium is an intentional waist-up crop, with both heads and the active cup protected.
    torso_friend=[o for o in friend.meshes if "torso" in o.name]
    render("02_cup_reaction",(.15,-3.20,2.05),(.08,.12,2.07),58,heads(lead)+heads(friend)+torso_friend+list(held.children_recursive),True,(.0,.12,1.92),8.0)
    # Establishing shot: reveal three tables, counter, real window, and both actors.
    lead.root.location=(-.94,-.48,.025);lead.root.rotation_euler.z=-.05
    friend.root.location=(.96,.10,.025);friend.root.rotation_euler.z=.10
    lead.expression("happy");friend.expression("neutral")
    aim_arm(lead,0,(0,-.12,-.65));aim_arm(lead,1,(-.10,-.54,.23));lead.attach_cup(held,1)
    render("03_cafe_wide",(0,-5.1,2.48),(0,.4,2.35),43,heads(lead)+heads(friend),False)
    manifest={"resolution":[scene.render.resolution_x,scene.render.resolution_y],"samples":scene.cycles.samples,
       "denoise":denoiser,"face_texture_size":1024,"clothing_texture_size":1024,
       "expressions":["neutral","happy","shocked","sad"],"proportions":Character.PROPORTIONS,
       "tables":3,"shots":records}
    (out/"quality_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("QUALITY_SPRINT_COMPLETE",json.dumps(manifest),flush=True)


if __name__=="__main__":main()
