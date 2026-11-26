# Quality Sprint 2 — measured look pass

Supervisor-measured targets take priority over the loosely stated near-thirds proportion: head width 0.95 × torso width, head height 22% of bare body height. Torso and legs split the remainder, each 39%. Scene units: 1.064 × .78 × .502 head, 1.12 × .65 × .889 torso, .56 × .65 × 1.26 arms, .56 × .64 × .889 legs. Arm ends around mid-thigh. Excludes hair/accessories from anatomical height; lineup shows full styled silhouette.

Face ink maps are redrawn at 60% prior scale and centered lower. Lead has explicit spiky swept mesh (tapered locks joined with a sculpted base, no textile material) and recurring red enamel star chest pin; friend alone wears a beanie. Matte skin roughness .87–.96, specular IOR .04. Original sweaters and printed tees remain; green and blue prints and yellow stitched pants added. Two seated patrons in wide; edge dressing, taller enclosure. Ceiling measured with 100×100 first-visible-surface camera rays, maximum contiguous top band and total area, target <=10% for medium/wide. This is geometry sampling, not segmentation of denoised image.

Four independent stills (studio lineup, portrait, reaction, wide). Existing story and animation paths unchanged. 720×1280 / 128 samples, same verified FFmpeg nlmeans pipeline; full 1080×1920 / 192 samples. Run from repo root:

```sh
blender -b --python-exit-code 1 --python scripts/render_quality_stills.py -- --profile preview --output render/quality
```

Workflow: Quality sprint hero stills. Original Sprint 2 run [45862909811](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45862909811) succeeded at `1e95da5`, all four jobs and packaging. Artifact `roblox-quality-sprint2-hero-preview`, ID 15140365069. Measured ceiling: reaction 6%, wide 4%; both maximum top band and sampled area. Supervisor accepted proportion/face/hair progress but requested lineup framing and yellow colour corrections. Follow-up renders all four shots with consistent lemon-yellow texture and neutral studio light; lineup is landscape 1280×900 (full 1920×1350) to use height without cutting off side-by-side full bodies. Café shots remain vertical. Final corrected workflow [45864864639](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45864864639) completed successfully at commit `596aceee4e8dfc0f29825770461f400bcc1e808f`; all four render jobs and packaging succeeded. Artifact [roblox-quality-sprint2-hero-preview](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45864864639/artifacts/15140261957), ID 15140261957. All four downloaded PNGs were independently checked byte-for-byte against the packaged artifact and visually inspected.


## Final verified evidence

| Still | Resolution | Artifact ID | Result |
|---|---|---|---|
| 00_lineup | 1280×900 | 15139906932 | Success; projected bounds x=3.66–96.34%, y=8.45–91.97%; height coverage 83.52%, previously 31.97% |
| 01_portrait | 720×1280 | 15139413318 | Success; distinct spiky hair and star pin |
| 02_cup_reaction | 720×1280 | 15139693036 | Success; ceiling area and top band both 6% |
| 03_cafe_wide | 720×1280 | 15141080425 | Success; two patrons, ceiling area and top band both 4% |

Mesh measurements unchanged: head width / torso width 95.00%, head height / bare body height 22.02%. All four stills use 128 Cycles samples and FFmpeg nlmeans. Final PNG SHA-256:

- 00_lineup: f0efac43fcffd30564022ad73e9c152a2e3693891c7b30fcd2f9bd77b9440e29
- 01_portrait: c14ea739508aa1366e6616089ca3f63311a673d791c63c72fd79cc379484dada
- 02_cup_reaction: ae87ae2d5dce59c46e6719f2a6d2b7d5a3101fe2ca7bc3b429800288438181f7
- 03_cafe_wide: 48cf9e6d9bae69a580245d1f0e3b95f208790da73cc9d51c794c785e91b7e138

Visual inspection: lineup framing resolved; trouser swatch shifted from median RGB (241,149,91), hue 23°, to (219,224,148), hue 64° in the studio. Orange eliminated; shade is pale lemon/greenish yellow, with a more olive cast in café shadow. This is not an exact saturated reference-yellow match. The reaction remains medium-long rather than strict medium; foreground floor remains generous and patrons are partly hidden by the leads. Residual background grain and sculpted hair sheen remain. No visual approval claimed. No stories or animation started.
