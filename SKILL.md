---
name: roblox-shorts
description: End-to-end production manual for original R6 animated stories, reusable characters, poses, props, sets, atmosphere, effects and GitHub-rendered video.
---

# Roblox story production manual

Read this file before creating any story. Use the [reference benchmark](docs/REFERENCE_BENCHMARK.md) and [current project state](docs/PROJECT_STATE.md). The historical prototype instructions are archived in [HISTORICAL_SKILL.md](docs/HISTORICAL_SKILL.md). This repository supplies executable Blender Python modules and an isolated showcase workflow, not an auto-installed ChatGPT skill or a universal text-to-video engine. Start a new chat, connect/authorize this repository, explicitly point the agent at SKILL.md, and use authorized standard CPU GitHub Actions (check billing/quotas). No external assets, paid image/audio/video services or voice generation without permission. Never fabricate renders, tool results or completion.

**Approval protocol:** show every review still and actual MP4 in chat, with direct file attachments; archives are supplementary. Inspect the rendered pixels yourself, list defects, request user approval. The two proof shorts are frozen during library approval; do not trigger or modify their drivers/workflows. Their prior success is historical evidence, not proof that new variants or library actions work in them.

## 1. Characters — identity on the source rig

The exact CC BY 4.0 [source GLB](assets/r6_rigged.glb), attribution in assets/R6_ATTRIBUTION.md, SHA-256 3a0f310faf09cf161f7036a4c0df1a20202b967683700badc4440309c0a7d95a, is authoritative. Two skinned meshes, one armature; native height 5.10125, 1.2 cube head, torso 2 wide × 2 tall × 1 deep, head/torso width 0.59892448. Uniform scale to 2.28 scene units; no body reshaping or skin-weight changes. Rigid R6 limbs, matte plastic, tiny bevels. Actor coordinates +X right, -Y forward, +Z up. Bones _rootJoint, Torso_00, Head_01, Left Arm_02, Right Arm_03, Left Leg_04, Right Leg_05 plus end joints. API uses arm/leg index 0 right, 1 left. Use real bone sockets, not mesh transforms.

Source: [r6_character.py](scripts/r6_character.py), [r6_variant_character.py](scripts/r6_variant_character.py), [r6_variant_textures.py](scripts/r6_variant_textures.py), [library_character.py](scripts/library_character.py), [library_character_assets.py](scripts/library_character_assets.py). Generate textures with system Python/Pillow/NumPy before invoking Blender:

~~~sh
/usr/bin/python3 scripts/library_character_assets.py
~~~

Lead: grey textured hoodie, dark jeans, saturated red star, dark tapered spiky strand hair, smug toothy face. Friend: clean cream tee, golden yellow textured denim (deepened RGB 244,164,2), ribbed slouched folded-brim knit hat, comic laughing face. Teacher: deep rose knit cardigan, raised collar/placket/buttons, dark textured trousers, swept strand hair and rounded bun, fine glasses/clear lens, mature unimpressed face. Dad: beige jacket over black shirt, pocket/buttons, black striped trousers, swept hair, stubble, worried brows. Four default skin options honey/warm_tan/peach/dad_tan; head/arms matte. Nine 1024² RGBA expressions neutral/happy/smug/tired/worried/laughing/shocked/sad/unimpressed; independent stubble/beard overlays supported by VariantCharacter. Distinct face artwork for all four roles. Role-sleeve texture includes hand color: regenerate sleeve when skin changes. Garment atlas panels are front/back/side/cap, preserve rest UV and skinned body. These are illustrated original textures, not photographic garments. Flat fallback only for distant extras.

### Worked new role: librarian

A role is an identity recipe; name is a unique instance ID. Add a role entry to RECIPES in library_character.py, choose skin, torso, leg, face-set folder and hair style. Generate nine transparent PNGs under assets/r6_variants/ROLE_FACE and matching ROLE_sleeve.png via library_character_assets.py. The example librarian has freckled mature faces, cardigan, blue denim and swept dark hair. Existing palette/atlas names can be reused; to author a garment add COLORS and panel drawing in r6_variant_textures.py. To author facial hair use independent face-plane overlay parented to Head_01 as in VariantCharacter; custom RecipeCharacter currently supports hair/outfit/face/skin recipe, not automatic facial hair selection. For unique accessory shape extend _accessories with attach_mesh; ensure original body and all sockets unchanged. Instantiate in Blender with scripts on sys.path:

