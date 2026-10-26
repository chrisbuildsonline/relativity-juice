"""Render the title and end cards (1920x1080, Cycles CPU) to out/cards/title.png and out/cards/end.png.

Blender's bundled font, emissive text in the gauge's cyan on near-black. The end card's numbers are
computed from the flight (last frame), not typed in.
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.flight import DURATION, FRAME_END, FRAME_START, time_of  # noqa: E402
from src.gauge import GLOW  # noqa: E402
from src.relativity import beta_at, gamma  # noqa: E402

OUT = os.path.join(ROOT, "out", "cards")
FIRST, LAST = beta_at(time_of(FRAME_START)), beta_at(time_of(FRAME_END))
DIM = (GLOW[0], GLOW[1] * 0.5, GLOW[2] * 0.5, 1.0)  # same hue, quieter, for the small lines

# (text, size, y, colour): y in scene units, the camera sees 16 x 9
TITLE = [("RELATIVITY JUICE", 1.25, 0.6, GLOW),
         ("NEON RACER: 85 to 420 KM/H (%gc to %gc)" % (FIRST, beta_at(DURATION)), 0.45, -0.5, GLOW),
         ("procedural 70s wedge supercars, Geometry Nodes, 90s Synthwave", 0.30, -1.6, DIM),
         ("theme: Speed", 0.28, -3.4, DIM)]
END = [("85 to 420 KM/H (%gc to %.4gc) in %g s" % (FIRST, LAST, DURATION), 0.68, 0.9, GLOW),
       ("4 native Blender cameras, 124 BPM synthwave, γ %.2f to %.1f" % (gamma(FIRST), gamma(LAST)), 0.44, -0.4, GLOW),
       ("procedural Blender, Cycles, Geometry Nodes, no hand keys", 0.32, -2.0, DIM)]


def card(name, lines):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.002, 0.003, 0.006, 1.0)  # type: ignore
    scene.world = world
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.type = "ORTHO"  # type: ignore
    cam.data.ortho_scale = 16.0  # type: ignore
    cam.location = (0.0, 0.0, 10.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for text, size, y, color in lines:
        curve = bpy.data.curves.new("t", "FONT")  # default font: Blender's bundled one
        curve.body = text
        curve.size = size
        curve.align_x = "CENTER"
        mat = bpy.data.materials.new("m")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes  # type: ignore
        nodes.clear()
        glow, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeOutputMaterial")
        glow.inputs["Color"].default_value = color
        mat.node_tree.links.new(glow.outputs[0], out.inputs["Surface"])  # type: ignore
        curve.materials.append(mat)
        obj = bpy.data.objects.new("t", curve)
        obj.location = (0.0, y, 0.0)
        scene.collection.objects.link(obj)
    os.makedirs(OUT, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("cards: %s" % scene.render.filepath)


card("title", TITLE)
card("end", END)
