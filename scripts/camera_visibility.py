"""Rendered object-ID visibility gate: full scene vs isolated projected silhouette."""
import bpy
from array import array

def visibility_gate(scene,out,segment,groups):
    layer=bpy.context.view_layer
    old_index=layer.use_pass_object_index;layer.use_pass_object_index=True
    old_nodes=scene.use_nodes;scene.use_nodes=True
    tree=scene.node_tree
    rl=tree.nodes.new("CompositorNodeRLayers")
    file=tree.nodes.new("CompositorNodeOutputFile")
    file.base_path=str(out);file.format.file_format="OPEN_EXR"
    file.format.color_mode="RGB";file.format.color_depth="32"
    tree.links.new(rl.outputs["IndexOB"],file.inputs[0])
    objects=[o for o in scene.objects if o.type in ("MESH","FONT","CURVE")]
    original={o:(o.hide_render,o.pass_index) for o in objects}
    old_samples=scene.cycles.samples;scene.cycles.samples=4
    def count(label):
        file.file_slots[0].path="id_"+segment+"_"+label+"_"
        bpy.ops.render.render()
        path=out/(file.file_slots[0].path+f"{scene.frame_current:04d}.exr")
        im=bpy.data.images.load(str(path),check_existing=False)
        im.colorspace_settings.name="Non-Color"
        pix=array("f",[0])*(im.size[0]*im.size[1]*4);im.pixels.foreach_get(pix)
        total=im.size[0]*im.size[1]
        result={name:sum(abs(pix[i]-idx)<.25 for i in range(0,len(pix),4)) for idx,name in enumerate(groups,1)}
        bpy.data.images.remove(im)
        return result,total
    try:
        for o in objects:o.pass_index=0
        for idx,(name,meshes) in enumerate(groups.items(),1):
            for o in meshes:o.pass_index=idx
        visible,total=count("visible")
        result={}
        for name,meshes in groups.items():
            keep=set(meshes)
            for o in objects:o.hide_render=original[o][0] or o not in keep
            isolated,_=count("isolated_"+name)
            projected=isolated[name];seen=visible[name]
            fraction=min(1,seen/projected) if projected else 0
            result[name]={"visible_pixels":seen,"projected_silhouette_pixels":projected,
                          "visible_frame_share":seen/total,"projected_frame_share":projected/total,
                          "occluded_fraction":1-fraction,"pass":projected>0 and fraction>=.60}
        return result
    finally:
        for o,(hidden,idx) in original.items():o.hide_render=hidden;o.pass_index=idx
        scene.cycles.samples=old_samples
        tree.nodes.remove(file);tree.nodes.remove(rl)
        layer.use_pass_object_index=old_index;scene.use_nodes=old_nodes