~~~python
from library_character import character
from library_animation import pose, grip
from library_props import build
a = character("library keeper 01", "librarian")
pose(a, "hold_left", .5, (-1.3,0,0))
a.pose("happy")
book = build("book", scale=.82)
attachment, error = grip(a, book, "left", frame=1)
~~~

Check original geometry ratio, two skinned meshes, rest→pose→reset vertex error <1e-5, actual grip translation error <1e-5, hair/face following head bone. Render full body and medium portrait under story lighting. Use expression swaps per beat; do not lip-sync rigid face decals.

## 2. Animation library — reusable bone actions

Source [library_animation.py](scripts/library_animation.py). parameters(action,t,side) returns explicit arm/leg directions (actor axes), head/torso Euler radians, root pitch, optional seat support. pose(actor,action,t,position,yaw,frame,side) applies absolute pose, grounds evaluated skin to support, keys real bone rotations and root transforms if frame provided. t is normalized action phase, cyclic actions accept repeated phases. Default arms/legs (0,0,-1), head/torso (0,0,0). Use at least 12fps for production and interpolate/sample per frame. Full exact parameters are in the Python function and rendered JSON manifests.

| Action | Non-default parameters (directions/Euler radians) |
|---|---|
| idle | arms (±.025,-.04,-1); head .025 sin(2πt) pitch/yaw |
| walk | q=.50 sin(2πt); opposite arms (0,±sin q,-cos q), legs counterphase; torso pitch .04 |
| run | q=.80 sin(2πt); torso pitch .14; same counterphase |
| sit | leg direction (0,-1,0); arms (±.08,-.35,-.92); seat .62 |
| stand_up | angle=(1-smoothstep(t))π/2, leg (0,-sin angle,-cos angle), seat .62(1-smoothstep(t)) |
| reach | selected arm (.06,-.88,-.47), head pitch .12 |
| throw | arm interpolates (.14,.72,.62)→(.14,-.93,-.22), torso yaw .12→-.12 |
| wave | selected arm (.35+.20 sin(2πt),-.10,.90); head yaw -.10 |
| point | selected arm (.05,-.99,.06); head yaw .08 |
| hug | both arms (±.30,-.91,.12), head pitch .08; stage pair facing |
| high_five | selected arm (.25,-.58,.77); solve both arms to one reachable world point |
| fall | root pitch -1.38 smoothstep(t), arms (±.45,-.55,.65), asymmetric legs |
| sleep | root pitch π/2, arms (±.10,0,-1); supply mattress support height |
| eat | arm (.40,-.87,.23), head pitch .10 |
| drink | arm (.33,-.87,.36), head pitch -.10 |
| hold_left | left arm (.06,-.58,-.81), real left socket |
| hold_right | right arm (.06,-.58,-.81), real right socket |
| hold_both | arms (±.38,-.73,-.56); midpoint and span from both sockets |

Use pose with unique frame key for each sample, or walk_path(actor,start,end,first,last,fps,cycle_seconds,run=False) for straight locomotion. For a reachable contact, aim_at returns measured residual; solve intersection of shoulder reach spheres for high-five, or plane/rim intersection for a seated plate. Use GripAttachment bind/release (stage_b_interaction.py) and analytic ballistic flight, then settle or bind to support. grip left/right returns attachment and error. dual_grip places a bar-like prop between two actual sockets; size local X endpoints to returned half-span. It is a static contact helper: update midpoint/orientation each moving sample, not a universal two-hand constraint. No IK, elbow/knee animation, collision solving, genuine mouth ingestion or foot lock; sit/stand/fall/sleep need specific chair/bed calibration, pair poses need collision review. A pose strip proves a pose, not full action timing or physics. The approved imported Walk/Sprint cycles supersede procedural locomotion for new stories; the procedural walk/run poses are fallback examples, not the authentic gait. Showcase clip uses imported Walk.

