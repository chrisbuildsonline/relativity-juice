"""Procedural cyberpunk megacity (bpy, seeded). Flight axis is +Y."""
import math

import bpy
import numpy as np

from src.relativity import DISPLAY_BEAM_CAP, DISPLAY_BEAM_EXP, DISPLAY_DESAT_MAX, IR_FLOOR, UV_TINT_NM, UV_TINT_RGB, wavelength_rgb

CAM_Z = 25.0  # camera path: x=0, z=CAM_Z, y from 0 to length
CORRIDOR_R = 12.0  # clearance radius around the camera path
MAX_EDGE = 4.0  # subdivide so the per-vertex warp bends edges into curves
MAX_LIT_EDGE = 2.0  # lit faces: finer, so the Doppler colour does not sweep the spectrum inside one face
OVERHANG = 300.0  # city extends this far behind y=0 and ahead of y=length
STREET_X = 16.0  # inner face of the first building row
GROUND_X = 72.0
PALETTE_NM = (440.0, 470.0, 500.0, 530.0, 590.0, 620.0, 660.0)
WINDOW_EMIT = 5.0
NEON_EMIT = 14.0
UV_EDGE_NM = 380.0  # same constants as relativity.shift_rgb
IR_EDGE_NM = 780.0
UV_RANGE_NM = 120.0
IR_FADE_NM = 220.0


class _Mesh:
    """Accumulates quad grids with per-vertex base_nm / emit."""

    def __init__(self):
        self.pts, self.quads, self.nm, self.emit = [], [], [], []
        self.n = 0

    def grid(self, p0, u, v, nm=550.0, emit=0.0):
        """Quad grid on p0 + s*u + t*v, every edge <= MAX_EDGE, shared vertices."""
        p0, u, v = (np.asarray(a, dtype=float) for a in (p0, u, v))
        edge = MAX_LIT_EDGE if emit else MAX_EDGE
        nu = max(1, math.ceil(np.linalg.norm(u) / edge))
        nv = max(1, math.ceil(np.linalg.norm(v) / edge))
        s = np.arange(nu + 1) / nu
        t = np.arange(nv + 1) / nv
        pts = p0 + s[:, None, None] * u + t[None, :, None] * v
        i, j = np.meshgrid(np.arange(nu), np.arange(nv), indexing="ij")
        a = (i * (nv + 1) + j).ravel() + self.n
        quads = np.stack([a, a + nv + 1, a + nv + 2, a + 1], axis=1)
        self.pts.append(pts.reshape(-1, 3))
        self.quads.append(quads)
        count = (nu + 1) * (nv + 1)
        self.nm.append(np.full(count, nm))
        self.emit.append(np.full(count, float(emit)))
        self.n += count


def _building(m, rng, x0, y0, w, d, h):
    box = ((x0, y0, 0), (w, 0, 0), (0, -1, 0)), ((x0, y0 + d, 0), (w, 0, 0), (0, 1, 0)), \
        ((x0, y0, 0), (0, d, 0), (-1, 0, 0)), ((x0 + w, y0, 0), (0, d, 0), (1, 0, 0))
    palette = rng.choice(PALETTE_NM, size=2, replace=False)
    for origin, u, n in box:
        origin, u, n = np.array(origin, float), np.array(u, float), np.array(n, float)
        length = np.linalg.norm(u)
        uh = u / length
        m.grid(origin, u, (0, 0, h))
        out = n * 0.05
        for z in np.arange(4.0, h - 4.0, 6.0):
            if rng.random() < 0.75:
                nm = np.clip(rng.choice(palette) + rng.uniform(-10, 10), 420.0, 680.0)
                m.grid(origin + out + uh + (0, 0, z), u - 2 * uh, (0, 0, 1.8), nm, WINDOW_EMIT)
        if rng.random() < 0.5:
            nm = float(rng.choice(PALETTE_NM))
            m.grid(origin + out + (0, 0, h - 0.6), u, (0, 0, 0.6), nm, NEON_EMIT)
        if rng.random() < 0.4:
            nm = float(rng.choice(PALETTE_NM))
            m.grid(origin + out + uh * rng.uniform(1, length - 2) + (0, 0, 2), uh * 0.8, (0, 0, h - 2), nm, NEON_EMIT)
    m.grid((x0, y0, h), (w, 0, 0), (0, d, 0))


