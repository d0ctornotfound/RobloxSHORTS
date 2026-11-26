# RobloxSHORTS

## Production skill — start here

Read [SKILL.md](SKILL.md) for the current end-to-end animated story production system: supplied R6 character rebuild (approval pending), story schema, Blender render, edit, validation and evidence delivery. The Last Slice is historically approved at preview quality; the old character standard has since been rejected. New R6 approval stills must be approved before either short is rerendered; see [project state](docs/PROJECT_STATE.md). To reuse in ChatGPT, start a fresh chat, connect/authorize this repository and point it at SKILL.md; the file does not install itself. The story renderer is currently café/cake-specific and requires adaptation for new choreography. The demo below is historical, not the current production entry point.

## Blender cloud rendering

A starter pipeline for generating vertical, silent 3D animations with Blender on GitHub-hosted Ubuntu runners. The procedural demo uses no third-party assets or paid AI APIs.

Open [Actions → Blender render](https://github.com/d0ctornotfound/RobloxSHORTS/actions/workflows/blender-render.yml), select **Run workflow**, and choose a profile and duration (5 or 10 seconds):

| Profile | Resolution | FPS | Duration |
| --- | --- | --- | --- |
| preview | 360 × 640 | 12 | 5 or 10 seconds |
| full | 1080 × 1920 | 24 | 5 or 10 seconds |

A five-second preview is also configured to run when the render script or workflow changes on main. Download the roblox-demo-preview-5s (or the corresponding selected profile and duration) artifact from the run summary. It contains demo.mp4, scene.blend and metadata.json. The workflow validates resolution, frame rate, frame count and duration before uploading.

GitHub Actions must be enabled. Standard public-repository Ubuntu runners use CPU rendering. Full-quality rendering may hit the 45-minute timeout. Check billing and artifact limits before using other runners or making the repository private. Artifacts expire after seven days.

## Local rendering

Install Blender and FFmpeg, then run:

```sh
blender -b --python-exit-code 1 --python scripts/render_demo.py -- --profile preview --output render
ffmpeg -framerate 12 -start_number 1 -i render/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart render/demo.mp4
```

For a five-second animation, add `--duration 5` to the Blender command. The Ubuntu package may lack OpenImageDenoiser, so denoising is disabled for CPU compatibility. For a single still, add `--still` to the Blender command. For full resolution, change the profile to full and FFmpeg frame rate to 24.

## Scope

The demo builds original R6-inspired block characters, simple pivot-based limb animation, a procedural town, lighting and a camera with bounding-box safety checks. It does not yet implement imported R6 rigs, foot-locking IK, lip sync, dialogue, scene editing, or script-to-shot conversion. No ElevenLabs calls or audio generation are made.

Future work: reusable rigs, a scene/shot schema, animation clips, collision-aware blocking, a multi-shot camera director and story-specific renders.
