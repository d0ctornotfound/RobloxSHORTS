---
name: roblox-shorts
description: Build, render, edit and verify original vertical R6-inspired animated story shorts using the supplied R6 armature, procedural sets and GitHub Actions. Use when asked to make a Roblox-style story short or continue this production system.
---

# Roblox Shorts production skill

## Start here

This repository makes original, vertical 9:16, narrated-story-style 3D shorts using an imported R6 armature, procedural Blender sets, textures, animation and an FFmpeg edit. The production output is an H.264 MP4 with burned-in single-word captions, original synthesized music/SFX, and an optional user-supplied narration WAV. The default deliverable has no spoken audio. Read [the reference benchmark](docs/REFERENCE_BENCHMARK.md), [current project state](docs/PROJECT_STATE.md), [historical rejected character development](docs/QUALITY_SPRINT_2.md), and [integration evidence](docs/INTEGRATION_SPRINT.md). Treat the latest supervisor verdict as authoritative when older development notes conflict.

A fresh ChatGPT chat or another agent must have access to this repository and a way to execute Blender locally or access authorized GitHub Actions. **A repository SKILL.md does not auto-install a ChatGPT skill or grant tool permissions.** The user starts a fresh chat, connects/authorizes this repo and points the agent to this root file. Read the actual source before changing it. No external visual assets, paid AI services or ElevenLabs usage without explicit user authorization. Never assume Actions is unlimited or free: check runner type, repo visibility, quotas and billing before execution; prefer existing standard CPU runners. Do not promise background work or invent render results. The scope is the user's requested short, not unsolicited further shorts or a separate look-development sprint.

## Visual and story grammar

- Reference target: classic supplied R6 block geometry, simple matte clothing, large centered expression decals, recurring lead, warm cinematic but legible lighting, fully dressed environments, physical interactions with visible contact. Use the exact supplied CC BY R6 rig, original material/accessory variations and original props.
- Keep the story immediately comprehensible: surreal premise/hook in the first seconds, concrete escalation, a physical gag or consequential interaction, and a payoff recalling an earlier detail. Visuals must depict the narration beat, not merely share its topic.
- Prefer purposeful cuts every 1–3 seconds, medium shots dominant, emotional close-ups, wide shots only to establish a location or necessary interaction. Keep characters large in the lower two-thirds, faces and active hands inside the frame, critical props unobscured, captions readable. Avoid empty ceiling/floor and set edges. Prefer enclosed frontal staging over oblique cutaways. The first approved preview has longer holds and wider two-shots than this aspirational grammar.
- Bold white single-word captions with black outline near bottom, timed continuously across the narration; do not cover the gag or crop the text. Music/SFX must support, not overpower, narration.

## Authoritative character standard — supplied R6 armature (approval pending)

**Supervisor directive 2026-11-26:** the previous procedural soft-toy character standard is rejected. Use [assets/r6_rigged.glb](assets/r6_rigged.glb) for every new character. Exact uploaded binary (149064 bytes, SHA-256 3a0f310faf09cf161f7036a4c0df1a20202b967683700badc4440309c0a7d95a, Git blob 5068dbb4ee2509336b1623dedf3da68a47e7c6da). Source attribution: Roblox-r6-rigged (1) by hopewell664, CC BY 4.0; see [assets/R6_ATTRIBUTION.md](assets/R6_ATTRIBUTION.md). The old quality_character.py and its procedural body/proportion spec are retired for new work; retain legacy files only to reproduce the historical previews.

| Source rest-pose measurement | Native units (width × depth × height) |
|---|---|
| Head | approximately 1.2 × 1.2 × 1.2 |
| Torso | 2 × 1 × 2 |
| Arms | approximately 1 × 1 × 2 each |
| Legs | approximately 1 × 1 × 2 each |
| Bare avatar total height | 5.1 (approximately 5.10125) |
| Head width / torso width | approximately 0.60 |

