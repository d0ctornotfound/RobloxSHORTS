"""Deterministic, irregular R6 blink scheduling shared by every character builder.

Blink timing is scene-time based (not action-time based), so it overlays any
body animation and expression track without changing the underlying motion.
"""
import hashlib
import random
import bpy
from bpy.app.handlers import persistent

_REGISTRY = {}
_DEFAULT_INTERVAL = (2.0, 5.0)
_DEFAULT_CLOSED = (.12, .15)

def _scene_key(scene):
    try:
        return scene.as_pointer()
    except Exception:
        return id(scene)

class BlinkController:
    def __init__(self, actor, seed=0, interval=_DEFAULT_INTERVAL, closed=_DEFAULT_CLOSED):
        self.actor = actor
        token = (actor.root.name + "|" + str(seed)).encode("utf-8")
        self.seed = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
        self.interval = tuple(interval)
        self.closed = tuple(closed)
        self.signature = None
        self.events = []

    def _build(self, scene):
        fps = float(scene.render.fps) / max(float(scene.render.fps_base), 1e-8)
        start = int(scene.frame_start)
        end = int(scene.frame_end)
        signature = (start, end, fps, self.interval, self.closed)
        if signature == self.signature:
            return
        self.signature = signature
        duration = max(0.0, (end - start + 1) / max(fps, 1e-8))
        rng = random.Random(self.seed)
        cursor = rng.uniform(1.25, 2.55)
        self.events = []
        while cursor < duration:
            length = rng.uniform(*self.closed)
            self.events.append((cursor, cursor + length))
            cursor += length + rng.uniform(*self.interval)

    def is_closed(self, scene, frame):
        self._build(scene)
        fps = float(scene.render.fps) / max(float(scene.render.fps_base), 1e-8)
        seconds = (int(frame) - int(scene.frame_start)) / max(fps, 1e-8)
        return any(start <= seconds < end for start, end in self.events)

    def manifest(self, scene):
        self._build(scene)
        return [{"start_seconds": round(a, 4), "end_seconds": round(b, 4),
                 "closed_seconds": round(b-a, 4)} for a, b in self.events]

def _apply_actor(actor, scene, frame):
    if not getattr(actor, "_blink_enabled", True):
        closed = False
    else:
        controller = getattr(actor, "_blink_controller", None)
        closed = bool(controller and controller.is_closed(scene, frame))
    tracks = getattr(actor, "_expression_tracks", ())
    if tracks:
        for track in tracks:
            expression = track.expression_at(frame)
            active = "sleep_closed" if closed else expression
            for name, obj in track.decals.items():
                obj.hide_render = name != active
    else:
        expression = getattr(actor, "current_expression", "neutral")
        name = "sleep_closed" if closed else expression
        materials = getattr(actor, "face_materials", {})
        face = getattr(actor, "face", None)
        if face is not None and name in materials and face.data.materials:
            face.data.materials[0] = materials[name]

@persistent
def _blink_frame_change(scene, depsgraph=None):
    for actor in tuple(_REGISTRY.get(_scene_key(scene), ())):
        try:
            _apply_actor(actor, scene, scene.frame_current)
        except ReferenceError:
            continue

def enable_blinking(scene, actors, seed=0, interval=_DEFAULT_INTERVAL, closed=_DEFAULT_CLOSED):
    """Enable irregular 2–5s blinks on one or more actors in this scene.

    Closed-lid decal duration defaults to 0.12–0.15 seconds. Actors can be
    passed directly or as a sequence. Repeated calls are safe and deterministic.
    """
    if not isinstance(actors, (list, tuple, set)):
        actors = [actors]
    key = _scene_key(scene)
    registered = _REGISTRY.setdefault(key, [])
    for actor in actors:
        if actor not in registered:
            registered.append(actor)
        actor._blink_enabled = True
        actor._blink_controller = BlinkController(actor, seed, interval, closed)
        if not hasattr(actor, "_expression_tracks"):
            actor._expression_tracks = []
        _apply_actor(actor, scene, scene.frame_current)
    if _blink_frame_change not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_blink_frame_change)
    return {actor.root.name: actor._blink_controller.manifest(scene) for actor in actors}

def disable_blinking(scene, actors=None):
    """Disable blinking for all actors in a scene, or a selected subset."""
    key = _scene_key(scene)
    registered = _REGISTRY.get(key, [])
    selected = list(registered) if actors is None else (list(actors) if isinstance(actors, (list, tuple, set)) else [actors])
    for actor in selected:
        actor._blink_enabled = False
        _apply_actor(actor, scene, scene.frame_current)
        if actor in registered:
            registered.remove(actor)
    if not registered:
        _REGISTRY.pop(key, None)

def refresh_expression(actor):
    """Refresh the direct decal after pose(), respecting the current blink."""
    scene = bpy.context.scene
    _apply_actor(actor, scene, scene.frame_current)

