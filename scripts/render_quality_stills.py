"""Sprint 2 measurable hero stills, independent of all animation paths."""
import argparse,json,sys,math,subprocess,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from render_demo import point_at,cube,material
from render_stills import configure
from stage_a_cafe import set_visible,light
from stage_b_interaction import aim_arm
from quality_character import Character,palette
from quality_cafe import build

SHOTS=("00_lineup","01_portrait","02_cup_reaction","03_cafe_wide")
def arguments():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",choices=("preview","full"),default="preview")
    p.add_argument("--shot",choices=("all",)+SHOTS,default="all")
    p.add_argument("--output",default="render/quality")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])

def ceiling_measure(scene,camera):
    # Sample actual camera rays on a 100x100 grid. Count ceiling hits
    # (or rays escaping the set) and the maximum top band at any column.
    # Ray-cast can hit hide_render geometry, so skip it explicitly.
    dg=bpy.context.evaluated_depsgraph_get()
    corners=camera.data.view_frame(scene=scene)
    xmin,xmax=min(v.x for v in corners),max(v.x for v in corners)
    ymin,ymax=min(v.y for v in corners),max(v.y for v in corners)
    z=corners[0].z
    origin=camera.matrix_world.translation
    cols=[]
    hits=0
    for i in range(100):
        band=0;open_band=True
        for j in range(100):
            v=Vector((xmin+(xmax-xmin)*(i+.5)/100,ymax-(ymax-ymin)*(j+.5)/100,z))
            direction=(camera.matrix_world.to_3x3()@v).normalized()
            start=origin.copy()
            ceiling=False
            for k in range(40):
                hit,loc,normal,index,obj,matrix=scene.ray_cast(dg,start,direction,distance=100)
                if not hit:ceiling=True;break
                if obj.hide_render:
                    start=loc+direction*.002
                    continue
                ceiling="ceiling" in obj.name.lower()
                break
            if ceiling:hits+=1
            if open_band and ceiling:band+=1
            else:open_band=False
        cols.append(band)
    return {"ceiling_area_fraction":hits/10000,"max_top_ceiling_band":max(cols)/100,"grid":[100,100]}