### Imported authentic-data locomotion (approval pending)

The user supplied [run_walk_roblox.bin](assets/animations/run_walk_roblox.bin), RBXM KeyframeSequences Walk (50 keys, 0–.8166666627s) and Sprint (35 keys, 0–.5666666627s), both Loop=true and ~60Hz. Source attribution and SHA in [SOURCE.md](assets/animations/SOURCE.md); embedded credit godofsun95, not an official Roblox animation claim. Parser [rbxm_animation.py](scripts/rbxm_animation.py) reads original binary/LZ4 chunks, instances/references, parent tree, interleaved numeric arrays, compact/explicit CFrames, timestamps and Motor6D C0/C1. It rejects unknown supported animation encodings, non-linear easing or incomplete pose hierarchies instead of inventing motion. Original CFrames and endpoint differences retained. RootPart weight is zero; source is in-place locomotion.

[r6_imported_cycles.py](scripts/r6_imported_cycles.py) maps source Torso, Head, Left/Right Arm and Leg to the exact target bone names. For each bone, source neutral joint axes from C0/C1 are rotated into actor space (+X Roblox right to -X actor right, +Y to +Z, -Z to -Y) then conjugated into evaluated GLB rest bone axes; source pose translations are mapped and uniformly scaled, rather than dropped. Preserves target joint pivots and original skin weights; not an exact source mesh clone. Source timing kept in named 60Hz Blender Actions walk_cycle and run_cycle, fake-user and CYCLES modifiers; original end key retained. No manually authored gait is substituted. For arbitrary fps, use Retarget.at(name,source_seconds,loop=True), which samples original intervals and slerps quaternions. Use loop=False to inspect exact last key. Walk max seam 2.153°/0.02484 studs; Sprint max seam 1.519°/0.03256 studs; do not erase those source differences. For a seamless production loop, use an explicitly documented short overlap/blend at edit or action level, never modify the preserved master.

~~~python
from library_character import character
from r6_imported_cycles import Retarget
a=character("walk hero","lead")
ret=Retarget(a)
actions=ret.actions()  # named reusable Blender Actions, source 60Hz
cal=ret.calibrate("walk_cycle")
# In a story, evaluate at (frame-first)/fps * playback_rate:
ret.at("walk_cycle", seconds * playback_rate)
# Set a.root position/yaw along desired path after pose evaluation.
# Root distance = cal["speed_scene_units_per_second"] * playback_rate * seconds.
~~~

Calibration samples evaluated sole points at original timestamps; median backward stance-foot velocity estimates root speed, stride = speed × cycle duration. Scale speed and phase by the same factor to avoid obvious foot sliding, trim at full cycles or use a timed blend when transitioning to idle. No exact foot-lock IK or authored forward root track; report estimated stance slip and any per-frame ground correction. For 60Hz action playback at other scene fps retime via NLA or direct sampler; don't assume 60Hz frame numbers match 12fps. Imported workflow [imported-cycles.yml](.github/workflows/imported-cycles.yml) only renders walk/run pose strips, packed named-action Blender scene and four-second street proof clip. Run 45920470758 completed 6/6 jobs; artifact 15164113448. Round-trip all 510 body poses passed (max matrix element residual 1.75834e-6, translation 1.21287e-7 source studs); verified actual Action samples, 42 curves each, frames 1–50 and 1–35 at 60Hz. Native speed estimates Walk 3.399, Sprint 7.752 scene units/s, but stance slip RMS 2.425/5.362 units/s respectively: not exact foot locking. Actual clip slows source and travel together to .6009, 8 units/47 intervals. The imported proof has minimum coverage 28.3%, near-black 2.84% (>2% gate) and stray red accessory near feet; conversion proven, presentation not production-approved. See [production evidence](docs/PRODUCTION_LIBRARY.md). Show actual media in chat. Until supervisor approves imported motion, older hand-authored walk/run remain only historical library demonstrations, not equivalent motion.

## 3. Props — modular catalogue

