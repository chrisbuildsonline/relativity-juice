"""Rear-view camera (bpy): follows the flight camera, looks back along -Y, with a baked-in label.

The Warp modifier still aberrates about the flight camera, so this shows what a window behind you sees:
D = 1 / (gamma (1 + beta)) on the back axis, so the city reddens, dims and empties out as beta rises.
"""
import math

import bpy

from src.flight import time_of
from src.gauge import _backing, _material, _strip
from src.relativity import beta_at, gamma

LABEL_AT = (-1.7, -0.68, -5.0)  # text origin in camera space: lower-left, 5 units ahead of the rear camera
LABEL_SIZE = 0.14
PANEL_W = 1.2
LABEL_STRENGTH = 0.9


def label_text(beta):
    return "LOOKING BACK\nD = %.3f" % (1.0 / (gamma(beta) * (1.0 + beta)))


def _on_frame(scene, depsgraph=None):
    if "RearLabel" in bpy.data.objects:
        bpy.data.objects["RearLabel"].data.body = label_text(beta_at(time_of(scene.frame_current)))  # type: ignore


def add_rear(scene):
    """Add "RearCam" (locked to the scene camera's position, facing -Y) and its label; make it the scene camera."""
    flight = scene.camera
    for name in ("RearCam", "RearLabel", "RearPanel"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])
    for o in bpy.data.objects:
        if o.name.startswith("Gauge"):
            o.hide_render = True  # parented to the flight camera: it would float in the rear view
    cam = bpy.data.objects.new("RearCam", bpy.data.cameras.new("RearCam"))
    cam.data.clip_end = flight.data.clip_end  # type: ignore
    cam.data.lens = flight.data.lens  # type: ignore
    cam.rotation_euler = (math.pi / 2, 0.0, math.pi)
    lock = cam.constraints.new("COPY_LOCATION")
    lock.target = flight  # type: ignore
    scene.collection.objects.link(cam)
    curve = bpy.data.curves.new("RearLabel", "FONT")  # default font: Blender's bundled one
    curve.size = LABEL_SIZE
    curve.materials.append(_material("RearLabel", LABEL_STRENGTH))
    label = bpy.data.objects.new("RearLabel", curve)
    label.parent = cam
    label.location = LABEL_AT
    scene.collection.objects.link(label)
    x, y, z = LABEL_AT  # the same translucent dark backing as the gauge, so the label reads over a lit facade
    _strip(scene, cam, "RearPanel", (x - 0.08, y - 0.26, z - 0.05), 0.42, _backing("RearPanel")).scale.x = PANEL_W
    if _on_frame not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_on_frame)
    _on_frame(scene)
    scene.camera = cam
    return cam
