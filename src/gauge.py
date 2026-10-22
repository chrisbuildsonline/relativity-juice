"""On-screen velocity gauge (bpy): beta / gamma text and a beta bar, parented to the camera.

Built from Blender's bundled font and emissive planes only. It is separate from the
City object, so the warp never touches it. A frame_change_pre handler sets it from the frame.
"""
import bpy

from src.flight import time_of
from src.relativity import beta_at, gamma

BAR_W = 1.2  # bar length at beta = 1, camera-space units
CORNER = (-1.55, -0.55, -5.0)  # text origin in camera space: lower-left, 5 units ahead
GLOW = (0.25, 0.85, 1.0, 1.0)
STRENGTH = 4.0


def gauge_text(beta):
    return "β = %.3fc\nγ = %.2f" % (beta, gamma(beta))


def update_gauge(beta):
    bpy.data.objects["GaugeText"].data.body = gauge_text(beta)
    bpy.data.objects["GaugeBar"].scale.x = BAR_W * float(beta)


def _on_frame(scene, depsgraph=None):
    if "GaugeText" in bpy.data.objects:
        update_gauge(beta_at(time_of(scene.frame_current)))


def _material(name, strength):
    """Unlit emission (strength 0 is a black plate)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    glow, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeOutputMaterial")
    glow.inputs["Color"].default_value = GLOW
    glow.inputs["Strength"].default_value = strength
    links.new(glow.outputs[0], out.inputs["Surface"])
    return mat


def _strip(scene, camera, name, loc, height, mat):
    """Plane from x = 0 to 1 (scale X is its length), parented to the camera."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, height, 0), (0, height, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.parent = camera
    obj.location = loc
    scene.collection.objects.link(obj)
    return obj


def add_gauge(scene, camera):
    """Add (or rebuild) the gauge in front of `camera`; keeps it current on frame change."""
    for name in ("GaugeText", "GaugeTrack", "GaugeBar", "GaugePanel"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])
    x, y, z = CORNER
    curve = bpy.data.curves.new("GaugeText", "FONT")  # default font: Blender's bundled one
    curve.size = 0.2
    curve.materials.append(_material("GaugeText", STRENGTH))
    text = bpy.data.objects.new("GaugeText", curve)
    text.parent = camera
    text.location = CORNER
    scene.collection.objects.link(text)
    bar_y = y - 0.32
    _strip(scene, camera, "GaugeTrack", (x, bar_y, z), 0.05, _material("GaugeTrack", STRENGTH * 0.15)).scale.x = BAR_W
    _strip(scene, camera, "GaugeBar", (x, bar_y, z + 0.01), 0.05, _material("GaugeBar", STRENGTH))
    # opaque dark plate behind everything so it reads on a blown-out frame
    _strip(scene, camera, "GaugePanel", (x - 0.1, bar_y - 0.1, z - 0.05), 0.75, _material("GaugePanel", 0.0)).scale.x = BAR_W + 0.2
    if _on_frame not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_on_frame)
    _on_frame(scene)