Source [library_props.py](scripts/library_props.py). build(kind,name=None,pos=(0,0,0),scale=1,p=None,**params) returns an empty root, child meshes authored locally; root is the base/support origin, parent props and key transforms on it. palette() returns shared original wood/cream/metal/glass/leaf/red/blue etc materials; supply a shared palette to reuse materials. For table/desk width,depth,height; bed width,depth; door/window width,height (window pane=False for open aperture); bookshelf width,height. All accept uniform scale; other specific designs have default proportions. Use contact height, grip offset and support footprint measured from evaluated meshes, not catalogue display scale.

| Group | Available builders |
|---|---|
| Furniture | table, chair, desk, bed, lamp, bookshelf |
| Architecture | door, window |
| Exterior | tree, plant, car |
| Food and tableware | cake, food (burger), plate, cup |
| Handheld | book, phone, paper_plane, umbrella, ball, gift_box |

Door panel and window frame are separate roots; for hinge motion place pivot on edge, parent door root under pivot and rotate. Car is stylized static body/wheels, not a vehicle dynamics rig. Glass is stylized opaque color except expressly transparent face lenses. Umbrella is simplified conical canopy. Catalogue displays normalized scales, not production scale. For new prop build local geometry with cube/cylinder/sphere, define base origin and size, verify nonzero evaluated bounds, render from three-quarter camera, test contact in actual scene.

## 4. Locations — construction and dressing

Source [library_sets.py](scripts/library_sets.py). wall_sections(name,y,width,height,wall,openings) cuts wall panels around apertures given (x,width,bottom,height); room(name,width,depth,height,window=(x,width,height),door=(x,width,height),front=False) builds plank floor, rear/side walls, trim, real openings and window/door kit. Camera inside open front or opaque room; never remove walls in camera rays to disguise voids. Add a ceiling if the shot sees overhead. Windows need actual exterior backing/sky and motivated light. Place furniture, dress surfaces with story props, repeat accents, preserve walking clearance and camera sightlines. Modular cafe() and classroom() are refactored **parallel examples**, not replacements for the approved historical sets (frozen proof shorts retain quality_cafe.py and classroom_set.py). street() builds a residential exterior with modular wall panels, house façades/doors/windows, planted front lawns, sidewalk joints, road markings, parked car, trees and lamps; returns window surfaces for atmosphere lighting. New location proof is the street. Use measured support plane for character placement. Add location-specific textures, trim, wall/door geometry and furniture before hero framing.

## 5. Atmosphere — time and weather

Source [library_atmosphere.py](scripts/library_atmosphere.py). Atmosphere(scene,windows=(),target=(0,0,1.2)); apply(preset,other=None,mix=0,frame=None) blends sun direction/color/energy, world RGB/strength and exposure, changes motivated fill and window emission. At night visible moon disc and seeded stars, cooler sky and warm lit windows. Values are art-directed linear RGB, not astronomical positions. Night uses moon-light direction; world color and strength also determine visible background. Transition per sampled frame; use mix from 0 to 1; moon/stars switch at night weight .48. Set window material emission through kit and inspect actual image. Overcast/rain lighting presets don't automatically create precipitation; call effects.

| Preset | Elevation / azimuth ° | Light RGB / energy | World RGB / strength | Exposure |
|---|---|---|---|---:|
| morning | 25 / -45 | (1,.78,.53) / 2.0 | (.46,.67,.91) / .42 | 0 |
| midday | 62 / -35 | (1,.95,.82) / 2.8 | (.38,.65,.94) / .48 | 0 |
| golden_hour | 12 / -60 | (1,.49,.20) / 2.5 | (.83,.42,.23) / .34 | .10 |
| dusk | 4 / -70 | (.75,.40,.40) / .55 | (.21,.26,.48) / .28 | .10 |
| night | 32 / 40 | (.34,.49,1) / .38 | (.035,.075,.22) / .25 | .25 |
| overcast | 55 / -35 | (.82,.90,1) / .35 | (.46,.53,.62) / .65 | 0 |
| rain | 38 / -35 | (.67,.78,1) / .22 | (.25,.34,.49) / .45 | .05 |