One imported armature with _rootJoint, Torso_00, Head_01, Left Arm_02, Right Arm_03, Left Leg_04, Right Leg_05 and end bones (12 joints total), two original skinned meshes, no source animation clips. Keep geometry, tiny source bevels, rigid vertex weights and native proportions intact. [scripts/r6_character.py](scripts/r6_character.py) validates the exact asset hash, armature, dimensions and skin bindings, then applies a uniform normalization to a 2.28-unit bare avatar height solely to match existing set scale (about .447×). This is not a change to proportions. Skin, clothing and accessories use flat matte plastic (roughness 1, specular IOR level 0). Simple colored torso and legs or restrained clothing textures; do not create puffy clothing or realistic limbs.

Identity: lead has blocky espresso hair, teal shirt, navy trousers and the red star chest pin; friend has a blocky ochre beanie with folded cuff, cream shirt and golden yellow trousers; teacher has simple dark block bun and open rectangular burgundy glasses, mauve shirt and dark trousers. Extras use the same source rig and simple alternate materials/accessories. Hair, hats, glasses and face plane are parented to the real Head_01 bone; the lead pin is on Torso_00. Never replace the imported body with generated geometry. No invented wrist/finger bones: the source has rigid R6 arms, not articulated hands.

Generate the six transparent 1024² expression PNGs with system Python + Pillow: python3 scripts/r6_faces.py --output assets/r6_faces. Neutral, happy (two black oval eyes and large curved smile), shocked, sad, unimpressed and laughing use large centered classic black ink, inspired by the supplied bundled face, not the retired low/small face rule. Apply as a transparent front decal and swap per beat with the existing ExpressionTrack or its bone-aware equivalent; the actual decal follows Head_01.

~~~python
from r6_character import R6Character
lead = R6Character("lead", "lead")
friend = R6Character("friend", "friend")
teacher = R6Character("teacher", "teacher")
extra = R6Character("extra", "patron_green", shirt=(.15,.28,.75))
extra.root.location = (2.4, 1.8, 0)
lead.pose("happy")
lead.set_bone("head", (.0,.0,.15), frame=1)
lead.aim_arm(1, (.1,-.95,-.15), frame=1)
# lead.grips[1] is a real bone-parented socket, not a free-floating hand.
~~~

All character joint motion must key pose bones through set_bone / aim_arm (index 0 = negative-X/right arm, index 1 = positive-X/left arm). Leg/torso/head posing uses actual bones; do not animate independent meshes, use artificial wrists/fingers, or reparent the skinned head to an empty. The existing GripAttachment COPY_TRANSFORMS can bind to the new arm-bone socket; re-evaluate world-space contact and release. A rigid arm cannot close fingers. Bone-parented contact sockets on Head_01 support cake/bun payoffs; calibrate them against actual new accessory meshes. Use evaluated/deformed vertices (mesh_points and group_points) for framing and occlusion; object rest bounds do not describe posed skinned geometry.

**Approval gate:** do not rerender either story or start another short until supervisor explicitly approves the new stills. [R6 approval still workflow](.github/workflows/r6-approval.yml) runs only three stills: full-body neutral studio lineup, lead+friend café, lead+teacher classroom. It tests original skinned-mesh deformation, grip socket movement, world attachment error and head-decal following. It uses the existing set builders, not a short render. The current legacy render_story.py and render_classroom.py still depend on the retired procedural Character/Teacher interface: the required production migration is to instantiate R6Character, replace old head pivots and shoulder/wrist/finger transforms with pose bones and bone-parented sockets, retarget contact geometry/seated poses/prop support and use evaluated skin bounds for the existing camera gates. Story timing, sets, camera rules, validation thresholds, captions and edit pipeline carry over unchanged. Do not claim migrated shorts are validated until their own new-rig runs pass. Preserve old renderers only as historical reproduction paths during this approval stage; do not run them.

## Story data and actual implementation boundary

The worked example is [stories/the_last_slice.json](stories/the_last_slice.json). Copy it to a NEW story file; do not overwrite the approved example. Every field is listed below. Seconds are relative to video start; shot intervals are start inclusive, end exclusive; frame index = round(seconds × fps)+1. Use chronological keys starting at zero where applicable; match shot boundaries on the frame grid. Angles in radians, positions XYZ in Blender units.

