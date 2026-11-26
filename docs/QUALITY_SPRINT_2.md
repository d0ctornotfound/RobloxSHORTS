# Quality Sprint 2 — measured look pass

Supervisor-measured targets take priority over the loosely stated near-thirds proportion: head width 0.95 × torso width, head height 22% of bare body height. Torso and legs split the remainder, each 39%. Scene units: 1.064 × .78 × .502 head, 1.12 × .65 × .889 torso, .56 × .65 × 1.26 arms, .56 × .64 × .889 legs. Arm ends around mid-thigh. Excludes hair/accessories from anatomical height; lineup shows full styled silhouette.

Face ink maps are redrawn at 60% prior scale and centered lower. Lead has explicit spiky swept mesh (tapered locks joined with a sculpted base, no textile material) and recurring red enamel star chest pin; friend alone wears a beanie. Matte skin roughness .87–.96, specular IOR .04. Original sweaters and printed tees remain; green and blue prints and yellow stitched pants added. Two seated patrons in wide; edge dressing, taller enclosure. Ceiling measured with 100×100 first-visible-surface camera rays, maximum contiguous top band and total area, target <=10% for medium/wide. This is geometry sampling, not segmentation of denoised image.

Four independent stills (studio lineup, portrait, reaction, wide). Existing story and animation paths unchanged. 720×1280 / 128 samples, same verified FFmpeg nlmeans pipeline; full 1080×1920 / 192 samples. Run from repo root:

```sh
blender -b --python-exit-code 1 --python scripts/render_quality_stills.py -- --profile preview --output render/quality
```

Workflow: Quality sprint hero stills. Original Sprint 2 run [45862909811](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45862909811) succeeded at `1e95da5`, all four jobs and packaging. Artifact `roblox-quality-sprint2-hero-preview`, ID 15140365069. Measured ceiling: reaction 6%, wide 4%; both maximum top band and sampled area. Supervisor accepted proportion/face/hair progress but requested lineup framing and yellow colour corrections. Follow-up renders all four shots with consistent lemon-yellow texture and neutral studio light; lineup is landscape 1280×900 (full 1920×1350) to use height without cutting off side-by-side full bodies. Café shots remain vertical. Final corrected workflow pending.
