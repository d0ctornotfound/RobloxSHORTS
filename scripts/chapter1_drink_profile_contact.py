"""Visual-first profile contact only; no sequence approval or gate changes."""
import os,sys,math,json,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
from render_chapter1_drink_sidewall import setup
from chapter1_round2 import basic,new_params
from character_motion import floor, D
from chapter1_round4_solver import ArmSolver,world,data,overlap,actual,restore,matlist,rays
from chapter1_round5_solver import flat_contact
from chapter1_round6_solver import prep,rim_contact,cup_nonrim
from chapter1_drink_sidewall import side_wall_contact
from chapter1_drink_path import sliced
from render_demo import point_at
from chapter1_articulation import face_grid,DOWN
from library_camera import metrics

def camera_views(cam,a,l):
    target=Vector((0,0,1.35));front=(a.root.matrix_world.to_3x3()@Vector((0,-1,0))).normalized()
    side=l.joint()-a.root.matrix_world.translation;side.z=0;side.normalize()
    return [(label,target+direction*10+Vector((0,0,1.0)),target) for label,direction in (("front",front),("side_profile",side),("three_quarter",(front+side).normalized()))]
def setcam(cam,v):
    cam.location=v[1];point_at(cam,v[2]);bpy.context.view_layer.update()
def face_clear(cam,a,geoms):
    c,dx,dz=face_grid(a);d=(cam.matrix_world.to_3x3()@DOWN).normalized()
    return sum(any(g[1].ray_cast(c+dx*x+dz*z-d*20,d,19.999)[0] is not None for g in geoms) for x in (-.55,-.275,0,.275,.55) for z in (-.26,0,.26,.52))