| Field | Type and meaning |
|---|---|
| id | Unique snake_case identifier; output file id.mp4 |
| title | Human-readable story title |
| location | Scene identifier; café and classroom have existing set builders |
| duration | Positive seconds; example 12 |
| narration | Exact complete spoken script, including punctuation; whitespace-normalized token join must match |
| characters | Object keyed by character ID; existing driver requires lead and friend |
| characters.ID.position | Three-number XYZ nominal root position |
| characters.ID.lead | Legacy Boolean identifying recurring lead vs friend; map to R6Character role when migrating |
| characters.ID.reach_arm | 0 = negative-X shoulder, 1 = positive-X shoulder in actor-local coordinates |
| props.plate.type | ceramic_plate in example; semantic prop identifier |
| props.plate.support_z | Plate base/table support height, 1.18 in example |
| props.plate.radius | Plate outer radius, .29 in example |
| props.slice.type | layer_cake in example; semantic prop identifier |
| props.slice.plate_offset | XYZ cake-base offset relative to plate, [0,0,.065] |
| props.slice.head_support | Legacy nominal support height, 2.525; current corrected driver overrides with embedded support 2.64 and mesh adjacency check |
| shots | Ordered array, contiguous and covering [0,duration) |
| shots[].id | Unique ordered shot ID; current driver/workflow know four example IDs |
| shots[].start / end | Seconds, no overlaps or gaps |
| shots[].kind | Shot intent, e.g. wide_two, medium_two, close_up, reaction_two |
| shots[].camera.position / target | Nominal camera XYZ position and look-at XYZ |
| shots[].camera.lens | Nominal focal length in mm |
| shots[].characters | Array of hero IDs to protect and measure |
| shots[].action | Named visual beat label, e.g. notice, reach_and_launch, cake_lands, payoff |
| shots[].caption | Optional human-readable beat text (example has this for first two shots); actual captions come from captions[] |
| captions | Ordered array of {start,end,text}; contiguous, full duration, enough frames for each word, joined text exactly equals narration |
| expressions | Object of actor ID to sorted [time, expression] keys; discrete, start at 0 |
| head_turns | Object of actor ID to sorted [time,yaw,pitch] keys; smooth interpolation, start at 0 |
| actions | Named time keys required by current choreography, described below |
| sfx | Array of {kind,time}; supported procedural kinds ding, slide, whoosh, thud |

Current action keys: notice (reaction cue), lead_reach_start, lead_contact, friend_reach_start, friend_contact, spin_start, launch, landing, payoff. Keep chronological reach/contact order, launch before landing, enough post-landing hold. Example: notice .65, lead reach 2.65–4.1, friend reach 4.35–5.75, spin 5.75, launch 6.55, land 7.55, payoff 9.5. Its four shots: 01_notice [0,2.5), 02_reach [2.5,7), 03_impact [7,9.5), 04_payoff [9.5,12). Its exact narration: “We both saw the last slice at the same time. I reached for it. He reached for it. The plate decided neither of us deserved it.” Use the JSON file for complete values and tracks.

**Not a generic script-to-video engine yet.** The current renderer accepts --story but is specialized to this two-person café cake gag. Root positions, shot camera candidates, patron visibility, embedded landing support, plate/cake builders and action choreography are hard-coded/retargeted; nominal JSON position, camera and head_support values and semantic labels do not automatically drive arbitrary scenes or actions. The GitHub workflow also hard-codes the example file/default, four shot IDs, frame-grab timestamps, filename and artifact name. Merely changing JSON or narration will not create a different physical story.

For the fresh-chat reuse test: design a distinct second short from the requested premise, map each narrated beat to visible action, save a separate JSON spec, then deliberately adapt/extend the story driver and props, shot camera blocking and action validation to that story. Reuse the supplied R6 builder, set, reusable interaction/expression systems, editor and pixel gate. Prefer extracting story-specific drivers/configuration or adding a separate driver/selector over breaking the approved example. Parameterize the workflow story selection, shot matrix, expected chunk count, renderer/editor --story, output filenames, timestamps and artifact naming consistently before triggering a different story. If preserving the old workflow, create a new story-specific workflow or explicitly select the new driver. Keep existing demo and approved story regression paths intact. Do not claim a generalized capability until it has rendered and been reviewed. Short #2 was implemented in a fresh chat on the old rig; new-rig approval is now the blocking milestone.

## Production pipeline

