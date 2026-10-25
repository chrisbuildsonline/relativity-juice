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
PANEL_W = 2.5  # wide enough for "D = 0.229  exposure +4.4 stops"
LABEL_STRENGTH = 0.9
STOPS_PER_HALVING = 1.25  # the display beaming already dims as D^2 (2 stops); this puts back most of it
EXPOSURE_MAX = 4.0  # stops, reached at D = 0.109 (0.98c), past the end of the inset window


def rear_d(beta):
    return 1.0 / (gamma(beta) * (1.0 + beta))


def exposure_stops(beta):
    """Film exposure gain for the rear view: STOPS_PER_HALVING stops per halving of D, under the displayed D^2 dimming, capped.

    The inset stays readable but still darkens as the speed climbs; the label states the gain, so nothing is hidden.
    """
    return min(EXPOSURE_MAX, -STOPS_PER_HALVING * math.log2(rear_d(beta)))


def label_text(beta):
    return "LOOKING BACK\nD = %.3f  exposure %+.1f stops" % (rear_d(beta), exposure_stops(beta))


def _on_frame(scene, depsgraph=None):
    beta = beta_at(time_of(scene.frame_current))
    if "RearLabel" in bpy.data.objects:
        bpy.data.objects["RearLabel"].data.body = label_text(beta)  # type: ignore
    rear = scene.camera is not None and scene.camera.name == "RearCam"
    scene.view_settings.exposure = exposure_stops(beta) if rear else 0.0  # the gain belongs to the rear render only


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
    scene.camera = cam
    _on_frame(scene)
    return cam
