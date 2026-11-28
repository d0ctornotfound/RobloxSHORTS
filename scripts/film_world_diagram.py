"""Reusable cast-based world diagram. No story IDs or fixed layout.
Scene adapter owns placement/support and camera; this module creates only
ground-space graphics around real actor marks. Requires Blender.
"""
import math
import bpy
from mathutils import Vector

def _material(name,rgb):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
    b=m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value=(*rgb,1)
    b.inputs["Roughness"].default_value=.85
    return m

def _curve(name,points,radius,material,parent):
    data=bpy.data.curves.new(name,"CURVE");data.dimensions="3D";data.resolution_u=1
    data.bevel_depth=radius;data.bevel_resolution=2
    s=data.splines.new("POLY");s.points.add(len(points)-1)
    for p,v in zip(s.points,points):p.co=(*v,1)
    ob=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(ob)
    ob.parent=parent;data.materials.append(material);return ob

def _label(name,content,position,size,mat,parent,rotation=0):
    d=bpy.data.curves.new(name,"FONT");d.body=content;d.align_x="CENTER";d.align_y="CENTER";d.size=size
    ob=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(ob);ob.parent=parent
    ob.location=position;ob.rotation_euler.z=rotation;d.materials.append(mat);return ob

def build(spec,place):
    """spec: columns of real actor marks; each actor has id, label, xyz, yaw.
    place(id,xyz,yaw) must place the real cast actor at its evaluated mark.
    links: from/to actor ids, normalized reveal_in/out. No portrait substitutes.
    Ground routes may be explicitly authored with waypoints to avoid overlaps.
    """
    root=bpy.data.objects.new(spec.get("name","World cast diagram"),None)
    bpy.context.scene.collection.objects.link(root)
    marks={};label_color=_material("diagram labels",spec.get("label_color",(.12,.12,.12)))
    z=spec.get("graphics_z",.035);radius=spec.get("line_radius",.025)
    for group in spec["formations"]:
        for actor in group["actors"]:
            cid=actor["id"]
            if cid in marks:raise ValueError("duplicate diagram actor "+cid)
            v=Vector(actor["xyz"]);marks[cid]=v
            place(cid,list(v),actor.get("yaw",0))
            dx,dy=actor.get("label_offset",[0,-.55])
            _label("label "+cid,actor.get("label",cid),(v.x+dx,v.y+dy,z),spec.get("font_size",.32),label_color,root)
        if group.get("heading"):
            _label("formation heading",group["heading"],group["heading_xyz"],spec.get("heading_size",.48),label_color,root)
    if spec.get("title"):_label("diagram title",spec["title"],spec["title_xyz"],spec.get("title_size",.50),label_color,root)
    arrows=[];default_color=spec.get("arrow_color",(.72,.12,.08))
    for i,l in enumerate(spec["links"]):
        a=marks[l["from"]].copy();b=marks[l["to"]].copy()
        if (a-b).length<.01:raise ValueError("degenerate diagram link")
        a.z=b.z=z
        a+=Vector((*l.get("start_offset",[0,0]),0));b+=Vector((*l.get("end_offset",[0,0]),0))
        d=(b-a).normalized()
        a+=d*l.get("start_clearance",.42);b-=d*l.get("end_clearance",.42)
        points=[a]+[Vector((p[0],p[1],z)) for p in l.get("waypoints",[])]+[b]
        if any((q-p).length<.01 for p,q in zip(points,points[1:])):raise ValueError("degenerate diagram route")
        mat=_material("diagram arrow "+str(i),l.get("color",default_color))
        shaft=_curve("diagram link "+str(i),points,radius,mat,root)
        tangent=(points[-1]-points[-2]).normalized()
        side=Vector((-tangent.y,tangent.x,0));size=l.get("arrowhead_size",.20)
        tip=points[-1];head=_curve("diagram head "+str(i),[tip-tangent*size+side*size*.55,tip,tip-tangent*size-side*size*.55],radius,mat,root)
        start,end=l.get("reveal",[0,1])
        if not 0<=start<end<=1:raise ValueError("invalid reveal interval")
        arrows.append((l["from"],l["to"],shaft,head,start,end))
    return {"root":root,"marks":marks,"arrows":arrows}

def evaluate(diagram,u):
    """Evaluate reveal at an absolute sample, preserving deterministic replay."""
    records=[]
    for a,b,shaft,head,start,end in diagram["arrows"]:
        f=max(0,min(1,(u-start)/(end-start)))
        shaft.hide_render=f<=0;shaft.data.bevel_factor_end=f
        head.hide_render=f<.999999
        records.append({"from":a,"to":b,"fraction":f,"arrowhead_visible":not head.hide_render})
    return {"actor_count":len(diagram["marks"]),"link_count":len(records),"links":records}
