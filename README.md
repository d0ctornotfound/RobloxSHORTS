# RobloxSHORTS
To be used for Chatgpt.

## Blender cloud rendering

A starter pipeline for generating vertical, silent 3D animations with Blender on GitHub-hosted Ubuntu runners. The procedural demo uses no third-party assets or paid AI APIs.

Open [Actions → Blender render](https://github.com/d0ctornotfound/RobloxSHORTS/actions/workflows/blender-render.yml), select **Run workflow**, and choose a profile:

| Profile | Resolution | FPS | Duration |
| --- | --- | --- | --- |
| preview | 360 × 640 | 12 | 10 seconds |
| full | 1080 × 1920 | 24 | 10 seconds |

The preview is also configured to run when the render script or workflow changes on main. Download the roblox-demo-preview or roblox-demo-full artifact from the run summary. It contains demo.mp4, scene.blend and metadata.json. The workflow validates resolution, frame rate, frame count and duration before uploading.

GitHub Actions must be enabled. Standard public-repository Ubuntu runners use CPU rendering. Full-quality rendering may hit the 45-minute timeout. Check billing and artifact limits before using other runners or making the repository private. Artifacts expire after seven days.

## Local rendering

Install Blender and FFmpeg, then run:

```sh
blender -b --python-exit-code 1 --python scripts/render_demo.py -- --profile preview --output render
ffmpeg -framerate 12 -start_number 1 -i render/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart render/demo.mp4
```

For a single still, add `--still` to the Blender command. For full resolution, change the profile to full and FFmpeg frame rate to 24.

## Scope

The demo builds original R6-inspired block characters, simple pivot-based limb animation, a procedural town, lighting and a camera with bounding-box safety checks. It does not yet implement imported R6 rigs, foot-locking IK, lip sync, dialogue, scene editing, or script-to-shot conversion. No ElevenLabs calls or audio generation are made.

Future work: reusable rigs, a scene/shot schema, animation clips, collision-aware blocking, a multi-shot camera director and story-specific renders.
