# Stage A v1 stills

All meshes, face images and material patterns are original and generated inside Blender. No asset services or external asset downloads.

Run locally from the repository root (Blender 4.x):
```sh
blender -b --python-exit-code 1 --python scripts/render_stills.py -- --profile preview --output render/stills
```

GitHub Actions: Blender render → Run workflow → mode=stills, profile=preview (540×960) or full (1080×1920). Changes to the Stage A scripts on main also trigger stills. Other existing animation triggers and the default manual animation mode remain. Artifact: roblox-stage-a-stills-preview or roblox-stage-a-stills-full.

The lead is the teal striped knit, indigo denim and swept espresso hair actor. The friend wears a berry knit and mustard beanie. Face decal swaps are neutral, happy, shocked and sad; the wide shot uses neutral and sad. Captions/audio and animated story beats are outside Stage A v1.
