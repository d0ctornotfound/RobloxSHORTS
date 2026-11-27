# Private map harvest — MCRD San Diego

Creator **LoneWolf_Alfa**, [original BuiltByBit release](https://builtbybit.com/resources/mcrd-san-diego.62883/), Free EULA; [license explanation](https://builtbybit.com/help/users/buying/licenses/). Source provided by user: 35,651,381 bytes, SHA-256 0d383e8e4ee0b3162e79f856efc22e8fa00a213b477fd2a496b36f500388eed1. Header 159 classes / 101,697 instances. Original creator requires attribution.

The public repository intentionally holds no original RBXL, mesh/texture bytes, or extracted third-party GLBs. Use the private user-delivered ZIP or regenerate from the licensed source in a private working directory. Do not commit the generated library here or publish it as a redistributable asset pack without permission.

First-pass assets: office_desk (39), wood_bench (13), garage_shelf (8), metal_door (6), metal_table (25), folding_table (9), window_frame_a (21), window_frame_b (30), locker_room_bench (27), door_panel_a (9). 187 visible parts. Source RGB, dimensions and CFrames retained; primitive shapes tessellated; generic PBR approximation; no external image bytes retrieved. Transparent helpers omitted. Trees, mesh chairs, vehicles, fences and building CSG are deferred, not replaced by bounding-box impostors.

Usage: install numpy, trimesh and optional lz4; run `python scripts/rbxl_harvest.py /private/mcrd_san_diego.bin --output /private/mcrd`. Import GLBs with Blender, source studs, Y-up automatically converted. Use common scale 2.28/5 for a five-stud source character reference, adapt after measuring. `blender -b --python scripts/render_harvest_review.py -- --assets /private/mcrd --output /private/review` on an authorized private rendering environment with the approved project rig and texture assets. Review driver authored but not yet run; no public CI run initiated. Only geometry/appearance allowlist; no script execution, game logic, weapon systems, or datastore extraction.

Full inventory and actual geometry catalogue were delivered privately in chat.
