# Stage B — interaction preview

Run from the repository root:

```sh
blender -b --python-exit-code 1 --python scripts/render_cafe_interaction.py -- --profile preview --output render/cafe
```

CI: Blender render → Run workflow → mode=animation, scene=cafe, profile=preview. The cafe scene is fixed at five seconds; the duration input applies to the original demo only. Preview is 360×640, 12 fps, 60 frames. The original demo is still the default animation scene.

The moving cup starts on the table. A real wrist socket drives the cup through a keyed world-space copy-transforms constraint (animated parent relationship); when released, the last held world position is retained and gravity takes over with a damped bounce onto the tabletop. This prototype intentionally lands upright; it is not a general rigid-body collision simulation. Lead and friend expression decals are keyed by discrete visibility.

The interaction manifest reports the actual frame-by-frame cup bottom, state, expression, grip error and support-height checks. The camera is fixed; lower-body cropping is intentional in the medium shot.