Keep faces readable at night, no black-level clamp. Frame the moon against unobstructed sky; stars are scene objects not a physical sky dome.

## 6. Effects — deterministic meshes and camera movement

Source [library_effects.py](scripts/library_effects.py). particles(kind,center,extent,count,seed) creates mesh particles in local box; update(effect,time,frame=None) wraps vertical coordinates, adds seeded lateral sway, optionally keys each sample. Rain streaks 4.7 units/s, snow .50, confetti .70, sparkles .12, dust .08. Rain uses thin tilted geometry; snow/sparkles/dust tiny spheres, confetti colored flat rectangles. These are geometric overlays, not fluids, snow accumulation or physics particles. Clip particles to camera/set and avoid crossing faces; rain should not appear indoors. shake(camera,base,time,amplitude=.025,frequency=17,frame=None) adds bounded sinusoidal XY-plane lateral/Z translation; aim original camera first, adjust framing margins, never shake through walls. A still demonstrates displacement only, not perceived motion; render actual moving sequence before using as final. Camera shake demo is relative to base camera, not a blur simulation.

## 7. Story — narration-first two-minute production

Target 105–135 seconds, roughly 210–330 spoken words (adjust for approved read timing); hook in 0–3 seconds, recognizable visual premise, concrete escalating consequences, early detail recalled in final payoff. Scene changes when story changes location, shot changes every 1–3 seconds. Medium dominant, close for reactions, wides to establish, inserts for props, keep lower two-thirds hero occupation. Exact first-person narration, visible action synchronized to each clause, no long static narration over unrelated visuals. Plan 40–100 shots depending on duration. Example [library_story_plan.json](examples/library_story_plan.json) is a 120s planning example, **not a produced long-form film**. Validate with python3 scripts/library_story_plan.py examples/library_story_plan.json. Fields: id,duration,fps,hook_end,narration,callbacks[{setup,payoff,detail}], shots[{start,end,location,camera,action,narration_beat,characters,props}]. Shot intervals contiguous, 1–3s each, exact narration token join, supported shot types wide/medium/close/insert. Callback time order verified; semantic quality is a human review. Props/locations in a story plan are requests to implement, not automatically available assets (e.g. shadow effect, clock and house interior require new builders).

Production order:
1. Write narration, estimate read length, get user premise/script approval. Mark hook, escalating beats, location changes and payoff callback. No voice generation until authorized; user can supply narration WAV.
2. Break into timed storyboard; choose actual character/prop/location/action/atmosphere APIs. List missing assets explicitly and build/test them, not placeholders. Map exact words to visual beats. Use planned 1–3s cuts, retain continuous prop/character state across shot boundaries.
3. Build a dedicated story timeline driver (existing render_story.py and render_classroom.py are story-specific, frozen). Story JSON example [the_last_slice.json](stories/the_last_slice.json) documents legacy exact captions, expressions, head_turns, action times, shots and props. It is not a universal schema. Adapt/reuse common library, not hard-coded cake/paper-plane logic. Preserve old workflows until authorized.
4. Render camera/key-pose preflight, then chunk animation on standard CPU CI. Budget preview 432×768,12fps,24 samples (120s =1440 frames); full 1080×1920,24fps,96 samples (2880 frames), unproven whole-short full profile; test 1–3s chunk, multiply measured seconds/frame, parallelize by shot/chunk, reuse unchanged archives. Do not assume quota/free. Showcase proof is deliberately lower quality 360×640,12fps,16 samples,12s; not a production profile. Plan camera path, keep safe bounds and rendered visibility. Avoid expensive unnecessary renders.
5. Edit with existing scripts/edit_story.py --story PATH --profile preview --frames DIR --output DIR --verify-slot, optional --narration approved.wav, exact captions/music/SFX; verify expected frame count and filenames. Existing editor is short-specific; inspect/extend for long-form timing rather than assuming arbitrary duration or voice alignment. No paid narration. Built-in fixed music reduction is not sidechain mastering. Listen/measure LUFS separately. For story final require exact narration/caption join, H264/AAC duration/probe and all validation gates.
6. Validate actual rendered frames: target >=45% projected hero vertical span (previous approved exceptions ~30–37% not new standard); face/hands/prop safe, no occlusion, representative object-ID visibility >=69%, 32-sample preflight darkness <=10%, final decoded RGB max channel <=24 pixels <=2% per frame; check physical socket error <1e-5, release continuity, support and hold (>=1.5s meaningful payoff), exact caption join. Numerical coverage is not actual visible area. Use scripts/camera_visibility.py and scripts/validate_story_pixels.py. View actual frames and playback; identify concrete defects, rerender only changed chunks and re-edit; show every review still/MP4 directly in chat. Record commit, run IDs, artifact ID, hashes, actual samples/resolution/fps, failures and user verdict. Never mark approved on your own.

