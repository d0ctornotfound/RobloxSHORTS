# Integrated Last Slice — short #1

Port of unchanged stories/the_last_slice.json, timing, action and narration text. Quality character and café modules replace Stage A assets. Retargeted actor roots, shoulder length, plate rim offset, friend reach, actual highest hair mesh vertex for head contact. Existing GripAttachment, GravityDrop, ExpressionTrack and editor retained. Static seated patrons, matte hair, fitted knitted wrap, corrected yellow and no legacy window crossbars. Camera retarget uses horizontal sensor fit, per-frame per-hero clipped vertical projected bounds (not pixel area). Minimum .45 required. Preview 432×768, 12 fps, 24 Cycles samples, adaptive threshold .065; FFmpeg hqdn3d before captions (OIDN unavailable on CI). Full 1080×1920, 24fps, 96 samples. No voice audio supplied; optional narration WAV remains.

CI completed; see final evidence below. Local: `blender -b --python-exit-code 1 --python scripts/render_story.py -- --profile preview --output render/story` then `python3 scripts/edit_story.py --profile preview --frames render/story --output render/final --verify-slot`.

First CI [45875679636](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45875679636) failed the frontal notice framing gate (lead 35.19%, friend 30.64%). Replaced frontal blocking with tested oblique long-lens candidates and orthographic fallback; every animated frame is checked for protected subject bounds, hero vertical coverage and face separation. Side cutaways preserve lighting/shadow rays.

Second CI run 45876003484 passed all four framing gates (notice 46.49%/48.21%, reach 53.93%/47.22%, impact 66.80%, payoff 45.90%/47.13%) but failed manifest JSON because the camera sampling list shadowed the integer render sample count. Renamed the list; retry recorded below.

Third run 45876246444 successfully serialized complete 144-frame manifest and passed all interaction/coverage gates (zero binding error, 0.03002 friend rim error, support z 2.91408, launch 80, landing 92, payoff 2.5 s). A camera angle variable shadowed CLI args before rendering; renamed it to theta.


## Integration production complete — short #1

Run [45876531786](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45876531786) completed successfully on render commit `120f93f17d1538d8548a1d31ce4d66e23ce03205`. All four render jobs (140104900984, 140104901666, 140104901445, 140104901520) and edit job 140110482776 succeeded. Final artifact [roblox-the-last-slice-integrated-preview-12s](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45876531786/artifacts/15146306456), ID 15146306456, 20,841,572 bytes. Archive SHA-256 `5df16b94a57904e2d8a0fe8c30427432fe55dfa5528ce9099c2acf20fc5fb801`; independently downloaded and matched. MP4 SHA-256 `62841de992e3b7a7dc1f8b897fd34fba2a8ed686d5039511042d39dd4062369c`, 1,760,225 bytes. Independent ffprobe: H.264 432×768, 12 fps, 144 frames, 12.000 s; mono AAC 48 kHz, 12.000 s. 24 Cycles samples, FFmpeg hqdn3d, 26 burned-in words, original procedural music and four SFX; narration absent, optional slot tested successfully. Four MP4-derived frame grabs packaged at 1.5, 5.9, 8.2 and 10.7 s.

Final manifest: minimum projected vertical hero coverage lead/friend notice 46.49%/48.21%, reach 53.93%/47.22%, impact 66.80% lead, payoff 45.90%/47.13%. Zero attachment error; friend rim error .03002; launch frame 80, landing frame 92, hair support 2.91408, payoff 2.5 s. Geometry checks are not image segmentation or proof of visible contact. Actual frame-grab inspection shows improved cast and fabric, but prominent cutaway/set edges and dark voids, foreground patron/arm occlusion in reach and impact, and cake balanced on a high hair tip so it reads as perched/floating. Orthographic reach and oblique views are visibly compromised. Some grain persists and window view is not clearly established in these grabs. Production-complete, visual approval pending, not a benchmark-quality claim. Original Stage C is superseded for production by this integrated short; no short #2 work initiated.


## Supervisor correction pass
Prior video NOT APPROVED: dark set edges, patron occlusion, cake missing in payoff, cluttered reach. Restored opaque expanded enclosure and neutral bounce; frontal perspective cameras inside set; protect hands, faces, and cake; hide patrons after notice; lower cake into crown (2.64) with tilt and broad side facing viewer. Coverage goal 45% retained, frontal readable two-shot may trade full projected body span (hard floor 30%, explicitly reported) to protect faces/active hands. New decoded MP4 pixel gate: all frames, near-black max RGB channel <=24/255, including captions, maximum 2% per shot. No black-level clamp. Six requested comparison grabs. CI completed; see correction evidence below. Previous artifact not approved.


### Correction pass — completed evidence

Run [45880102202](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45880102202) succeeded, all five jobs. Render commit 9edaa643a6ea10a797d072861967d79f6ccabb98. Artifact [roblox-the-last-slice-corrected-preview-12s](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45880102202/artifacts/15147751306), ID 15147751306, 22,479,321 bytes. Archive SHA-256 db0de4ad2f9f87b266d338065c000408f616ca6ce6ac863822bdf78d6039c90c, independently downloaded and matched. MP4 SHA-256 8948e8e23d0af97de8226029d3c9a0e0d296667c67794f70dd75f807d3009679, 1,739,459 bytes. ffprobe independently confirmed H.264 432x768, 12 fps, 144 frames, 12.000 s, AAC mono 48kHz. 24 Cycles samples, unchanged music/SFX/captions and no narration; narration slot tested.

All 144 final decoded frames independently checked, identical to pixel_validation.json. Max-channel RGB <=24/255 including caption outlines. Worst-frame percentages:

| Shot | Rejected original | Corrected maximum | Corrected mean | Worst frame |
|---|---:|---:|---:|---:|
| Notice | 4.304% | 0.857808% | 0.774951% | 28 |
| Reach | 10.549% | 0.798732% | 0.513220% | 67 |
| Impact | 1.884% | 0.899101% | 0.804057% | 93 |
| Payoff | 4.409% | 0.888551% | 0.546302% | 133 |

All pass <=2%. No black clamp. Six final MP4-derived grabs at 1.5, 4.0, 5.9, 7.0, 8.2, 10.7 s packaged and inspected. Frontal cameras show enclosed café with no large dark set-edge void; patrons only in notice (still intrude at left/right edges in that shot), no patron occlusion in reach/impact/payoff. At 5.9s both hands/arms and plate read clearly. Cake visible in crown at 8.2 and 10.7, base lowered .274082 below highest tip, attachment remains active throughout hold. Actual launch/land frames 80/92, zero attachment error, friend rim error .030018, hold 2.5s.

Remaining limitations: frontal two-shot coverage regressed below prior 45% target, notice lead/friend 34.85%/30.09%, reach 35.47%/30.62%, payoff 36.75%/31.76%, impact lead 66.20%. This is a deliberate tradeoff for frontal readable composition but is NOT a claim that earlier 45% gate passes. Reach remains wide rather than tight medium, foreground rug and upper wall consume substantial space. Notice patrons overlap the outer actor arms at frame edges. Airborne cake partly clipped at right edge at 7.0s, cake contact still stylized; payoff cake visible but small. Lighting is brighter and grain persists. Dark pixel gate alone does not prove visual quality. Correction production complete, awaiting supervisor approval; previous integrated artifact rejected, no short #2 started.