Dependencies: Blender 4.0-compatible Python/bpy (CI tested Ubuntu 24.04 package Blender 4.0.2), Python 3, FFmpeg + ffprobe with libass/libx264, DejaVu Sans font. Historical reproduction commands for the previously verified example (DO NOT run either short while R6 approval is pending; update the drivers to the new rig before production resumes):

~~~sh
# 1. Build continuous animation and render all frames into a clean directory.
blender -b --python-exit-code 1 --python scripts/render_story.py -- \
  --story stories/the_last_slice.json --profile preview --shot all --output render/story

# 2. Edit, synthesize original music and effects, burn captions, test narration slot.
python3 scripts/edit_story.py --story stories/the_last_slice.json \
  --profile preview --frames render/story --output render/final --verify-slot

# 3. Copy reproducibility data and enforce darkness gate on the actual encoded MP4.
cp render/story/story_manifest.json render/story/story.blend render/final/
cp stories/the_last_slice.json render/final/
python3 scripts/validate_story_pixels.py --video render/final/the_last_slice.mp4 \
  --manifest render/final/story_manifest.json --output render/final/pixel_validation.json

# 4. Inspect encoded video, extract exact comparison frames and hash outputs.
mkdir -p render/final/frame_grabs
for item in 01_notice_1p5:1.5 02_reach_4p0:4.0 02_reach_5p9:5.9 03_impact_7p0:7.0 03_impact_8p2:8.2 04_payoff_10p7:10.7; do
  ffmpeg -y -v error -ss "${item#*:}" -i render/final/the_last_slice.mp4 \
    -frames:v 1 "render/final/frame_grabs/${item%:*}.png"
done
ffprobe -v error -show_streams -show_format -of json render/final/the_last_slice.mp4
sha256sum render/final/the_last_slice.mp4
~~~

Use clean output directories for rerenders; the editor asserts exact frame filenames/count, so stale frames must not leak into a new edit. For parallel rendering, pass one actual shot ID to --shot and separate output folders; assemble frames in order after checking identical manifests, no duplicate/missing frames. The first shot saves the packed story.blend. One continuous keyed timeline is reconstructed deterministically per chunk; no prop teleport at cuts. For a new story substitute its spec/driver/ID and its own timestamp list. Do not reuse the approved example's files as evidence for a new render.

| Animation profile | Resolution | FPS | Cycles samples | Status |
|---|---|---:|---:|---|
| preview | 432 × 768 | 12 | 24 | Proven, short #1 approved at preview |
| full | 1080 × 1920 | 24 | 96 | Configured, not yet proven for complete short |

Adaptive thresholds .065 preview/.02 full; CPU OIDN unavailable in tested runner, Cycles denoise disabled; FFmpeg hqdn3d=2.5:2:3:2.5 before captions. Full may exceed runner time; check actual success, don't claim a full master from a preview. Quality stills use a separate profile (preview 720×1280, lineup 1280×900; 128 samples, FFmpeg nlmeans; full 1080×1920/1920×1350 at 192 samples).

### Optional user narration

Re-edit existing frames, no Blender re-render needed:
~~~sh
python3 scripts/edit_story.py --story stories/the_last_slice.json \
  --profile preview --frames render/story --output render/narrated \
  --narration /absolute/path/to/approved_take.wav --verify-slot
~~~
Use matching narration length/timing and listen; caption timings are distributed per caption segment, not automatic speech alignment. The built-in mix leaves voice at unity, pads/trims to story duration, applies fixed music gain .28 with narration and a limiter. It is not dynamic sidechain ducking or a LUFS mastering system. The supervisor separately mixed narration locally with sidechain ducking and reported −17.9 LUFS for short #1; that private master is not the GitHub artifact. --verify-slot uses a synthetic tone in a temporary directory and never ships it. Never generate voice or spend paid credits without explicit authorization. Re-run the pixel gate and probe on a narrated export too.

### GitHub Actions