## 8. Isolated library showcase — reproduce and review

Workflow [.github/workflows/library-showcase.yml](.github/workflows/library-showcase.yml) only watches library code/showcase paths, runs standard Ubuntu Blender CPU. It does not render either proof short. Manual dispatch renders the complete matrix and packages verified files. The one-time completion workflow reuses unchanged pose/prop/character evidence from run 45919353390 and renders the modified shared-set jobs; do not rely on expiring prior archives for future full builds. For local debugging in Blender:

~~~sh
/usr/bin/python3 scripts/library_character_assets.py
blender -b --python-exit-code 1 --python scripts/render_library_showcase.py -- --job characters --output render/showcase
# Repeat jobs: poses0..2, props0..2, rooms, sky0..1, effects, clip0..5, import_walk, import_run.
# Download CI job artifacts under chunks/library-<job>/ before packaging:
python3 scripts/package_library_showcase.py
~~~

The package contains actual rendered character example, three pose strips (18 actions), three prop catalogue rows (21 types), modular café/classroom, all seven atmosphere stills on one street, all six effects frames, day→night walk MP4, encoded grabs and manifest. Contact sheets combine actual images, no generated mockups. This is a silent library proof, not a captioned story. Validate original GLB hash, bone displacement/reset, grip and high-five residual, bounds and per-frame ground support, unique actions/props, continuous 144-frame clip, day/night endpoint, file SHA-256, long-form plan. Report near-black gate including failure, not silently relax for atmosphere. Visual review of feet, clothing, props, moon visibility, and walk continuity remains required. Package success is not user approval. Completed library run 45919789293, artifact 15164132181; 18 pose and 21 prop proofs and 120s plan validated, 12s FK walk/transition clip is historical and not imported RBXM. Night maximum 5.25% near-black fails production gate; visual limitations in [PRODUCTION_LIBRARY.md](docs/PRODUCTION_LIBRARY.md).

Prior approved character base and lead/dad/friend/teacher variants: runs 45910965865,45915369587,45917281074; friend trousers deepened during library pass. Café armature-only port run 45912247014 passed, but variant rerender had not started; classroom port still frozen. Existing proof shorts are not updated by this sprint. Known limitations: procedural textures, rigid FK, no automatic story compiler, preview grain, no fully verified long-form or full profile. The next milestone is supervisor library approval, then explicitly authorized proof short integration. 


### Supervisor-approved locomotion and final showcase
Imported Walk and Sprint retargeting approved (run 45920470758, artifact 15164113448). Source credit godofsun95, license not established; see assets/R6_ATTRIBUTION.md and assets/animations/SOURCE.md. Remove redundant red pin backing slab in VariantCharacter, keep chest star; final showcase asserts star height is within evaluated torso bounds on every frame. The final street showcase uses Retarget.at('walk_cycle',seconds*rate), original timing and stride calibration, 20 scene units over 143/12 seconds, 144 frames, 360×640, 12 fps, 16 samples. Six independent frame chunks, native source cycle sampled without modifying endpoints. No procedural gait in the clip. Prior approval stills from run 45919789293 are retained as library evidence; final imported walk/run strips are regenerated after backing removal. Production gates remain unchanged; demo coverage/darkness reported separately. No proof short rerender until library approval.
