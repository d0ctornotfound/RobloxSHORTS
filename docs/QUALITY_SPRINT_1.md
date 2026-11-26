# Quality Sprint 1 — hero look development

New versioned modules: quality_character.py, quality_textures.py, quality_cafe.py. The legacy builders and Stage B/C renderers remain frozen for reproducibility. The new Character inherits the prior expression/pose/grip interfaces, but changed body dimensions mean animation blocking and contact must be revalidated after visual approval.

The proportions are expressed in scene units in Character.PROPORTIONS. The head is .90 × .80 × .80; torso 1.12 × .61 × .80; arm .56 × .59 × .80; leg .55 × .60 × .80. These are an artistic R6-inspired approximation based on the written benchmark, not measurements of the reference videos or a Roblox-exported rig. Drawn 1024px face and garment maps, continuous molded hair, geometric sweater motif, screen-printed tee, denim stitching. Three tables, dressed counter, menu, pictures, real window aperture with outdoor geometry, plants and practical pendants.

Local render:

```sh
blender -b --python-exit-code 1 --python scripts/render_quality_stills.py -- --profile preview --output render/quality
```

Preview 720×1280, 96 CPU Cycles samples, OpenImageDenoise, AgX medium-high contrast, subtle saturation grade. Full 1080×1920, 160 samples. The close-up has shallow depth of field. GitHub Actions workflow Quality sprint hero stills renders the three independent shots in parallel and packages their actual PNGs and manifest. No paid services or external visual assets.