def main():
    out=Path(os.environ["OUT"]);out.mkdir(parents=True,exist_ok=True)
    scene,cam,a,_,art,__,cup,yaw=setup("drink");scene.frame_set(30)
    assert not scene.cycles.use_denoising
    # Stage anatomical side profile, upright torso, slight backward tilt
    # at the sip. Keep native limb lengths and the existing scaled cup.
    yaw=math.pi/2
    p=new_params("drink",29/59,29/30);p.update(pitch=0,torso=(0,0,0),head=(-.23,0,0),arms=[D,D],legs=[D,D])
    basic(a,p,(0,0,0),yaw);art.rigid();art.shift(Vector((0,0,-floor(a))));a.pose("neutral");bpy.context.view_layer.update()
    l=art.arms[0];arm=ArmSolver(l);decal,anchor,n,up,side,heads,other,body,extras=prep(a,art)
    outward=l.joint()-a.root.matrix_world.translation;outward.z=0;outward.normalize()
    if side.dot(outward)<0:side=-side
    views=camera_views(cam,a,l);z=Vector((0,0,1));forward=a.root.matrix_world.to_3x3()@Vector((0,-1,0))
    best=None;count=0
    # Actual rim vertex nearest the mouth corner, cup extending sideways
    # and outward instead of covering the central face.
    for corner,offset,tilt,az in itertools.product((.035,.065,.095,.125),(.025,.045,.059),map(math.radians,(25,40,55)),(-.65,0,.65)):
        hn=n-z*n.dot(z);hn.normalize();tangent=(hn*math.cos(az)+side*math.sin(az)).normalized()
        axis=(z*math.cos(tilt)-tangent*math.sin(tilt)).normalized();rot=z.rotation_difference(axis)
        rim=[rot@cup.data.vertices[32+i].co for i in range(32)]
        # Centre cup on the outside of the contact point; pick the inward
        # rim edge facing the actual mouth rather than the cup centre.
        tip=min(rim,key=lambda v:v.dot(side)+.6*v.dot(n))
        target=decal+side*corner+n*offset
        cm=Matrix.Translation(target-tip)@rot.to_matrix().to_4x4()
        cg=world(data(cup),cm);nonrim=cup_nonrim(cup,cm)
        cuphead=overlap(cg,heads);cupbody=overlap(cg,[body]+extras)
        # Candidate enumeration uses only the existing exact plane solver.
        # Contact still is selected visually first; no gate is waived.
        surfaces=[]
        for i in range(12):
            for h in (.15,.40,.65):
                surfaces.append(side_wall_contact(cup,cm,(i+.5)*math.tau/12,h))
        # Also allow actual bottom-cap support for the redesign.
        surfaces.append((cm@Vector((0,0,-.07)),(cm.to_3x3()@Vector((0,0,-1))).normalized()))
        for gq,gn in surfaces:
            for fu,fv,branch in itertools.product((.15,.50,.85),(.15,.50,.85),(-1,1)):
                sol=flat_contact(arm,gq,gn,yaw,(2,-1,fu,fv,branch,.004,Vector((0,0,0))))
                if sol is None:continue
                count+=1
                um,lm=map(Matrix,sol["matrices"]);elbow=lm.translation;end=lm@Vector((0,0,-l.b))
                # Require the elbow and the proximal lower arm below chin;
                # prefer elbow behind the hand, not projected over the eyes.
                chin=decal-up*.09
                armhead=sum(overlap(g,heads) for g in (sol["upper"],sol["lower"]))
                ab=overlap(world(sliced(l.upper,-.25*l.a),um),[body])+overlap(sol["lower"],[body])
                ao=sum(overlap(g,other+extras) for g in (sol["upper"],sol["lower"]))
                ca=overlap(cg,[sol["upper"],sol["lower"]]+other)
                chin_pen=max(0,elbow.z-chin.z)+max(0,(elbow.lerp(end,.55)).z-chin.z)
                back_pen=max(0,(elbow-end).dot(forward))
                # Cheap geometric screening before evaluating all three
                # cameras. Keep exact best across visually plausible poses.
                if cuphead or cupbody or ca:continue
                if chin_pen>.08:continue
                blocks=[]
                for v in views:
                    setcam(cam,v);blocks.append(face_clear(cam,a,[sol["upper"],sol["lower"],nonrim]))
                lat,gap,center=rim_contact(cup,cm,decal,n)
                cap=(lm.to_3x3()@DOWN).normalized().dot(-gn)
                support=min((v-gq).dot(gn) for v in sol["hand"][0])
                outward_offset=(elbow-l.joint()).dot(outward)
                score=(max(blocks),sum(blocks),armhead,ab+ao,chin_pen,back_pen,max(0,lat-.03)+max(0,abs(gap)-.06),abs(corner-.065))
                row=dict(parameters=[corner,offset,tilt,az,fu,fv,branch],arm_matrices=sol["matrices"],cup_matrix=matlist(cm),face_central_rays_by_view=blocks,head_arm_intersections=armhead,cup_head_intersections=cuphead,cup_body_intersections=cupbody,cup_arm_intersections=ca,arm_body_intersections=ab,arm_other_intersections=ao,grip_gap=sol["gap"],support_clearance=support,cap_alignment=cap,rim_center_lateral=lat,rim_center_gap=gap,actual_rim_tip=list(target),grip_anchor=list(gq),grip_normal=list(gn),elbow=list(elbow),elbow_outward_relative_shoulder=outward_offset,chin_penalty=chin_pen,back_penalty=back_pen,score=list(score))
                if best is None or score<best[0]:best=score,row
    assert best is not None,"No exact visual-first profile candidate"
    row=best[1];restore(l,row["arm_matrices"]);cup.matrix_world=Matrix(row["cup_matrix"]);bpy.context.view_layer.update()
    cameras={}
    for v in views:
        setcam(cam,v);cameras[v[0]]=matlist(cam.matrix_world)
        scene.render.filepath=str(out/f"drink_{v[0]}.png");bpy.ops.render.render(write_still=True)
    row.update(candidates_exact=count,frame=30,cameras=cameras,status="VISUAL_FIRST_CONTACT_ONLY",denoising=False,full_sequence_validation=False,root_matrix=matlist(a.root.matrix_world))
    (out/"profile_contact.json").write_text(json.dumps(row,indent=2,allow_nan=False)+"\n")
    print("DRINK_PROFILE_CONTACT",json.dumps(row),flush=True)
if __name__=="__main__":main()
