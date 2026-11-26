# Integrated Last Slice — short #1

Port of unchanged stories/the_last_slice.json, timing, action and narration text. Quality character and café modules replace Stage A assets. Retargeted actor roots, shoulder length, plate rim offset, friend reach, actual highest hair mesh vertex for head contact. Existing GripAttachment, GravityDrop, ExpressionTrack and editor retained. Static seated patrons, matte hair, fitted knitted wrap, corrected yellow and no legacy window crossbars. Camera retarget uses horizontal sensor fit, per-frame per-hero clipped vertical projected bounds (not pixel area). Minimum .45 required. Preview 432×768, 12 fps, 24 Cycles samples, adaptive threshold .065; FFmpeg hqdn3d before captions (OIDN unavailable on CI). Full 1080×1920, 24fps, 96 samples. No voice audio supplied; optional narration WAV remains.

CI pending. Local: `blender -b --python-exit-code 1 --python scripts/render_story.py -- --profile preview --output render/story` then `python3 scripts/edit_story.py --profile preview --frames render/story --output render/final --verify-slot`.

First CI [45875679636](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45875679636) failed the frontal notice framing gate (lead 35.19%, friend 30.64%). Replaced frontal blocking with tested oblique long-lens candidates and orthographic fallback; every animated frame is checked for protected subject bounds, hero vertical coverage and face separation. Side cutaways preserve lighting/shadow rays.

Second CI run 45876003484 passed all four framing gates (notice 46.49%/48.21%, reach 53.93%/47.22%, impact 66.80%, payoff 45.90%/47.13%) but failed manifest JSON because the camera sampling list shadowed the integer render sample count. Renamed the list; retry pending.

Third run 45876246444 successfully serialized complete 144-frame manifest and passed all interaction/coverage gates (zero binding error, 0.03002 friend rim error, support z 2.91408, launch 80, landing 92, payoff 2.5 s). A camera angle variable shadowed CLI args before rendering; renamed it to theta.