def _ground(m, length):
    y0, y1 = -OVERHANG - 50.0, length + OVERHANG + 50.0
    m.grid((-GROUND_X, y0, 0), (2 * GROUND_X, 0, 0), (0, y1 - y0, 0))
    for k, x in enumerate(np.arange(-64.0, 64.1, 16.0)):
        m.grid((x - 0.25, y0, 0.05), (0.5, 0, 0), (0, y1 - y0, 0), PALETTE_NM[k % 3], NEON_EMIT)
    for k, y in enumerate(np.arange(y0, y1, 32.0)):
        m.grid((-GROUND_X, y - 0.25, 0.05), (2 * GROUND_X, 0, 0), (0, 0.5, 0), PALETTE_NM[3 + k % 3], NEON_EMIT)


def _material():
    mat = bpy.data.materials.new("CityMat")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()

    def attr(name):
        n = nodes.new("ShaderNodeAttribute")
        n.attribute_name = name
        return n

    def math(op, a=None, b=None, c=None, clamp=False):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if isinstance(v, bpy.types.NodeSocket):
                links.new(v, n.inputs[i])
            elif v is not None:
                n.inputs[i].default_value = v
        return n.outputs[0]

    base, emit, dop = attr("base_nm"), attr("emit"), attr("doppler")
    # observed wavelength = base / D, clamped to what the Wavelength node can draw
    lam = math("DIVIDE", base.outputs["Fac"], dop.outputs["Fac"])
    clamp = nodes.new("ShaderNodeClamp")
    clamp.inputs["Min"].default_value = UV_EDGE_NM
    clamp.inputs["Max"].default_value = IR_EDGE_NM
    links.new(lam, clamp.inputs["Value"])
    wave = nodes.new("ShaderNodeWavelength")
    links.new(clamp.outputs["Result"], wave.inputs["Wavelength"])

    def ramp(src, lo, hi, smooth=False):
        r = nodes.new("ShaderNodeMapRange")
        r.interpolation_type = "SMOOTHSTEP" if smooth else "LINEAR"
        r.clamp = True
        for k, v in (("From Min", lo), ("From Max", hi), ("To Min", 0.0), ("To Max", 1.0)):
            r.inputs[k].default_value = v
        links.new(src, r.inputs["Value"])
        return r.outputs["Result"]

    def mix(fac, a, b):
        n = nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        links.new(fac, n.inputs[0])
        for i, v in ((6, a), (7, b)):  # RGBA A / B (the name "A" would hit the float socket)
            if isinstance(v, bpy.types.NodeSocket):
                links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[2]

    # UV: blend to relativity.uv_tint(base_nm) over UV_RANGE_NM below the edge; IR: deep red, dimmer with D, never black
    tint = nodes.new("ShaderNodeValToRGB")
    span = UV_TINT_NM[-1] - UV_TINT_NM[0]
    tint.color_ramp.elements.new(0.5)
    for e, nm, rgb in zip(tint.color_ramp.elements, UV_TINT_NM, UV_TINT_RGB):
        e.position, e.color = (nm - UV_TINT_NM[0]) / span, (*rgb, 1.0)
    rng = nodes.new("ShaderNodeMapRange")
    for k, v in (("From Min", UV_TINT_NM[0]), ("From Max", UV_TINT_NM[-1])):
        rng.inputs[k].default_value = v
    links.new(base.outputs["Fac"], rng.inputs["Value"])
    links.new(rng.outputs["Result"], tint.inputs["Fac"])
    # display tone-map (relativity.display_desaturation): late in the flight the spectrum is squeezed into a thin
    # ring at the frame edge; pull visible-band colour towards its own grey so it does not read as a rainbow glitch
    bw = nodes.new("ShaderNodeRGBToBW")
    links.new(wave.outputs["Color"], bw.inputs["Color"])
    visible = mix(attr("desat").outputs["Fac"], wave.outputs["Color"], bw.outputs["Val"])
    uv = mix(ramp(lam, UV_EDGE_NM, UV_EDGE_NM - UV_RANGE_NM), visible, tint.outputs["Color"])
    # past 780 nm: relativity.display_infrared, the red edge colour (the Wavelength node is nearly black there; desaturated like
    # the rest late in the flight) down to IR_FLOOR by 1000 nm, then falling as 1000 / lambda
    edge = wavelength_rgb(IR_EDGE_NM)
    grey = float(edge @ (0.2126, 0.7152, 0.0722))
    red = mix(attr("desat").outputs["Fac"], (*edge, 1.0), (grey, grey, grey, 1.0))
    fade = math("MULTIPLY_ADD", ramp(lam, IR_EDGE_NM + IR_FADE_NM, IR_EDGE_NM, smooth=True), 1.0 - IR_FLOOR, IR_FLOOR)
    tail = math("MULTIPLY", fade, math("DIVIDE", IR_EDGE_NM + IR_FADE_NM, lam, clamp=True))
    keep = math("MULTIPLY_ADD", attr("desat").outputs["Fac"], -1.0 / DISPLAY_DESAT_MAX, 1.0)  # all of it follows the late-flight desaturation out
    infrared = mix(math("MULTIPLY", tail, keep), (0.0, 0.0, 0.0, 1.0), red)
    shifted = mix(ramp(lam, IR_EDGE_NM, IR_EDGE_NM + 1.0), uv, infrared)
    # beaming tone-mapped from D^4 to min(D^2, cap) (relativity.display_beaming); only camera rays see it,
    # so bounce light off the walls stays at rest brightness instead of whiting them out
    beam = math("MINIMUM", math("POWER", dop.outputs["Fac"], DISPLAY_BEAM_EXP), DISPLAY_BEAM_CAP)
    cam_ray = nodes.new("ShaderNodeLightPath").outputs["Is Camera Ray"]
    strength = math("MULTIPLY", emit.outputs["Fac"], math("MULTIPLY_ADD", math("SUBTRACT", beam, 1.0), cam_ray, 1.0))
    glow = nodes.new("ShaderNodeEmission")
    dark = nodes.new("ShaderNodeBsdfPrincipled")
    dark.inputs["Base Color"].default_value = (0.012, 0.014, 0.02, 1.0)
    dark.inputs["Roughness"].default_value = 0.35
    add = nodes.new("ShaderNodeAddShader")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(shifted, glow.inputs["Color"])
    links.new(strength, glow.inputs["Strength"])
    links.new(dark.outputs["BSDF"], add.inputs[0])
    links.new(glow.outputs["Emission"], add.inputs[1])
    links.new(add.outputs["Shader"], out.inputs["Surface"])
    return mat