[Integrated quality story short](.github/workflows/story-render.yml) runs on pushes to main touching stories/**, render_story.py, stage_c_*.py, quality_*.py, edit_story.py, validate_story_pixels.py or the workflow itself. Manual dispatch accepts preview/full; default is preview. Current matrix four example shots, CPU Ubuntu 24.04, 60 min per render job; edit 15 min. Check Actions permission and billing before dispatch. If a connector lacks dispatch, authorized relevant push triggers workflow; do not push meaningless changes to force runs. Fetch actual run status, failed job logs and artifact IDs. Intermediate story-frames-<shot> artifacts (1-day retention) hold frames + story_manifest.json, plus packed story.blend in first shot. Edit verifies identical manifests and complete unique frames, runs the editor, extracts six grabs and enforces pixel gate. Final roblox-the-last-slice-corrected-<profile>-12s (7 days) includes the_last_slice.mp4, story.blend, story_manifest.json, source JSON, metadata.json, word_timing.json, captions.ass, music.wav, sfx.wav, mix.wav, frame_grabs/, pixel_validation.json. Raw frames are in intermediate archives, not final package. Download promptly; expired artifacts require reproduction, not invented links.

Historical [Quality sprint hero stills](.github/workflows/quality-stills.yml) is manual only (retired character standard; do not use for new approval); four-shot matrix and package roblox-quality-sprint2-hero-<profile>, with quality_manifest.json. Local equivalent: blender -b --python-exit-code 1 --python scripts/render_quality_stills.py -- --profile preview --shot all --output render/quality. Historical [demo workflow](.github/workflows/blender-render.yml) is not the production short; keep its regression path separate. Documentation-only commits do not trigger the story workflow.

## Validation: numeric AND visual

Do not call a short production-complete until the render and edit succeed and actual MP4 and frame grabs exist. Do not call it approved until the user/supervisor approves the actual preview or master. Required checks:

1. Camera and hero framing: per-shot report minimum clipped projected vertical span per hero over every frame; not a pixel area or occlusion measurement. Target >=45% per hero, aim toward lower two-thirds. Protect faces/hair, active hands and story props with safe projected bounds, no cuts through them; two-shot face center separation >=.18 of width in current driver. Physical camera envelope (current cafe |x|<3.70, -6<y<2.30), visible opaque set, ceiling/floor not dominating. Quality still medium/wide ceiling <=10%. The corrected first preview explicitly accepted a narrower numeric exception, 30% hard fallback floor where frontal two-shot readability required it (actual ~30–37%). This is not the new benchmark: for subsequent shorts target 45%, report any miss honestly and obtain explicit approval for any exception rather than silently relaxing checks. Inspect rendered pixels for visibility.
2. Camera pre-flight (required before full animation): render one actual reduced-resolution test PNG at a representative frame for each chosen camera segment, including separate payoff cuts. Evaluate display RGB with all channels <=24 at 50% resolution and 32 Cycles samples; reject if >10% near-black, inspect for subject occlusion where possible; a failed candidate must be corrected before animation. Projected bounds alone do not detect occluders. Classroom driver implements the test, records PNG and JSON evidence, and stops the runner before animation on failure. Pre-flight darkness is a catastrophic camera-obstruction screen, not the final image quality gate: run 45894893830 had 99.937% near-black in the throw shot. In run 45902470116, actual failed PNG inspection showed ordinary dark hair, clothing and under-desk shadows with 8-sample grain, not a black obstruction (independent PNG counts 2.145%, 2.270%, 2.614%). Supervisor authorized 32 samples and 10% for pre-flight only. Final decoded RGB24 gate remains strictly <=2% on every frame, unchanged. The classroom driver also renders a Cycles object-index pass of the complete scene and an isolated silhouette pass per hero (or plane in glide), using the same camera and sampled frame. Report visible pixels, isolated projected silhouette pixels, frame shares and occluded fraction. Reject if visible/isolated <60% or isolated silhouette is empty. Preserve EXR evidence. This is sampled, not proof of all-frame visibility; preserve the independent full encoded-video gate and actual frame inspection. Record exact camera transforms for reuse.
3. Near-black: scripts/validate_story_pixels.py checks every frame of decoded final RGB24 MP4 including captions. Count pixels whose R,G,B all <=24 (8-bit); worst frame per shot must be <=2%. Report max, mean, worst frame and total frames. Do not game with a black-level clamp; fix set enclosure/lighting/camera. This metric does not detect every dark-brown void, so visual review remains mandatory.
4. Physical interaction: use scripts/stage_b_interaction.py aim_arm, key_arm, GripAttachment, GravityDrop and ExpressionTrack. Bind real wrist sockets to props, keep world transforms at release, validate support footprint and analytic flight, and verify expected state transitions at the intended frame. Existing driver attachment error <1e-5 scene units (observed zero), friend rim distance error <.16 (observed .03002), reevaluation position difference <.001, exactly one visible expression decal. New physical action needs corresponding contact/release/support validation; numerical socket agreement is not proof of visibly believable contact.
5. Payoff: prop remains attached or settles on support through end, hold long enough to read. Existing cake driver asserts >=1.5 s head attachment and reports planned payoff hold (2.5 s for approved short). Check the actual last shot at beginning/middle/end; retain the story's intended hold and visible payoff. For other gags define equivalent state/hold assertions.
6. Edit integrity: word join exactly equals narration; first/last caption frame covers entire story, successive intervals contiguous, enough frames for each word. FFprobe confirms resolution, fps, frame count, duration within .05 s, AAC audio; expected narration presence/absence and optional slot test. Cross-check all shot manifests, exact frame filenames and duration. Use decoded playback for audio/caption legibility and sync, not just assertions.

## Review and delivery loop

- Before expensive animation, inspect camera/key-pose previews if available; choose frame positions that expose each action. Render preview, then edit and run every gate. Check actual workflow result (including edit), not just render job success.
- Download the real artifact; verify archive digest when available, independently hash MP4 and probe streams/duration. Inspect the actual MP4 and extracted encoded frames, one per shot at minimum plus key action moments, including contact/release, impact, and beginning/middle/end of payoff. In the example comparison set: 1.5 notice, 4.0 first reach, 5.9 hands meet, 7.0 airborne, 8.2 impact, 10.7 payoff. For new stories choose meaningful named timestamps rather than reusing these arbitrarily. Frame times are sampled on the actual output frame grid.
- Compare visual evidence with the narration and reference grammar: no voids or unintended geometry, no patron occlusion, faces and hands readable, prop contact visible, payoff unmistakable. Identify concrete defects with timestamp; correct only necessary geometry, lighting, drivers, camera, edit; rerender/re-edit and repeat validation. If CI fails, retrieve logs, fix root cause, rerun and document failed run IDs, not just successes. If tool/runtime limits prevent completion, report exactly which jobs/artifacts exist and what's pending; do not substitute older or synthetic media.
- Attach the actual MP4 and actual frame grabs in the chat when environment supports files, plus ZIP/source package link, run ID, artifact name/ID, render commit, final HEAD, SHA-256 of MP4/archive and actual profile/fps/samples. Verify paths before linking. Update docs/PROJECT_STATE.md and story-specific evidence with numerical results, visual shortcomings and user verdict. Do not claim viewing motion/audio unless actually inspected; if only frames/metadata available disclose that. Never approve your own output in place of user.

## Verified baseline and limitations

Short #1 The Last Slice corrected preview: supervisor APPROVED preview-complete. [Run 45880102202](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45880102202), render commit 9edaa643a6ea10a797d072861967d79f6ccabb98, [artifact 15147751306](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45880102202/artifacts/15147751306), roblox-the-last-slice-corrected-preview-12s. MP4 SHA-256 8948e8e23d0af97de8226029d3c9a0e0d296667c67794f70dd75f807d3009679. Archive SHA-256 db0de4ad2f9f87b266d338065c000408f616ca6ce6ac863822bdf78d6039c90c. 12s, 144 frames; worst near-black by shot .857808%, .798732%, .899101%, .888551%; attachment error zero; launch 80/landing 92; payoff hold 2.5s. Approved visually after targeted correction, not after numerical validation alone. Earlier rejected build is historical, not the production baseline.

Known gaps: preview grain at 24 samples; approved frontal two-shots ~30–37% character span versus >=45% goal and reference lower-two-thirds composition; airborne cake slightly cropped at 7.0s; analytical upright/tilted prop flight and socket constraints, not full rigid-body collision simulation or IK; no general lip sync, no universal automatic script-to-shot conversion, only one dressed café location proven for production. Full profile unproven. New locations, props and story actions require actual implementation and verification. These limitations must not be hidden or treated as authorization to regress further.

Next milestone: supervisor approval of the exact supplied R6 rig stills, then separately migrate and verify the story renderers. Both existing previews are frozen; no new short render is authorized.