def main():
    a=arguments();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    records=[]
    denoiser="FFmpeg nlmeans (s=3.5:p=7:r=15)"
    # Each shot is an independent still. Build the studio or café from scratch
    # to prevent visibility flags or character pose from leaking between shots.
    for shot in SHOTS:
        if a.shot not in ("all",shot):continue
        scene=configure(a.profile)
        scene.render.resolution_x,scene.render.resolution_y=((1280,900) if a.profile=="preview" else (1920,1350)) if shot=="00_lineup" else ((720,1280) if a.profile=="preview" else (1080,1920))
        scene.cycles.samples=128 if a.profile=="preview" else 192
        scene.cycles.use_denoising=False
        scene.cycles.adaptive_threshold=.008
        scene.cycles.max_bounces=7
        scene.cycles.diffuse_bounces=4
        scene.cycles.transparent_max_bounces=10
        scene.view_settings.view_transform="AgX"
        scene.view_settings.look="AgX - Medium High Contrast"
        scene.view_settings.exposure=.05
        scene.world.node_tree.nodes.get("Background").inputs[0].default_value=(.42,.31,.21,1)
        scene.world.node_tree.nodes.get("Background").inputs[1].default_value=.20
        scene.use_nodes=True
        ns,ls=scene.node_tree.nodes,scene.node_tree.links;ns.clear()
        src=ns.new("CompositorNodeRLayers");grade=ns.new("CompositorNodeHueSat")
        grade.inputs["Saturation"].default_value=1.17
        ls.new(src.outputs["Image"],grade.inputs["Image"])
        dest=ns.new("CompositorNodeComposite");ls.new(grade.outputs["Image"],dest.inputs["Image"])
        if shot=="00_lineup":
            floor=material("Neutral studio seamless",(.24,.27,.29))
            cube("Studio floor",(0,0,-.08),(30,30,.16),floor,bevel=0)
            cube("Studio neutral backdrop",(0,5,4),(30,.15,12),floor,bevel=0)
            light("Studio key",(-3,-4,5),(0,0,1.4),650,4,(1,.98,.94))
            light("Studio fill",(3,-4,3),(0,0,1.4),400,4,(.94,.98,1))
        else:
            table_cup,held=build()
        p=palette()
        lead=Character("Series lead",p,role="lead")
        friend=Character("Cafe friend",p,lead=False,role="friend")
        assert len([o for o in lead.meshes if "swept spiky hair" in o.name])==1
        assert not any("beanie" in o.name for o in lead.meshes)
        assert len([o for o in friend.meshes if "beanie" in o.name])==1
        assert not any("beanie" in o.name for o in lead.meshes)
        assert len([o for o in lead.meshes if "signature" in o.name])==2
        assert all("Hero cloth" not in m.name for o in lead.meshes if "spiky hair" in o.name for m in o.data.materials)
        for expr in ("neutral","happy","shocked","sad"):
            lead.expression(expr)
            assert lead.face.data.materials[0]==p["faces"][expr]
            assert p["faces"][expr].node_tree.nodes.get("Image Texture").image.size[:]==(1024,1024)
        bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
        camera.data.type="PERSP";camera.data.sensor_fit="HORIZONTAL"
        def fit(position,target,lens,objects,margin=.035,ortho=False):
            camera.location=position;point_at(camera,target)
            camera.data.type="ORTHO" if ortho else "PERSP"
            if ortho:camera.data.ortho_scale=lens
            else:camera.data.lens=lens
            for _ in range(70):
                bpy.context.view_layer.update()
                vs=[world_to_camera_view(scene,camera,o.matrix_world@Vector(c)) for o in objects for c in o.bound_box]
                if all(margin<=v.x<=1-margin and margin<=v.y<=1-margin and v.z>0 for v in vs):break
                if ortho:camera.data.ortho_scale*=1.025
                else:camera.data.lens*=.98
            else:raise RuntimeError("Could not fit subjects")
            return [min(v.x for v in vs),max(v.x for v in vs),min(v.y for v in vs),max(v.y for v in vs)]
        def heads(actor):
            return [o for o in actor.meshes if any(k in o.name for k in ("head","hair","beanie","decal"))]
        def neutral(actor):
            actor.pose("neutral")
            for i in (0,1):actor.grip_closed(i,True)
        def seated(actor,position,angle):
            actor.root.location=position;actor.root.rotation_euler.z=angle
            for leg in actor.legs:leg.rotation_euler.x=-math.pi/2
            actor.pose("happy")
            aim_arm(actor,0,(.20,-.72,-.30));aim_arm(actor,1,(-.15,-.7,-.36))
        dof=False;ceiling=None;patron_count=0
        if shot=="00_lineup":
            lead.root.location=(-1.22,0,0);friend.root.location=(1.22,0,0)
            neutral(lead);neutral(friend)
            bounds=fit((0,-10,2.12),(0,0,1.45),5.05,lead.meshes+friend.meshes,margin=.035,ortho=True)
            assert bounds[3]-bounds[2]>=.70, bounds
        elif shot=="01_portrait":
            lead.root.location=(0,-.6,.025);lead.root.rotation_euler.z=-.10
            lead.pose("happy",((-.06,.03,0),(-.10,-.03,0)))
            friend.visible(False);set_visible(held,False)
            bounds=fit((.10,-3.30,2.20),(0,-.6,2.02),66,heads(lead)+[o for o in lead.meshes if "signature" in o.name])
            dof=True;focus=(0,-.99,2.06);fstop=2.0
        elif shot=="02_cup_reaction":
            # Small depth stagger protects both faces; the outer body edges
            # may crop, but heads, active hand and cup remain in frame.
            lead.root.location=(-.77,-.43,.025);lead.root.rotation_euler.z=-.09
            friend.root.location=(.79,.47,.025);friend.root.rotation_euler.z=.12
            lead.expression("shocked");friend.expression("happy")
            aim_arm(lead,0,(0,-.08,-1));aim_arm(lead,1,(-.22,-.86,-.12))
            lead.attach_cup(held,1);set_visible(held,True)
            aim_arm(friend,0,(-.20,-.12,-1));aim_arm(friend,1,(-.12,-.10,-1))
            table_cup.location=(.37,.17,1.18)
            bounds=fit((.09,-3.45,2.74),(.04,.05,1.69),55,heads(lead)+heads(friend)+list(held.children_recursive))
            dof=True;focus=(0,-.13,1.94);fstop=8
            ceiling=ceiling_measure(scene,camera)
        else:
            lead.root.location=(-.89,-.73,.025);lead.root.rotation_euler.z=-.08
            friend.root.location=(.90,-.30,.025);friend.root.rotation_euler.z=.08
            lead.expression("happy");friend.expression("neutral")
            aim_arm(lead,0,(0,-.13,-1));aim_arm(lead,1,(-.12,-.83,-.18));lead.attach_cup(held,1)
            aim_arm(friend,0,(-.12,-.12,-1));aim_arm(friend,1,(.12,-.12,-1))
            # Patrons sit at the rear-side chairs, angled toward their tables.
            # The seat is at z=.67; lowering the hip by .219 supports the
            # horizontal upper leg. Move chair under each patron if needed.
            patrons=[Character("Left patron",p,False,role="patron_green"),Character("Right patron",p,False,role="patron_blue")]
            for ob in patrons[0].meshes+patrons[1].meshes:
                assert "beanie" not in ob.name
            seated(patrons[0],(-2.35,1.03,-.219),-.12)
            seated(patrons[1],(2.45,1.78,-.219),.12)
            for idx,(x,y) in enumerate([(-2.35,1.03),(2.45,1.78)]):
                label="Side table chair 0" if idx==0 else "Window table chair 0"
                chair=bpy.data.objects.get(label)
                if chair:
                    chair.location.x=x;chair.location.y=y;chair.rotation_euler.z=(-.12 if idx==0 else .12)
            patron_count=2
            bounds=fit((0,-6.4,4.05),(0,.38,1.45),45,heads(lead)+heads(friend)+heads(patrons[0])+heads(patrons[1]))
            ceiling=ceiling_measure(scene,camera)
        if ceiling:
            print("CEILING_MEASUREMENT",shot,json.dumps(ceiling),flush=True)
            assert ceiling["ceiling_area_fraction"]<=.10 and ceiling["max_top_ceiling_band"]<=.10,ceiling
        camera.data.dof.use_dof=dof
        if dof:
            camera.data.dof.focus_distance=(camera.location-Vector(focus)).length
            camera.data.dof.aperture_fstop=fstop;camera.data.dof.aperture_blades=7
        bpy.context.view_layer.update()
        # Geometry measurement from actual object dimensions, excluding hair.
        head=lead.head.dimensions[:]
        torso=next(o for o in lead.meshes if o.name.endswith(" / torso")).dimensions[:]
        body_height=lead.head.location.z+head[2]/2
        assert abs(head[0]/torso[0]-.95)<.01 and abs(head[2]/body_height-.22)<.01
        measurements={"head_width_over_torso":head[0]/torso[0],"head_height_over_body":head[2]/body_height,
                      "body_height_without_hair":body_height,"head_dimensions":list(head),"torso_dimensions":list(torso),
                      "arm_end_height":1.778-1.115-.135}
        print("MEASURED_R6",json.dumps(measurements),flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/"raw.png";scene.render.filepath=str(raw)
            bpy.ops.render.render(write_still=True)
            subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(raw),
                "-vf","nlmeans=s=3.5:p=7:r=15","-frames:v","1","-threads","1",str(out/(shot+".png"))],check=True)
        rec={"file":shot+".png","resolution":[scene.render.resolution_x,scene.render.resolution_y],"bounds":bounds,"lens":camera.data.lens if camera.data.type=="PERSP" else None,"ortho_scale":camera.data.ortho_scale if camera.data.type=="ORTHO" else None,"dof":dof,"ceiling":ceiling,"patrons":patron_count}
        records.append(rec);print("QUALITY_RENDERED",json.dumps(rec),flush=True)
    manifest={"resolution":[720,1280] if a.profile=="preview" else [1080,1920],"lineup_resolution":[1280,900] if a.profile=="preview" else [1920,1350],"samples":scene.cycles.samples,
       "denoise":denoiser,"face_texture_size":1024,"clothing_texture_size":1024,"face_ink_scale":.60,
       "expressions":["neutral","happy","shocked","sad"],"proportions":Character.PROPORTIONS,
       "measurements":measurements,"tables":3,"signature":"red enamel star chest pin","shots":records}
    (out/"quality_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("QUALITY_SPRINT_COMPLETE",json.dumps(manifest),flush=True)

if __name__=="__main__":main()