def build_city(seed=7, length=2000.0):
    """Build the city into the current scene; returns the single mesh object "City"."""
    rng = np.random.default_rng(seed)
    m = _Mesh()
    _ground(m, length)
    for side in (-1, 1):
        y = -OVERHANG
        while y < length + OVERHANG:
            w = rng.uniform(14, 36)
            d = rng.uniform(12, 28)
            h = float(np.clip(rng.lognormal(4.0, 0.5), 30, 260))
            x0 = STREET_X + rng.uniform(0, 8)
            _building(m, rng, x0 if side > 0 else -x0 - w, y, w, d, h)
            y += d + rng.uniform(0, 5)
    # skyline wall closing the street behind the start: looking back, aberration blows the open end up to fill the view
    x = -GROUND_X
    while x < GROUND_X:
        w, d = rng.uniform(14, 36), rng.uniform(12, 28)
        _building(m, rng, x, -OVERHANG - d, w, d, float(np.clip(rng.lognormal(4.0, 0.5), 60, 260)))
        x += w

    pts = np.concatenate(m.pts)
    mesh = bpy.data.meshes.new("City")
    mesh.from_pydata(pts.tolist(), [], np.concatenate(m.quads).tolist())
    # doppler = 1 (rest), desat = 0 until the warp modifier overwrites them
    for name, values in (("base_nm", m.nm), ("emit", m.emit), ("doppler", [np.ones(len(pts))]), ("desat", [np.zeros(len(pts))])):
        mesh.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", np.concatenate(values))
    mesh.materials.append(_material())
    obj = bpy.data.objects.new("City", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_view(scene, y=0.0):
    """Camera at (0, y, CAM_Z) looking down +Y, plus a near-black world and AgX."""
    scene.view_settings.view_transform = "AgX"
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.clip_end = 5000.0
    cam.location = (0.0, y, CAM_Z)
    cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    world = bpy.data.worlds.new("World")
    world.color = (0.004, 0.004, 0.01)
    scene.world = world
