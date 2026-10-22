"""Procedural cyberpunk megacity (bpy, seeded). Flight axis is +Y."""
import math

import bpy
import numpy as np

CAM_Z = 25.0  # camera path: x=0, z=CAM_Z, y from 0 to length
CORRIDOR_R = 12.0  # clearance radius around the camera path
MAX_EDGE = 4.0  # subdivide so the per-vertex warp bends edges into curves
OVERHANG = 300.0  # city extends this far behind y=0 and ahead of y=length
STREET_X = 16.0  # inner face of the first building row
GROUND_X = 72.0
PALETTE_NM = (440.0, 470.0, 500.0, 530.0, 590.0, 620.0, 660.0)
WINDOW_EMIT = 5.0
NEON_EMIT = 14.0


class _Mesh:
    """Accumulates quad grids with per-vertex base_nm / emit."""

    def __init__(self):
        self.pts, self.quads, self.nm, self.emit = [], [], [], []
        self.n = 0

    def grid(self, p0, u, v, nm=550.0, emit=0.0):
        """Quad grid on p0 + s*u + t*v, every edge <= MAX_EDGE, shared vertices."""
        p0, u, v = (np.asarray(a, dtype=float) for a in (p0, u, v))
        nu = max(1, math.ceil(np.linalg.norm(u) / MAX_EDGE))
        nv = max(1, math.ceil(np.linalg.norm(v) / MAX_EDGE))
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
    base = nodes.new("ShaderNodeAttribute")
    base.attribute_name = "base_nm"
    emit = nodes.new("ShaderNodeAttribute")
    emit.attribute_name = "emit"
    wave = nodes.new("ShaderNodeWavelength")
    glow = nodes.new("ShaderNodeEmission")
    dark = nodes.new("ShaderNodeBsdfPrincipled")
    dark.inputs["Base Color"].default_value = (0.012, 0.014, 0.02, 1.0)
    dark.inputs["Roughness"].default_value = 0.35
    add = nodes.new("ShaderNodeAddShader")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(base.outputs["Fac"], wave.inputs["Wavelength"])
    links.new(wave.outputs["Color"], glow.inputs["Color"])
    links.new(emit.outputs["Fac"], glow.inputs["Strength"])
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

    pts = np.concatenate(m.pts)
    mesh = bpy.data.meshes.new("City")
    mesh.from_pydata(pts.tolist(), [], np.concatenate(m.quads).tolist())
    for name, values in (("base_nm", m.nm), ("emit", m.emit)):
        mesh.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", np.concatenate(values))
    mesh.materials.append(_material())
    obj = bpy.data.objects.new("City", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_view(scene):
    """Camera at the path start looking down +Y, plus a near-black world."""
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.clip_end = 5000.0
    cam.location = (0.0, 0.0, CAM_Z)
    cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    world = bpy.data.worlds.new("World")
    world.color = (0.004, 0.004, 0.01)
    scene.world = world
