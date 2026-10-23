"""On-screen velocity gauge (bpy): beta / gamma text and a beta bar, parented to the camera.

Built from Blender's bundled font and emissive planes only. It is separate from the
City object, so the warp never touches it. A frame_change_pre handler sets it from the frame.
"""
import bpy

from src.flight import time_of
from src.relativity import beta_at, gamma

BAR_W = 1.2  # bar length at beta = 1, camera-space units
CORNER = (-1.5, -0.65, -5.0)  # text origin in camera space: lower-left, 5 units ahead
GLOW = (0.0, 0.45, 1.0, 1.0)
STRENGTH = 0.9 # AgX desaturates anything brighter towards white
TEXT_SIZE = 0.12
BACKING_ALPHA = 0.94  # share of the frame behind the gauge that is dimmed to black
FRAME_LINE = 0.012


def gauge_text(beta):
    return "β = %.3fc\nγ = %.2f" % (beta, gamma(beta))


def update_gauge(beta):
    bpy.data.objects["GaugeText"].data.body = gauge_text(beta)
    bpy.data.objects["GaugeBar"].scale.x = BAR_W * float(beta)


def _on_frame(scene, depsgraph=None):
    if "GaugeText" in bpy.data.objects:
        update_gauge(beta_at(time_of(scene.frame_current)))


def _material(name, strength):
    """Unlit emission."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    glow, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeOutputMaterial")
    glow.inputs["Color"].default_value = GLOW
    glow.inputs["Strength"].default_value = strength
    links.new(glow.outputs[0], out.inputs["Surface"])
    return mat


def _backing(name):
    """Black at BACKING_ALPHA, see-through for the rest."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    clear, black = nodes.new("ShaderNodeBsdfTransparent"), nodes.new("ShaderNodeEmission")
    black.inputs["Strength"].default_value = 0.0
    mix, out = nodes.new("ShaderNodeMixShader"), nodes.new("ShaderNodeOutputMaterial")
    mix.inputs["Fac"].default_value = BACKING_ALPHA
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(black.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def _frame(scene, camera, name, loc, w, h, mat):
    """Thin outline of a w x h rectangle (four quads), parented to the camera."""
    t = FRAME_LINE
    o = [(0, 0), (w, 0), (w, h), (0, h)]
    i = [(t, t), (w - t, t), (w - t, h - t), (t, h - t)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(px, py, 0) for px, py in o + i], [], [(k, (k + 1) % 4, 4 + (k + 1) % 4, 4 + k) for k in range(4)])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.parent = camera
    obj.location = loc
    scene.collection.objects.link(obj)
    return obj


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
    for name in ("GaugeText", "GaugeTrack", "GaugeBar", "GaugePanel", "GaugeFrame"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])
    x, y, z = CORNER
    curve = bpy.data.curves.new("GaugeText", "FONT")  # default font: Blender's bundled one
    curve.size = TEXT_SIZE
    curve.materials.append(_material("GaugeText", STRENGTH))
    text = bpy.data.objects.new("GaugeText", curve)
    text.parent = camera
    text.location = CORNER
    scene.collection.objects.link(text)
    bar_y = y - 0.24
    _strip(scene, camera, "GaugeTrack", (x, bar_y, z), 0.03, _material("GaugeTrack", STRENGTH * 0.15)).scale.x = BAR_W
    _strip(scene, camera, "GaugeBar", (x, bar_y, z + 0.01), 0.03, _material("GaugeBar", STRENGTH))
    # translucent dark backing: dims a beamed window behind the glyphs without a black box
    _strip(scene, camera, "GaugePanel", (x - 0.08, bar_y - 0.03, z - 0.05), 0.39, _backing("GaugePanel")).scale.x = BAR_W + 0.16
    _frame(scene, camera, "GaugeFrame", (x - 0.08, bar_y - 0.03, z - 0.04), BAR_W + 0.16, 0.39, _material("GaugeFrame", STRENGTH))
    if _on_frame not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_on_frame)
    _on_frame(scene)
