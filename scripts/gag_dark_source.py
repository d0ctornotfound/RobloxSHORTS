"""Unmodified Variant B beauty, then hard object/material index diagnostic passes.
Blender index buffers are not anti-aliased: mixed/codec-edge pixels receive the
frontmost sampled ID, not a causal decomposition of light transport."""
import bpy,json
import numpy as np
from array import array

def capture(scene,out,frame):
    layer=bpy.context.view_layer
    objects=[o for o in scene.objects if o.type in ("MESH","FONT","CURVE","SURFACE","META")]
    materials=list(bpy.data.materials)
    assert max(len(objects),len(materials))<32767
    old_o={o:o.pass_index for o in objects};old_m={m:m.pass_index for m in materials}
    old_ob=layer.use_pass_object_index;old_ma=layer.use_pass_material_index
    old_nodes=scene.use_nodes
    old_samples=scene.cycles.samples
    nodes=[]
    try:
        for i,o in enumerate(objects,1):o.pass_index=i
        for i,m in enumerate(materials,1):m.pass_index=i
        layer.use_pass_object_index=True;layer.use_pass_material_index=True
        scene.use_nodes=True;tree=scene.node_tree
        rl=tree.nodes.new("CompositorNodeRLayers");nodes.append(rl)
        for kind,socket in (("object","IndexOB"),("material","IndexMA")):
            file=tree.nodes.new("CompositorNodeOutputFile");nodes.append(file)
            file.base_path=str(out);file.format.file_format="OPEN_EXR"
            file.format.color_mode="RGB";file.format.color_depth="32"
            file.file_slots[0].path=f"source_{frame:04d}_{kind}_"
            tree.links.new(rl.outputs[socket],file.inputs[0])
        # Preserve original samples/seed and scene; no extra lights or visibility changes.
        bpy.ops.render.render(write_still=False)
        result={}
        for kind in ("object","material"):
            path=out/f"source_{frame:04d}_{kind}_{scene.frame_current:04d}.exr"
            im=bpy.data.images.load(str(path),check_existing=False)
            im.colorspace_settings.name="Non-Color"
            width,height=im.size[:]
            buf=np.empty(width*height*4,dtype=np.float32);im.pixels.foreach_get(buf)
            vals=buf.reshape(height,width,4)[::-1,:,0]
            rounded=np.rint(vals)
            assert np.isfinite(vals).all() and np.max(np.abs(vals-rounded))<.05,(kind,float(np.max(np.abs(vals-rounded))))
            result[kind]=rounded.astype(np.uint16)
            bpy.data.images.remove(im)
        np.savez_compressed(out/f"ids_{frame:04d}.npz",**result)
        mapping={"objects":{str(i):{"name":o.name,"materials":[m.name for m in o.data.materials if m]} for i,o in enumerate(objects,1)},"materials":{str(i):m.name for i,m in enumerate(materials,1)}}
        (out/f"ids_{frame:04d}.json").write_text(json.dumps(mapping,indent=2)+"\n")
    finally:
        for o,i in old_o.items():o.pass_index=i
        for m,i in old_m.items():m.pass_index=i
        for n in reversed(nodes):scene.node_tree.nodes.remove(n)
        layer.use_pass_object_index=old_ob;layer.use_pass_material_index=old_ma
        scene.cycles.samples=old_samples;scene.use_nodes=old_nodes
