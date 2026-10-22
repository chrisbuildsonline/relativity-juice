"""Headless Cycles CPU smoke render: one 64x36 frame, then check it is not flat."""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "smoke")
PNG = os.path.join(OUT, "smoke.png")
os.makedirs(OUT, exist_ok=True)
if os.path.exists(PNG):
    os.remove(PNG)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Emissive cube.
bpy.ops.mesh.primitive_cube_add(size=2)
cube = bpy.context.active_object
mat = bpy.data.materials.new("glow")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()
emit = nodes.new("ShaderNodeEmission")
emit.inputs["Color"].default_value = (1.0, 0.2, 0.6, 1.0)
emit.inputs["Strength"].default_value = 4.0
out = nodes.new("ShaderNodeOutputMaterial")
mat.node_tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
cube.data.materials.append(mat)

# Camera.
bpy.ops.object.camera_add(location=(4, -4, 3), rotation=(1.1, 0, 0.785))
scene.camera = bpy.context.active_object

# Dark world so the cube stands out.
world = bpy.data.worlds.new("w")
world.color = (0.02, 0.02, 0.05)
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.render.resolution_x = 64
scene.render.resolution_y = 36
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = PNG

bpy.ops.render.render(write_still=True)

if not os.path.exists(PNG):
    sys.exit("smoke: no PNG written at " + PNG)

img = bpy.data.images.load(PNG)
w, h = img.size
if (w, h) != (64, 36):
    sys.exit("smoke: unexpected size %dx%d" % (w, h))
px = list(img.pixels)
colours = {tuple(round(v, 3) for v in px[i:i + 4]) for i in range(0, len(px), 4)}
if len(colours) < 2:
    sys.exit("smoke: render is a single flat colour: %s" % (colours,))
print("smoke ok: %dx%d, %d distinct colours -> %s" % (w, h, len(colours), PNG))
