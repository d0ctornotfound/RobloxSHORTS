# Saying Hi — supervisor review: PARTIAL / NOT APPROVED

Scope: additive branch only, Chapters 1–4 locked, no full-film render or paid voice generation. Script and reference times are stored verbatim. No production media is claimed complete.

## Planning deliverables
- Exact script: stories/saying_hi_script.txt
- Proposed 20-person roster: stories/saying_hi_cast.json. The original order's additional counts conflict with 10 girls and 10 boys: June + nine girls; narrator + Otis + three popular boys + five additional boys. Otis is one of the six remaining wall boys. Brody is specified as uniformly 0.84 scale; actual stature and contact recalibration are not measured.
- Persistent square/chart marks: stories/saying_hi_staging.json. All 10 initial arrows and the final 20-link design encoded in data; June→Kai and narrator→June explicitly present. This is a design-level count, not inspection of rendered arrows.
- 48-sentence plan: stories/saying_hi_plan.json; reference timeline 101.20 s. No narration words altered. Otis authors both charts; the replacement visibly supersedes the first in the planned action. Interview acts have distinct action descriptions; 6–9 montage still needs actual internal cut times.
- Validator, temporary eSpeak NG retimer and held-still animatic command added. Strict validator does not accept null actual audio bounds unless --draft is explicitly passed.
- Candidate chart drawing, square builder and prop/contact/dog helpers added. No Blender execution or approved actor creation demonstrated.
- External scenery: repo AdityapalW/Roblox-skill is accessible; README and root listing read. Itlay/Itlay.gltf exists (22,608,734 bytes, Git blob 20108af3a19fae6b5beaa5fac2e3305b56112a41). README mentions procedural geometry and selected Poly Haven CC0 textures, but root has no license for the map itself. No external map downloaded or imported. Candidate original square uses existing kit. Verify reuse terms if changing this choice.

## Required proof measurements — not measured
| Proof | Reference timing | Missing evidence / proposed fix |
|---|---|---|
| A Chart reveal | 6.78–16.76 | Design count 10 only; render same overhead with real identity portraits and Otis's visible hand, time actual arrow drawing, verify 10 distinct visible endpoints and Me row. |
| B Crossing | 47.40–53.40 | No grip gap, clipping or stride samples; implement two-hand carrying via locked socket/adapters; calibrate StrideLock path to actual TTS; sample sole stance drift; render real eye-covering action separately. |
| C June | 69.60–75.12 | No rendered eyeline, face or pencil shake; inspect camera framing, use locked expression/blink and head/torso reactions, test grip and visibility. |
| D Greeting and payoff | 89.46–101.20 | No seat or foot gap, sliding or dog ground/contact measurements. Calibrate seat with approved sit adapter, shift June without visible float, render original dog and roll, confirm empty wall and replacement chart. |
| Cast and square | 0–101.20 | Look recipes are design specifications only; no actor factory or lineup, no rendered group shot. Create new opt-in custom looks using locked builders without editing them. Check phone-size differentiation, cast scale, north approach clearance, support plane and camera. |
| Animatic | entire story | Exporter currently accepts actual held stills only; missing all actual stills. Add real-motion clip ingestion for Otis's beat, ensure audio coverage, label ANIMATIC. No final MP4. |

## Review limitations
- Planned staging states and camera descriptions are not evaluated spatial continuity or visibility. Fixed wide portrait framing of the whole class could make actors too small; inspect and adjust the camera, not the cast identity.
- No physical contact numbers, render frame counts, EEVEE samples or encoded rates exist for proof clips. Requested 30/30 motion-proof sampling is a target only.
- Existing approved R6 limitations remain (sit speckling, rigid limbs and some shading); no new visual defects can be attributed to footage that does not exist.
- Temporary TTS sentence-chunk lengths include voice padding; actual retiming must be checked before any proof shot. Final narration is not approved.
- Workflow is a planning verification only, not the requested full motion-proof pipeline. Supervisor must not authorize final film on this evidence.

Planning verification results, if successful, are published by the branch-only workflow as explicit files under assets/saying_hi_review/. No further visual approval is implied.


## Continuation — supervisor-authorized Itlay set

The supervisor authorized the public scenery library and specifically directed use of the Italy plaza. This supersedes the earlier no-import decision. Source: [AdityapalW/Roblox-skill](https://github.com/AdityapalW/Roblox-skill), pinned commit `54b34ba1be2e3013a9de59e40db288d8f2ebda53`. Requested import is exactly `Itlay/Itlay.gltf`, git blob `20108af3a19fae6b5beaa5fac2e3305b56112a41` (22,608,734 bytes). The source `Itlay/manifest.json` describes an approximate procedural environment, no cast, Town camera target (0, 2.9, 1) in source coordinates. The source README identifies selected CC0 Poly Haven photo textures alongside procedural geometry/textures; individual texture names/URLs are not supplied by the manifest. No other set, Studio project, separate prop, or external dog is imported. Supervisor authorization is recorded; it is not a claim that the entire repository is CC0.

`scripts/saying_hi_square.py` now imports the pinned glTF using Blender's native axis conversion, preserves its material assignments and adds the story-local support platform, well, tally wall and seats. GitHub workflow validates the source git blob before importing. Imported object counts, camera placement, ground alignment and actual group image are pending smoke evidence. The prior original-only square is superseded.

New cast implementation `scripts/saying_hi_cast.py` constructs all 20 fixed IDs on the locked R6 rig, reuses Chapter 3 shell helpers, Chapter 4 hair geometry/texture helpers and Chapter 2 expression/blink system, and adds story-local shape/accessory/texture recipes. New looks, Brody's uniform scale, face framing, hair shapes, skirt/dress approximations (trousers used in current candidate) and support heights are not yet approved. The approved library files are not edited. `scripts/render_saying_hi_smoke.py` renders lineup rows and one imported-square group smoke. The standing/seated look and support geometry are under test; no contact measurements reported as passed.

### Confirmed prior planning run

Run 46101638425 succeeded. Actual audio validation: 48 sentences, 48 shots, 443 words, temporary narration 149.11315192743766 s. Deliberate failure: `SHOT PLAN FAIL: sh01: verbatim narration mismatch`, exit code 1. Actual repository evidence under `assets/saying_hi_review/`: `actual_audio_validation.json`, `draft_validation.json`, `deliberate_failure.log`, `temp_narration.wav`, `chart_initial_design.png`, `chart_replacement_design.png`, `SHA256SUMS`, `workflow_provenance.txt`. These design boards are not rendered cast charts. The 149.11 s read exceeds the 101.20 s reference and is not suitable for motion timing.

New `--match-reference` retimer option uses local eSpeak NG at 250 wpm with per-sentence FFmpeg atempo and trailing PCM silence to match reference windows, without deliberately truncating speech. Sentence bounds measure paced PCM chunks, not individual phonemes; listen for unnatural speed before approving final audio. The new pace and smoke workflow [46101985666](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/46101985666), source commit `32228156491d51e2a44c3d5b665ccb6192a372d0`, is in progress at this checkpoint. It publishes actual or partial smoke files, source provenance, and paced audio if valid. No full motion-proof jobs launched. No final film or paid TTS.

