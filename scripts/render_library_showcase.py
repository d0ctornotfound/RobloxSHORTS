"""Render actual library evidence; isolated from both proof stories."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from render_stills import configure
from render_demo import cube,empty,material,point_at
from stage_a_cafe import light
from quality_cafe import text
from render_r6_stills import camera,actor_bounds,smoke
from r6_character import SOURCE_SHA256,mesh_points,bounds,group_points
from r6_imported_cycles import Retarget
from library_character import character
from library_animation import ACTIONS,pose,aim_at,grip,dual_grip
from library_props import NAMES,build,palette
import library_sets
from library_atmosphere import Atmosphere
from library_effects import particles,update,shake

JOBS=("dusk_review","characters","poses0","poses1","poses2","props0","props1","props2","rooms","sky0","sky1","effects","clip0","clip1","clip2","clip3","clip4","clip5","import_walk","import_run")
def fresh(w=540,h=960,samples=24):
    scene=configure("preview");scene.render.resolution_x=w;scene.render.resolution_y=h
    scene.cycles.samples=samples;scene.cycles.adaptive_threshold=.10
    scene.view_settings.view_transform="AgX";scene.view_settings.look="AgX - Medium High Contrast";scene.view_settings.exposure=.12
    bg=scene.world.node_tree.nodes.get("Background");bg.inputs[0].default_value=(.47,.52,.62,1);bg.inputs[1].default_value=.45
    return scene
def studio(scene,width):
    gray=material("Studio blue grey",(.18,.24,.31))
    cube("Seamless studio floor",(0,0,-.12),(200,200,.24),gray,bevel=0)
    cube("Studio back",(0,5,3),(200,.12,12),gray,bevel=0)
    light("Large soft key",(-3,-6,7),(0,0,1.2),1800,9,(1,.94,.86))
    light("Fill",(4,-4,5),(0,0,1.2),1250,8,(.83,.93,1))
    light("Rim",(0,4,6),(0,0,1.2),1600,8,(1,.97,.9))
    return camera(scene,(0,-14,4.2),(0,0,1.3),width,True)
def render(scene,out,name):
    scene.render.filepath=str(out/(name+".png"));bpy.ops.render.render(write_still=True)
def save(out,name,rec):
    (out/(name+".json")).write_text(json.dumps(rec,indent=2)+"\n")
def visible(scene,cam,actor):
    b=actor_bounds(scene,cam,actor)
    assert b[0]>=.015 and b[1]<=.985 and b[2]>=.015 and b[3]<=.985,(actor.role,b)
    return b
def fit(scene,cam,actors):
    for _ in range(40):
        bpy.context.view_layer.update()
        bs=[actor_bounds(scene,cam,a) for a in actors]
        if all(b[0]>=.015 and b[1]<=.985 and b[2]>=.015 and b[3]<=.985 for b in bs):return bs
        if cam.data.type=="ORTHO":cam.data.ortho_scale*=1.04
        else:cam.data.lens*=.96
    raise RuntimeError(("cannot fit",bs))
def characters(out):
    scene=fresh(1200,800,32);cam=studio(scene,6.7)
    a=character("new librarian","librarian");b=character("series lead","lead")
    checks=[smoke(a),smoke(b)]
    pose(a,"hold_left",.5,(-1.3,0,0));a.pose("happy")
    prop=build("book",scale=.82);_,error=grip(a,prop,"left")
    pose(b,"wave",.25,(1.3,0,0));b.pose("smug")
    bs=fit(scene,cam,[a,b]);render(scene,out,"characters")
    save(out,"characters",{"source":SOURCE_SHA256,"roles":[a.role,b.role],"checks":checks,"bounds":bs,"grip_error":error,"garment":a.variant_garment})
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"characters.blend"))
def pose_strip(out,part):
    scene=fresh(1920,620,24);cam=studio(scene,24.3);p=palette();actors=[];rows=[]
    for k,name in enumerate(ACTIONS[part*6:part*6+6]):
        x=(k-2.5)*3.9;label=name.replace("_"," ").upper()
        a=character(name+" A","friend");actors.append(a)
        pos=(x,0,0);phase={"walk":.25,"run":.25,"stand_up":.48,"throw":.78,"wave":.20,"fall":.85}.get(name,.5)
        if name in ("sit","stand_up"):build("chair",pos=(x,.19,0),p=p)
        if name=="sleep":build("bed",pos=(x,0,0),p=p);pos=(x,0,.74)
        if name in ("hug","high_five"):pos=(x-.76,0,0)
        pa=pose(a,name,phase,pos,yaw=math.pi/2 if name=="hug" else 0);a.pose("laughing" if name in ("high_five","hug","wave") else "shocked" if name=="fall" else "happy")
        err=None;partner=None
        if name=="hug":
            b=character(name+" B","lead");actors.append(b);pose(b,name,phase,(x+.76,0,0),yaw=-math.pi/2);b.pose("happy");partner="lead"
        if name=="high_five":
            b=character(name+" B","lead");actors.append(b);pose(b,name,phase,(x+.76,0,0));b.pose("happy");partner="lead"
            ia=max(range(2),key=lambda i:(a.armature.matrix_world@a.arms[i].head).x)
            ib=min(range(2),key=lambda i:(b.armature.matrix_world@b.arms[i].head).x)
            ja=a.armature.matrix_world@a.arms[ia].head;jb=b.armature.matrix_world@b.arms[ib].head
            L=(a.grips[ia].matrix_world.translation-ja).length;mid=(ja+jb)/2
            delta=(ja-jb).length/2;assert delta<L
            target=mid+Vector((0,0,math.sqrt(L*L-delta*delta)))
            err=max(aim_at(a,ia,target),aim_at(b,ib,target));assert err<.002,err
        if name in ("eat","drink","hold_left","hold_right","throw"):
            kind={"eat":"food","drink":"cup","hold_left":"book","hold_right":"phone","throw":"ball"}[name]
            pr=build(kind,scale=.8,p=p);_,err=grip(a,pr,"left" if name=="hold_left" else "right")
        if name=="hold_both":
            pr=empty("Two handed tray",(0,0,0));_,half,err=dual_grip(a,pr)
            cube("Tray",(0,0,.045),(half*2+.06,.28,.08),p["wood"],pr)
        text("Action label",label,(x,-2.15,.22),.26,p["cream"])
        rows.append({"action":name,"phase":phase,"parameters":pa,"grip_or_contact_error":err,"partner":partner})
    bs=fit(scene,cam,actors);render(scene,out,"poses"+str(part))
    save(out,"poses"+str(part),{"actions":rows,"actor_bounds":bs})
def catalogue(out,part):
    scene=fresh(1920,660,24);cam=studio(scene,23.5);p=palette();rows=[]
    for k,kind in enumerate(NAMES[part*7:part*7+7]):
        x=(k-3)*3.05;pr=build(kind,p=p)
        bpy.context.view_layer.update()
        lo,hi=bounds(v for ob in pr.children_recursive if ob.type=="MESH" for v in mesh_points(ob))
        dims=hi-lo;assert min(dims)>.001
        sc=2.30/max(dims.x,dims.y,dims.z)
        pr.scale=(sc,)*3;pr.location=(x-sc*(lo.x+hi.x)/2,-sc*(lo.y+hi.y)/2,-sc*lo.z)
        pr.rotation_euler.z=.28;bpy.context.view_layer.update()
        text("Prop label",kind.replace("_"," ").upper(),(x,-2.0,.18),.23,p["cream"])
        rows.append({"kind":kind,"native_dimensions":list(dims),"display_scale":sc,"mesh_count":sum(o.type=="MESH" for o in pr.children_recursive)})
    render(scene,out,"props"+str(part));save(out,"props"+str(part),{"props":rows})
def rooms(out):
    for name in ("cafe","classroom"):
        scene=fresh(840,640,24);getattr(library_sets,name)()
        light("Room soft key",(0,-3,3.8),(0,1,1.2),650,4,(1,.91,.81))
        light("Room fill",(2,-1,3),(0,2,1.3),280,4,(.82,.91,1))
        camera(scene,(0,-3.60,2.6),(0,2.0,1.6),27)
        render(scene,out,"room_"+name);save(out,"room_"+name,{"kit":name,"mesh_count":sum(o.type=="MESH" for o in scene.objects)})
def street_scene(samples=24,w=540,h=960):
    scene=fresh(w,h,samples);st=library_sets.street()
    atm=Atmosphere(scene,st["windows"],lamps=st["lamps"])
    cam=camera(scene,(0,-5.0,2.80),(0,.8,2.25),37)
    actor=character("Street lead","lead");actor.pose("smug")
    pose(actor,"idle",.5,(0,0,0),yaw=.18)
    return scene,atm,cam,actor
def skies(out,part):
    names=("morning","midday","golden_hour","dusk") if part==0 else ("night","overcast","rain")
    scene,atm,cam,a=street_scene()
    for name in names:
        rec=atm.apply(name);bpy.context.view_layer.update()
        rec["actor_bounds"]=visible(scene,cam,a)
        render(scene,out,"sky_"+name);save(out,"sky_"+name,rec)
    if part==1:bpy.ops.wm.save_as_mainfile(filepath=str(out/"street.blend"))
def dusk_review(out):
    scene,atm,cam,a=street_scene(64)
    for name in ("dusk","night"):
        rec=atm.apply(name);bpy.context.view_layer.update()
        rec["actor_bounds"]=visible(scene,cam,a)
        assert rec["lamp_energy"]==85
        assert rec["camera_gradient_weight"]==(1 if name=="dusk" else 0)
        render(scene,out,"sky_"+name);save(out,"sky_"+name,rec)

def effects(out):
    scene,atm,cam,a=street_scene(20);atm.apply("rain")
    base=cam.location.copy();rows=[]
    for kind in ("rain","snow","sparkles","confetti","dust"):
        e=particles(kind,center=(0,-.65,1.9),extent=(6,3.2,4.7),count=125 if kind=="rain" else 95)
        update(e,.65);bpy.context.view_layer.update()
        render(scene,out,"fx_"+kind)
        rows.append({"kind":kind,"count":len(e["items"]),"time":.65})
        for ob,_ in e["items"]:bpy.data.objects.remove(ob,do_unlink=True)
        bpy.data.objects.remove(e["root"],do_unlink=True)
    displacement=shake(cam,base,.73,.16,12);assert displacement>.01
    render(scene,out,"fx_shake");save(out,"effects",{"effects":rows,"shake_displacement":displacement})
def clip(out,part):
    from render_imported_cycles import grounded
    scene,atm,cam,a=street_scene(16,360,640);fps=12;scene.render.fps=fps
    scene.frame_start=1;scene.frame_end=144
    ret=Retarget(a);cal=ret.calibrate("walk_cycle")
    c=ret.clips["walk_cycle"];duration=12;distance=20
    speed=distance/((144-1)/fps);rate=speed/cal["speed_scene_units_per_second"]
    first=part*24+1;last=first+23;records=[]
    star=[o for o in a.accessories if "signature red star" in o.name]
    assert len(star)==1 and not any("signature red pin" in o.name for o in a.accessories)
    # Pin must remain within the torso's evaluated vertical range on every frame.
    for f in range(first,last+1):
        t=(f-1)/fps;x=-distance/2+speed*t;scene.frame_set(f)
        ret.at("walk_cycle",t*rate)
        low,adjust=grounded(a,(x,0,0),math.pi/2);a.pose("smug")
        cam.location=(x+.85,-3.75,2.24);cam.data.lens=43
        point_at(cam,(x+.12,.25,1.78))
        # Move the fill with the camera, preserving the preset's color/energy.
        atm.fill.location=(x,-5,5);point_at(atm.fill,(x,0,1.2))
        if t<3:rec=atm.apply("midday")
        elif t<6:rec=atm.apply("midday","golden_hour",(t-3)/3)
        elif t<9:rec=atm.apply("golden_hour","night",(t-6)/3)
        else:rec=atm.apply("night")
        # Keep blue night legible with a motivated cool bounce, not a pixel clamp.
        night=rec["night"]
        atm.fill.data.energy+=190*night
        bpy.context.view_layer.update()
        torso=group_points(a.body,a.bones["torso"].name);lo,hi=bounds(torso)
        center=sum(mesh_points(star[0]),Vector())/len(mesh_points(star[0]))
        assert lo.z-.035<=center.z<=hi.z+.035,("star detached from chest",f,list(center),list(lo),list(hi))
        rec.update({"frame":f,"x":x,"source_seconds":t*rate%c["duration"],"foot_min_z":low,
                    "star_height":center.z,"torso_z_bounds":[lo.z,hi.z]})
        rec["actor_bounds"]=visible(scene,cam,a)
        assert abs(low)<.001
        records.append(rec);render(scene,out,f"frame_{f:04d}")
    save(out,"clip"+str(part),{"fps":fps,"resolution":[360,640],"samples":16,
         "action":"walk_cycle","source_sha256":ret.data["source_sha256"],"speed":speed,"playback_rate":rate,
         "calibration":cal,"frames":records})
def main():
    p=argparse.ArgumentParser();p.add_argument("--job",choices=JOBS,required=True);p.add_argument("--output",default="render/showcase")
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    j=a.job
    if j=="dusk_review":dusk_review(out)
    elif j=="characters":characters(out)
    elif j.startswith("poses"):pose_strip(out,int(j[-1]))
    elif j.startswith("props"):catalogue(out,int(j[-1]))
    elif j=="rooms":rooms(out)
    elif j.startswith("sky"):skies(out,int(j[-1]))
    elif j=="effects":effects(out)
    elif j.startswith("clip"):clip(out,int(j[-1]))
    elif j.startswith("import_"):
        from render_imported_cycles import strip
        strip(out,"walk_cycle" if j=="import_walk" else "run_cycle")
if __name__=="__main__":main()
