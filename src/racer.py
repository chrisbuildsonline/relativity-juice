"""Native Blender procedural 70s/80s Synthwave Neon Racer scene (bpy + numpy).

Builds the complete animated scene inside Blender with zero external assets and zero post-composited overlays:
- HeroRacer (gunmetal + cyan neon 70s wedge supercar) and RivalRacer (crimson/orange interceptor), each with
  4 child wheel objects (spinning neon rims keyframed from arc length) and F-curve banking.
- SynthHighway: glossy wet-asphalt 4-lane highway, dashed neon lane lines, overhead neon speed-gantries,
  flanking wireframe neon mountains, and a giant segmented OutRun sunset sun.
- Geometry Nodes modifiers built in Python:
  1. HighwayNodes (on SynthHighway): 124 BPM synthwave wave displacement + gantry pulse.
  2. TrailNodes (on PlasmaTrails): procedural Tron-style twin plasma light-ribbons + frame-253 boost shockwave.
- 4 native Blender shot cameras (CamLaunch, CamHeli, CamOvertake, CamBoost) + timeline markers at frames
  1, 85, 169, and 253, with shutter-safe pre-cut keyframes and an in-camera 3D telemetry HUD.
"""
import math

import bpy
import numpy as np

from src.flight import DURATION, FPS, FRAME_END, FRAME_START, time_of
from src.relativity import beta_at, gamma

SHOT_CUTS = (
    (1, "CamLaunch"),
    (85, "CamHeli"),
    (169, "CamOvertake"),
    (253, "CamBoost"),
)
HIGHWAY_LEN = 2400.0
WHEEL_R = 0.42

_T = np.linspace(0.0, DURATION, 3001)
_DT = float(_T[1] - _T[0])


def _speed_mps(t):
    """Forward speed in scene units/s: ramps from 58 u/s (85 km/h) to 165 u/s (420 km/h) with boost at 10.5 s."""
    t_arr = np.asarray(t, dtype=float)
    u = np.clip(t_arr / DURATION, 0.0, 1.0)
    base = 58.0 + 78.0 * (u * u * (3.0 - 2.0 * u))
    boost = 34.0 / (1.0 + np.exp(-(t_arr - 10.5) * 3.5))
    return base + boost


_V_GRID = _speed_mps(_T)
_Y_GRID = np.concatenate([[0.0], np.cumsum(0.5 * (_V_GRID[1:] + _V_GRID[:-1]) * _DT)])


def hero_y(t):
    """Hero car forward Y position at time t (seconds)."""
    out = np.interp(np.asarray(t, dtype=float), _T, _Y_GRID)
    return float(out) if out.ndim == 0 else out


def hero_kmh(t):
    """Displayed telemetry speed in km/h (85 km/h at launch -> 420 km/h at hyper-boost finish)."""
    u = min(max(float(t) / DURATION, 0.0), 1.0)
    b = float(beta_at(min(max(float(t), 0.0), DURATION)))
    boost = 1.0 / (1.0 + math.exp(-(float(t) - 10.5) * 4.0))
    return 85.0 + 255.0 * (0.45 * u + 0.55 * b) + 80.0 * boost


def hero_x(t):
    """Hero car lateral lane trajectory X(t): stays within [-3.2, +3.2] for tight dramatic framing."""
    tf = float(t)
    # Starts right-center (+2.3), carves a dramatic S-curve left (-2.8 at t=4.8 s) and right (+2.2 at t=8.5 s for overtake),
    # then settles to center (+0.3) for the hyper-boost run into the sunset sun.
    weave_left = -5.1 * math.exp(-((tf - 4.8) / 1.15) ** 2)
    overtake_right = 0.4 * math.exp(-((tf - 8.5) / 1.4) ** 2)
    center_boost = -2.0 / (1.0 + math.exp(-(tf - 10.6) * 2.2))
    return 2.3 + weave_left + overtake_right + center_boost


def rival_y(t):
    """Rival car Y(t): starts 15 units ahead, hero drafts and overtakes side-by-side at t = 8.5 s (frame 205)."""
    tf = float(t)
    hy = hero_y(tf)
    # At t=0: +15 u ahead; at t=5.0 s: +7.5 u ahead; at t=8.5 s (frame 205): 0.0 u (dead even!); at t=10.5 s: -6.5 u behind
    lead = 15.0 * (1.0 - tf / 8.5) - 14.0 / (1.0 + math.exp(-(tf - 10.8) * 1.8)) + 0.45
    return hy + lead


def rival_x(t):
    """Rival car lateral position X(t): holds left-center lane (-2.1) with subtle weave."""
    tf = float(t)
    return -2.1 + 0.45 * math.sin(tf * 0.8 + 0.3)


def car_kinematics(x_fn, y_fn, t):
    """Return (x, y, z, pitch, roll, yaw) at time t from finite differences."""
    eps = 0.02
    t0 = max(0.0, min(DURATION, float(t)))
    ta, tb = max(0.0, t0 - eps), min(DURATION, t0 + eps)
    dt = max(tb - ta, 1e-4)
    x, y = x_fn(t0), y_fn(t0)
    vx = (x_fn(tb) - x_fn(ta)) / dt
    vy = max((y_fn(tb) - y_fn(ta)) / dt, 1.0)
    ax = (x_fn(tb) - 2.0 * x + x_fn(ta)) / ((0.5 * dt) ** 2)
    yaw = -math.atan2(vx, vy) * 1.45
    roll = float(np.clip(-ax * 0.015 - vx * 0.022, -0.18, 0.18))
    boost_squat = 0.035 * math.exp(-((t0 - 10.7) / 0.9) ** 2) + 0.016 * math.exp(-((t0 - 0.8) / 0.7) ** 2)
    z = 0.015 * math.sin(t0 * 16.0)
    return x, y, z, boost_squat, roll, yaw


def _emissive_mat(name, color, strength):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color[:3], 1.0)
    em.inputs["Strength"].default_value = float(strength)
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def _pbr_mat(name, base_color, metallic=0.9, roughness=0.12, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_color[:3], 1.0)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    bsdf.inputs["Roughness"].default_value = float(roughness)
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = float(coat)
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


class _MultiMesh:
    """Builds a multi-material quad mesh cleanly from procedural boxes, prisms, and strips."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.mat_idx = []

    def quad(self, p0, p1, p2, p3, mat=0):
        base = len(self.verts)
        self.verts.extend((p0, p1, p2, p3))
        self.faces.append((base, base + 1, base + 2, base + 3))
        self.mat_idx.append(int(mat))

    def box(self, x0, x1, y0, y1, z0, z1, mat=0, top_mat=None):
        tm = mat if top_mat is None else top_mat
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), mat)
        self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), tm)
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), mat)
        self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), mat)
        self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), mat)
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), mat)

    def to_object(self, name, materials):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        for m in materials:
            mesh.materials.append(m)
        if self.faces:
            mesh.polygons.foreach_set("material_index", self.mat_idx)
        mesh.update()
        return bpy.data.objects.new(name, mesh)


def _build_wheel(name, mat_tire, mat_neon, is_left):
    """Build one 3D wheel centered at origin with glowing concentric synthwave rim rings and spokes."""
    mm = _MultiMesh()
    segs = 20
    r_outer = WHEEL_R
    r_rim = WHEEL_R * 0.72
    r_hub = WHEEL_R * 0.24
    w = 0.34
    x_out = -w * 0.5 if is_left else w * 0.5
    x_in = -x_out

    for i in range(segs):
        a0 = 2.0 * math.pi * i / segs
        a1 = 2.0 * math.pi * (i + 1) / segs
        y0, z0 = r_outer * math.cos(a0), r_outer * math.sin(a0)
        y1, z1 = r_outer * math.cos(a1), r_outer * math.sin(a1)
        ry0, rz0 = r_rim * math.cos(a0), r_rim * math.sin(a0)
        ry1, rz1 = r_rim * math.cos(a1), r_rim * math.sin(a1)
        hy0, hz0 = r_hub * math.cos(a0), r_hub * math.sin(a0)
        hy1, hz1 = r_hub * math.cos(a1), r_hub * math.sin(a1)

        mm.quad((x_in, y0, z0), (x_out, y0, z0), (x_out, y1, z1), (x_in, y1, z1), mat=0)
        mm.quad((x_out, ry0, rz0), (x_out, y0, z0), (x_out, y1, z1), (x_out, ry1, rz1), mat=0)
        spoke_mat = 1 if (i % 4 == 0) else 0
        mm.quad((x_out * 1.02, ry0 * 0.90, rz0 * 0.90), (x_out * 1.02, ry0, rz0),
                (x_out * 1.02, ry1, rz1), (x_out * 1.02, ry1 * 0.90, rz1 * 0.90), mat=1)
        mm.quad((x_out * 0.98, hy0, hz0), (x_out * 0.98, ry0 * 0.90, rz0 * 0.90),
                (x_out * 0.98, ry1 * 0.90, rz1 * 0.90), (x_out * 0.98, hy1, hz1), mat=spoke_mat)
        mm.quad((x_out * 1.03, 0.0, 0.0), (x_out * 1.03, hy0, hz0), (x_out * 1.03, hy1, hz1), (x_out * 1.03, 0.0, 0.0), mat=1)

    return mm.to_object(name, [mat_tire, mat_neon])


def build_wedge_car(scene, name, body_rgb, neon_rgb, tail_rgb):
    """Build a 1970s/80s synthwave wedge supercar with glowing neon trim, louvers, twin thrusters, and 4 child wheels."""
    mat_body = _pbr_mat(name + "_Body", body_rgb, metallic=0.92, roughness=0.11, coat=0.8)
    mat_glass = _pbr_mat(name + "_Glass", (0.01, 0.02, 0.05), metallic=0.85, roughness=0.04)
    mat_neon = _emissive_mat(name + "_Neon", neon_rgb, 20.0)
    mat_tail = _emissive_mat(name + "_Tail", tail_rgb, 34.0)
    mat_tire = _pbr_mat(name + "_Tire", (0.02, 0.02, 0.025), metallic=0.15, roughness=0.55)

    mm = _MultiMesh()
    profile = [
        (2.45, 0.92, 0.84, 0.20, 0.34, 0),
        (1.55, 1.08, 0.96, 0.20, 0.62, 0),
        (0.55, 1.12, 0.82, 0.22, 0.82, 1),
        (-0.55, 1.14, 0.78, 0.22, 1.16, 1),
        (-1.75, 1.18, 0.94, 0.26, 0.92, 0),
        (-2.45, 1.15, 1.02, 0.32, 0.84, 0),
    ]
    for i in range(len(profile) - 1):
        y0, wb0, wt0, zb0, zt0, _ = profile[i]
        y1, wb1, wt1, zb1, zt1, tm = profile[i + 1]
        mm.quad((-wt0, y0, zt0), (wt0, y0, zt0), (wt1, y1, zt1), (-wt1, y1, zt1), mat=tm)
        mm.quad((-wb0, y0, zb0), (-wb1, y1, zb1), (wb1, y1, zb1), (wb0, y0, zb0), mat=0)
        mm.quad((-wb0, y0, zb0), (-wt0, y0, zt0), (-wt1, y1, zt1), (-wb1, y1, zb1), mat=0)
        mm.quad((wb0, y0, zb0), (wb1, y1, zb1), (wt1, y1, zt1), (wt0, y0, zt0), mat=0)
        for sgn in (-1.0, 1.0):
            mm.quad((sgn * (wt0 + 0.015), y0, zt0 + 0.01), (sgn * (wt0 - 0.03), y0, zt0 + 0.01),
                    (sgn * (wt1 - 0.03), y1, zt1 + 0.01), (sgn * (wt1 + 0.015), y1, zt1 + 0.01), mat=2)
            mm.quad((sgn * (wb0 + 0.015), y0, zb0 + 0.05), (sgn * (wb0 + 0.015), y0, zb0 + 0.11),
                    (sgn * (wb1 + 0.015), y1, zb1 + 0.11), (sgn * (wb1 + 0.015), y1, zb1 + 0.05), mat=2)

    mm.quad((-0.92, 2.45, 0.20), (0.92, 2.45, 0.20), (0.84, 2.45, 0.34), (-0.84, 2.45, 0.34), mat=0)
    mm.box(-0.88, -0.32, 2.44, 2.47, 0.25, 0.32, mat=2)
    mm.box(0.32, 0.88, 2.44, 2.47, 0.25, 0.32, mat=2)
    mm.box(-0.94, 0.94, 2.43, 2.48, 0.17, 0.21, mat=2)

    for k in range(5):
        ly = -0.70 - k * 0.22
        lz = 1.12 - k * 0.045
        mm.box(-0.72, 0.72, ly - 0.04, ly + 0.04, lz, lz + 0.035, mat=0, top_mat=2)

    mm.box(-0.88, -0.80, -2.38, -2.05, 0.82, 1.24, mat=0)
    mm.box(0.80, 0.88, -2.38, -2.05, 0.82, 1.24, mat=0)
    mm.box(-1.16, 1.16, -2.44, -2.02, 1.22, 1.28, mat=0, top_mat=2)
    mm.box(-1.18, -1.14, -2.46, -1.98, 1.16, 1.32, mat=2)
    mm.box(1.14, 1.18, -2.46, -1.98, 1.16, 1.32, mat=2)

    mm.quad((-1.15, -2.45, 0.32), (-1.02, -2.45, 0.84), (1.02, -2.45, 0.84), (1.15, -2.45, 0.32), mat=0)
    mm.box(-1.02, 1.02, -2.48, -2.44, 0.64, 0.78, mat=3)
    mm.box(-0.72, -0.28, -2.54, -2.42, 0.36, 0.56, mat=3)
    mm.box(0.28, 0.72, -2.54, -2.42, 0.36, 0.56, mat=3)

    car = mm.to_object(name, [mat_body, mat_glass, mat_neon, mat_tail])
    scene.collection.objects.link(car)

    wheel_coords = (
        ("WheelFL", (-1.08, 1.42, WHEEL_R), True),
        ("WheelFR", (1.08, 1.42, WHEEL_R), False),
        ("WheelRL", (-1.12, -1.48, WHEEL_R), True),
        ("WheelRR", (1.12, -1.48, WHEEL_R), False),
    )
    for w_suffix, loc, is_left in wheel_coords:
        w_obj = _build_wheel("%s_%s" % (name, w_suffix), mat_tire, mat_neon, is_left)
        w_obj.parent = car
        w_obj.location = loc
        scene.collection.objects.link(w_obj)

    return car


def _add_highway_nodes(highway_obj):
    """Add a Geometry Nodes modifier ('HighwayNodes') that drives a 124 BPM synthwave mountain/gantry pulse."""
    tree = bpy.data.node_groups.new("HighwayNodes", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    pulse_sock = tree.interface.new_socket("BeatPhase", in_out="INPUT", socket_type="NodeSocketFloat")
    pulse_sock.default_value = 0.0

    nodes, links = tree.nodes, tree.links
    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    pos = nodes.new("GeometryNodeInputPosition")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(pos.outputs["Position"], sep.inputs["Vector"])

    abs_x = nodes.new("ShaderNodeMath")
    abs_x.operation = "ABSOLUTE"
    links.new(sep.outputs["X"], abs_x.inputs[0])

    sub_x = nodes.new("ShaderNodeMath")
    sub_x.operation = "SUBTRACT"
    sub_x.use_clamp = True
    links.new(abs_x.outputs["Value"], sub_x.inputs[0])
    sub_x.inputs[1].default_value = 14.5

    scaled_y = nodes.new("ShaderNodeMath")
    scaled_y.operation = "MULTIPLY_ADD"
    links.new(sep.outputs["Y"], scaled_y.inputs[0])
    scaled_y.inputs[1].default_value = 0.05
    links.new(gin.outputs["BeatPhase"], scaled_y.inputs[2])

    wave_y = nodes.new("ShaderNodeMath")
    wave_y.operation = "SINE"
    links.new(scaled_y.outputs["Value"], wave_y.inputs[0])

    dz = nodes.new("ShaderNodeMath")
    dz.operation = "MULTIPLY"
    links.new(sub_x.outputs["Value"], dz.inputs[0])
    links.new(wave_y.outputs["Value"], dz.inputs[1])

    dz_scaled = nodes.new("ShaderNodeMath")
    dz_scaled.operation = "MULTIPLY"
    links.new(dz.outputs["Value"], dz_scaled.inputs[0])
    dz_scaled.inputs[1].default_value = 0.08

    offset = nodes.new("ShaderNodeCombineXYZ")
    links.new(dz_scaled.outputs["Value"], offset.inputs["Z"])

    setp = nodes.new("GeometryNodeSetPosition")
    links.new(gin.outputs["Geometry"], setp.inputs["Geometry"])
    links.new(offset.outputs["Vector"], setp.inputs["Offset"])
    links.new(setp.outputs["Geometry"], gout.inputs["Geometry"])

    mod = highway_obj.modifiers.new("HighwayNodes", "NODES")
    mod.node_group = tree
    return mod


def _add_trail_nodes(trail_obj):
    """Add a Geometry Nodes modifier ('TrailNodes') that ripples and flares the plasma light-ribbons."""
    tree = bpy.data.node_groups.new("TrailNodes", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    boost_sock = tree.interface.new_socket("BoostFactor", in_out="INPUT", socket_type="NodeSocketFloat")
    boost_sock.default_value = 1.0

    nodes, links = tree.nodes, tree.links
    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    pos = nodes.new("GeometryNodeInputPosition")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(pos.outputs["Position"], sep.inputs["Vector"])

    freq = nodes.new("ShaderNodeMath")
    freq.operation = "MULTIPLY"
    links.new(sep.outputs["Y"], freq.inputs[0])
    freq.inputs[1].default_value = 0.65

    flutter = nodes.new("ShaderNodeMath")
    flutter.operation = "SINE"
    links.new(freq.outputs["Value"], flutter.inputs[0])

    amp = nodes.new("ShaderNodeMath")
    amp.operation = "MULTIPLY"
    links.new(flutter.outputs["Value"], amp.inputs[0])
    links.new(gin.outputs["BoostFactor"], amp.inputs[1])

    amp_z = nodes.new("ShaderNodeMath")
    amp_z.operation = "MULTIPLY"
    links.new(amp.outputs["Value"], amp_z.inputs[0])
    amp_z.inputs[1].default_value = 0.04

    offset = nodes.new("ShaderNodeCombineXYZ")
    links.new(amp_z.outputs["Value"], offset.inputs["Z"])

    setp = nodes.new("GeometryNodeSetPosition")
    links.new(gin.outputs["Geometry"], setp.inputs["Geometry"])
    links.new(offset.outputs["Vector"], setp.inputs["Offset"])
    links.new(setp.outputs["Geometry"], gout.inputs["Geometry"])

    mod = trail_obj.modifiers.new("TrailNodes", "NODES")
    mod.node_group = tree
    return mod


def build_highway_and_world(scene):
    """Build the wet-mirror neon highway, overhead speed-gantries, wireframe mountains, and OutRun sunset sun."""
    mat_road = _pbr_mat("WetAsphalt", (0.012, 0.010, 0.024), metallic=0.38, roughness=0.065, coat=0.9)
    mat_mtn = _pbr_mat("MountainRock", (0.022, 0.008, 0.045), metallic=0.25, roughness=0.35)
    mat_cyan = _emissive_mat("GridCyan", (0.0, 0.90, 1.0), 16.0)
    mat_mag = _emissive_mat("GridMagenta", (1.0, 0.06, 0.58), 18.0)
    mat_gold = _emissive_mat("SunGold", (1.0, 0.35, 0.06), 28.0)

    mm = _MultiMesh()
    y0, y1 = -140.0, HIGHWAY_LEN
    for y in np.arange(y0, y1, 16.0):
        yn = y + 16.0
        mm.quad((-13.0, y, 0.0), (13.0, y, 0.0), (13.0, yn, 0.0), (-13.0, yn, 0.0), mat=0)
        mm.quad((-12.6, y, 0.015), (12.6, y, 0.015), (12.6, y + 0.18, 0.015), (-12.6, y + 0.18, 0.015), mat=2)
        mm.quad((-0.22, y, 0.02), (0.22, y, 0.02), (0.22, yn, 0.02), (-0.22, yn, 0.02), mat=3)
        for lx in (-4.4, 4.4):
            mm.quad((lx - 0.12, y + 2.0, 0.02), (lx + 0.12, y + 2.0, 0.02),
                    (lx + 0.12, y + 11.0, 0.02), (lx - 0.12, y + 11.0, 0.02), mat=2)

    for sgn in (-1.0, 1.0):
        bx = sgn * 12.8
        mm.box(bx - 0.25, bx + 0.25, y0, y1, 0.0, 0.65, mat=0, top_mat=3)
        mm.box(bx - 0.30, bx + 0.30, y0, y1, 0.32, 0.46, mat=3)

    for k, gy in enumerate(np.arange(-40.0, y1, 36.0)):
        g_mat = 2 if (k % 2 == 0) else 3
        for sgn in (-1.0, 1.0):
            px = sgn * 13.6
            mm.box(px - 0.45, px + 0.45, gy - 0.5, gy + 0.5, 0.0, 9.5, mat=0)
            mm.box(px - sgn * 0.52, px - sgn * 0.38, gy - 0.22, gy + 0.22, 0.6, 9.2, mat=g_mat)
        mm.box(-14.0, 14.0, gy - 0.5, gy + 0.5, 9.2, 9.9, mat=0)
        mm.box(-13.4, 13.4, gy - 0.55, gy + 0.55, 9.0, 9.22, mat=g_mat)

    rng = np.random.default_rng(77)
    x_bands = [14.0, 26.0, 42.0, 62.0, 88.0]
    y_steps = np.arange(-120.0, y1 + 40.0, 28.0)
    for sgn in (-1.0, 1.0):
        z_grid = np.zeros((len(x_bands), len(y_steps)))
        for ix, xb in enumerate(x_bands):
            if ix > 0:
                base_h = (ix ** 1.35) * 8.5
                z_grid[ix] = base_h + rng.uniform(1.5, 14.0, size=len(y_steps))
        for ix in range(len(x_bands) - 1):
            for iy in range(len(y_steps) - 1):
                xa, xb = sgn * x_bands[ix], sgn * x_bands[ix + 1]
                ya, yb = y_steps[iy], y_steps[iy + 1]
                p00 = (xa, ya, z_grid[ix, iy])
                p10 = (xb, ya, z_grid[ix + 1, iy])
                p11 = (xb, yb, z_grid[ix + 1, iy + 1])
                p01 = (xa, yb, z_grid[ix, iy + 1])
                mm.quad(p00, p10, p11, p01, mat=1)
                w_mat = 3 if (ix % 2 == 0) else 2
                mm.quad((p10[0], p10[1], p10[2] + 0.08), (p11[0], p11[1], p11[2] + 0.08),
                        (p11[0] - sgn * 0.45, p11[1], p11[2] + 0.02), (p10[0] - sgn * 0.45, p10[1], p10[2] + 0.02), mat=w_mat)

    # Segmented OutRun sunset sun positioned right at the end of the race corridor so it looms large in every forward shot
    sun_y = 1850.0
    sun_r = 160.0
    sun_z0 = 34.0
    for band in range(11):
        f0 = -0.65 + band * 0.13
        f1 = f0 + 0.095
        za, zb = sun_z0 + f0 * sun_r, sun_z0 + f1 * sun_r
        wa = sun_r * math.sqrt(max(0.0, 1.0 - f0 * f0))
        wb = sun_r * math.sqrt(max(0.0, 1.0 - f1 * f1))
        s_mat = 4 if band >= 4 else 3
        mm.quad((-wa, sun_y, za), (wa, sun_y, za), (wb, sun_y, zb), (-wb, sun_y, zb), mat=s_mat)

    highway = mm.to_object("SynthHighway", [mat_road, mat_mtn, mat_cyan, mat_mag, mat_gold])
    scene.collection.objects.link(highway)
    _add_highway_nodes(highway)
    return highway


def build_plasma_trails_and_fx(scene, hero_car, rival_car):
    """Build procedural Tron-style plasma light-ribbons behind both cars plus the frame-253 boost shockwave ring."""
    mat_cyan_trail = _emissive_mat("HeroTrailMat", (0.0, 0.92, 1.0), 30.0)
    mat_crim_trail = _emissive_mat("RivalTrailMat", (1.0, 0.18, 0.04), 26.0)
    mat_shock = _emissive_mat("ShockwaveMat", (0.35, 0.95, 1.0), 42.0)

    # Keep trails 3.2 units long behind the dual thrusters so they glow brightly behind the rear tires without crossing the chase cameras
    for parent_car, t_name, mat in ((hero_car, "PlasmaTrails", mat_cyan_trail), (rival_car, "RivalTrails", mat_crim_trail)):
        mm = _MultiMesh()
        segs = 14
        trail_len = 3.2
        for nozzle_x in (-0.52, 0.52):
            for i in range(segs):
                u0, u1 = i / segs, (i + 1) / segs
                y0 = -2.48 - u0 * trail_len
                y1 = -2.48 - u1 * trail_len
                h0 = 0.18 * (1.0 - 0.80 * u0)
                h1 = 0.18 * (1.0 - 0.80 * u1)
                w0 = 0.16 * (1.0 - 0.75 * u0)
                w1 = 0.16 * (1.0 - 0.75 * u1)
                mm.quad((nozzle_x - w0, y0, 0.42), (nozzle_x + w0, y0, 0.42),
                        (nozzle_x + w1, y1, 0.42), (nozzle_x - w1, y1, 0.42), mat=0)
                mm.quad((nozzle_x, y0, 0.42 - h0), (nozzle_x, y0, 0.42 + h0),
                        (nozzle_x, y1, 0.42 + h1), (nozzle_x, y1, 0.42 - h1), mat=0)
        obj = mm.to_object(t_name, [mat])
        obj.parent = parent_car
        scene.collection.objects.link(obj)
        _add_trail_nodes(obj)

    sm = _MultiMesh()
    ring_segs = 28
    for i in range(ring_segs):
        a0 = 2.0 * math.pi * i / ring_segs
        a1 = 2.0 * math.pi * (i + 1) / ring_segs
        for r_in, r_out in ((1.0, 1.32), (1.55, 1.72)):
            x0, z0 = r_in * math.cos(a0), r_in * math.sin(a0)
            x1, z1 = r_in * math.cos(a1), r_in * math.sin(a1)
            X0, Z0 = r_out * math.cos(a0), r_out * math.sin(a0)
            X1, Z1 = r_out * math.cos(a1), r_out * math.sin(a1)
            sm.quad((x0, 0.0, z0), (X0, 0.0, Z0), (X1, 0.0, Z1), (x1, 0.0, z1), mat=0)
    shock = sm.to_object("BoostShockwave", [mat_shock])
    scene.collection.objects.link(shock)
    return shock


def _setup_cameras_and_markers(scene):
    """Create the 4 shot cameras and timeline markers, plus the primary active Camera."""
    scene.timeline_markers.clear()
    cams = {}
    for frame, name in SHOT_CUTS:
        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = 35.0
        cam_data.clip_start = 0.05
        cam_data.clip_end = 4000.0
        cam_obj = bpy.data.objects.new(name, cam_data)
        scene.collection.objects.link(cam_obj)
        cams[name] = cam_obj
        scene.timeline_markers.new(name, frame=frame)

    master_data = bpy.data.cameras.new("Camera")
    master_data.lens = 35.0
    master_data.clip_start = 0.05
    master_data.clip_end = 4000.0
    master = bpy.data.objects.new("Camera", master_data)
    scene.collection.objects.link(master)
    scene.camera = master
    return cams, master


def _look_at_quat(cam_pos, target_pos, roll_angle=0.0):
    """Compute Euler XYZ rotation for a Blender camera at cam_pos looking at target_pos with optional Dutch roll."""
    from mathutils import Matrix, Vector
    eye = Vector(cam_pos)
    target = Vector(target_pos)
    forward = (target - eye).normalized()
    world_up = Vector((math.sin(roll_angle), 0.0, math.cos(roll_angle))).normalized()
    right = forward.cross(world_up).normalized()
    up = right.cross(forward).normalized()
    rot_mat = Matrix((
        (right.x, up.x, -forward.x),
        (right.y, up.y, -forward.y),
        (right.z, up.z, -forward.z),
    ))
    eul = rot_mat.to_euler("XYZ")
    return (float(eul.x), float(eul.y), float(eul.z))


def shot_camera_pose(frame):
    """Return (shot_name, cam_pos, look_target, lens_mm, roll_rad) for frame 1..360 (supports float subframes)."""
    t = (float(frame) - FRAME_START) / FPS
    hx, hy, hz, _, h_roll, _ = car_kinematics(hero_x, hero_y, t)
    rx, ry, rz, _, _, _ = car_kinematics(rival_x, rival_y, t)

    if frame < 84.5:
        # Shot 1 (Frames 1..84): Low Rear-Quarter Wheel/Exhaust Launch Cam showing full HeroRacer + RivalRacer ahead
        u = max(0.0, min(1.0, (float(frame) - 1.0) / 83.0))
        cam_pos = (hx - 2.35 + 0.55 * u, hy - 5.6 + 0.4 * u, 0.92 + 0.22 * u)
        target = (hx - 0.25, hy + 2.5, 0.72)
        return "CamLaunch", cam_pos, target, 32.0, 0.03 * (1.0 - u)
    if frame < 168.5:
        # Shot 2 (Frames 85..168): Sweeping Helicopter Aerial Orbit Cam over both cars and their light-ribbons
        u = max(0.0, min(1.0, (float(frame) - 85.0) / 83.0))
        sweep_x = hx + 4.4 * math.cos(u * math.pi * 0.9)
        cam_pos = (sweep_x, hy - 10.2 + 1.8 * u, 4.9 - 1.5 * u)
        target = (0.65 * hx + 0.35 * rx, hy + 3.8, 0.68)
        return "CamHeli", cam_pos, target, 34.0, -h_roll * 0.55
    if frame < 252.5:
        # Shot 3 (Frames 169..252): Dynamic Front-3/4 Overtake Cam looking across both wedge supercars
        u = max(0.0, min(1.0, (float(frame) - 169.0) / 83.0))
        mid_x = 0.5 * (hx + rx)
        lead_y = max(hy, ry)
        cam_pos = (hx + 3.4 - 0.8 * u, lead_y + 4.8 - 2.2 * u, 1.85 - 0.35 * u)
        target = (mid_x - 0.2, 0.5 * (hy + ry) - 0.8, 0.62)
        return "CamOvertake", cam_pos, target, 32.0, -h_roll * 0.4
    # Shot 4 (Frames 253..360): Low Center Chase Cam -> Wide-FOV Hyper-Boost into the Segmented Sun
    u = max(0.0, min(1.0, (float(frame) - 253.0) / 107.0))
    s = u * u * (3.0 - 2.0 * u)
    cam_pos = (hx * 0.85, hy - 6.0 - 1.2 * s, 1.25 - 0.18 * s)
    target = (hx * 0.35, hy + 18.0, 1.10 + 0.6 * s)
    lens = 35.0 - 15.0 * s  # widens smoothly from 35 mm down to 20 mm as boost ignites
    return "CamBoost", cam_pos, target, lens, h_roll * 0.35


def _add_racer_hud(scene, master_cam):
    """Add an in-camera 3D Synthwave Telemetry HUD close to the camera aperture so rotation never motion-blurs it."""
    from src.gauge import BAR_W, CORNER, _backing, _frame, _material, _strip

    for name in list(bpy.data.objects.keys()):
        if name.startswith("RacerHUD") or name.startswith("Gauge"):
            bpy.data.objects.remove(bpy.data.objects[name])

    # Place HUD 20x closer to the camera pinhole (depth_scale = 0.05 -> z = -0.25) so camera rotation velocity is tiny
    rig = bpy.data.objects.new("RacerHUD_Rig", None)
    rig.parent = master_cam
    scene.collection.objects.link(rig)

    x, y, z = CORNER
    curve = bpy.data.curves.new("GaugeText", "FONT")
    curve.size = 0.092
    curve.materials.append(_material("RacerHUD_TextMat", 1.15))
    text = bpy.data.objects.new("GaugeText", curve)
    text.parent = rig
    text.location = (x, y, z)
    scene.collection.objects.link(text)

    bar_y = y - 0.24
    track = _strip(scene, rig, "GaugeTrack", (x, bar_y, z), 0.03, _material("RacerHUD_TrackMat", 0.18))
    track.scale.x = BAR_W
    _strip(scene, rig, "GaugeBar", (x, bar_y, z + 0.01), 0.03, _material("RacerHUD_BarMat", 1.25))
    panel_mat = _backing("RacerHUD_PanelMat")
    mix_nodes = [n for n in panel_mat.node_tree.nodes if n.type == "MIX_SHADER"]
    if mix_nodes:
        mix_nodes[0].inputs["Fac"].default_value = 0.96
    panel = _strip(scene, rig, "GaugePanel", (x - 0.08, bar_y - 0.03, z - 0.05), 0.39, panel_mat)
    panel.scale.x = BAR_W + 0.16
    _frame(scene, rig, "GaugeFrame", (x - 0.08, bar_y - 0.03, z - 0.04), BAR_W + 0.16, 0.39,
           _material("RacerHUD_FrameMat", 1.15))

    def _on_racer_frame(scn, depsgraph=None):
        if "GaugeText" not in bpy.data.objects or "GaugeBar" not in bpy.data.objects:
            return
        t = time_of(scn.frame_current)
        b = float(beta_at(t))
        kmh = hero_kmh(t)
        bpy.data.objects["GaugeText"].data.body = "%3.0f KM/H\nβ=%.3fc γ=%.1f" % (kmh, b, gamma(b))
        bpy.data.objects["GaugeBar"].scale.x = BAR_W * b

    bpy.app.handlers.frame_change_pre[:] = [
        h for h in bpy.app.handlers.frame_change_pre if getattr(h, "__name__", "") != "_on_racer_frame"
    ]
    bpy.app.handlers.frame_change_pre.append(_on_racer_frame)
    _on_racer_frame(scene)
    return rig


def animate_racer_scene(scene, hero_car, rival_car, highway, shockwave, cams, master_cam, hud_rig):
    """Keyframe cars, spinning wheels, Geometry Nodes inputs, boost shockwave, and shutter-safe camera cuts."""
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, FRAME_END

    h_wheels = [o for o in hero_car.children if "Wheel" in o.name]
    r_wheels = [o for o in rival_car.children if "Wheel" in o.name]
    hw_mod = highway.modifiers["HighwayNodes"]
    hw_key = hw_mod.node_group.interface.items_tree["BeatPhase"].identifier
    tr_obj = bpy.data.objects["PlasmaTrails"]
    tr_mod = tr_obj.modifiers["TrailNodes"]
    tr_key = tr_mod.node_group.interface.items_tree["BoostFactor"].identifier

    depth_scale = 0.05  # puts the HUD at z = -0.25 u in front of the lens

    def _key_cam(c_obj, f_val, cpos, ceul, clens):
        c_obj.location = cpos
        c_obj.rotation_euler = ceul
        c_obj.data.lens = clens
        c_obj.keyframe_insert(data_path="location", frame=f_val)
        c_obj.keyframe_insert(data_path="rotation_euler", frame=f_val)
        c_obj.data.keyframe_insert(data_path="lens", frame=f_val)

    def _key_hud(f_val, clens):
        xy_s = depth_scale * (50.0 / max(float(clens), 1.0))
        hud_rig.scale = (xy_s, xy_s, depth_scale)
        hud_rig.keyframe_insert(data_path="scale", frame=f_val)

    for f in range(FRAME_START, FRAME_END + 1):
        t = time_of(f)
        hx, hy, hz, hpitch, hroll, hyaw = car_kinematics(hero_x, hero_y, t)
        rx, ry, rz, rpitch, rroll, ryaw = car_kinematics(rival_x, rival_y, t)

        hero_car.location = (hx, hy, hz)
        hero_car.rotation_euler = (hpitch, hroll, hyaw)
        hero_car.keyframe_insert(data_path="location", frame=f)
        hero_car.keyframe_insert(data_path="rotation_euler", frame=f)

        rival_car.location = (rx, ry, rz)
        rival_car.rotation_euler = (rpitch, rroll, ryaw)
        rival_car.keyframe_insert(data_path="location", frame=f)
        rival_car.keyframe_insert(data_path="rotation_euler", frame=f)

        h_ang = -hy / WHEEL_R
        r_ang = -ry / WHEEL_R
        for w in h_wheels:
            w.rotation_euler = (h_ang, 0.0, 0.0)
            w.keyframe_insert(data_path="rotation_euler", frame=f)
        for w in r_wheels:
            w.rotation_euler = (r_ang, 0.0, 0.0)
            w.keyframe_insert(data_path="rotation_euler", frame=f)

        hw_mod[hw_key] = float(t * (124.0 / 60.0) * 2.0 * math.pi)
        highway.keyframe_insert(data_path='modifiers["HighwayNodes"]["%s"]' % hw_key, frame=f)
        boost_fac = 1.0 + 2.5 / (1.0 + math.exp(-(t - 10.5) * 4.0))
        tr_mod[tr_key] = float(boost_fac)
        tr_obj.keyframe_insert(data_path='modifiers["TrailNodes"]["%s"]' % tr_key, frame=f)

        if 253 <= f <= 305:
            su = (f - 253) / 52.0
            sc = 0.6 + 14.0 * su
            shockwave.location = (hx, hy - 1.5 - 12.0 * su, 0.85)
            shockwave.scale = (sc, 1.0, sc)
        else:
            shockwave.location = (hx, hy - 50.0, -20.0)
            shockwave.scale = (0.001, 0.001, 0.001)
        shockwave.keyframe_insert(data_path="location", frame=f)
        shockwave.keyframe_insert(data_path="scale", frame=f)

        shot_name, cpos, ctarget, clens, croll = shot_camera_pose(f)
        ceul = _look_at_quat(cpos, ctarget, croll)
        _key_cam(cams[shot_name], f, cpos, ceul, clens)
        _key_cam(master_cam, f, cpos, ceul, clens)
        _key_hud(f, clens)

        # Insert shutter guard keyframes at f + 0.45 before and f - 0.45 after each camera cut so motion blur
        # (shutter = 0.35 -> [f - 0.175, f + 0.175]) never interpolates across two different cameras!
        if f in (84, 168, 252):
            _, cpos_a, ctarget_a, clens_a, croll_a = shot_camera_pose(f + 0.45)
            _key_cam(master_cam, f + 0.45, cpos_a, _look_at_quat(cpos_a, ctarget_a, croll_a), clens_a)
            _key_hud(f + 0.45, clens_a)
            _, cpos_b, ctarget_b, clens_b, croll_b = shot_camera_pose(f + 0.55)
            _key_cam(master_cam, f + 0.55, cpos_b, _look_at_quat(cpos_b, ctarget_b, croll_b), clens_b)
            _key_hud(f + 0.55, clens_b)

    for ob in [hero_car, rival_car, highway, tr_obj, shockwave, master_cam, hud_rig, *cams.values(), *h_wheels, *r_wheels]:
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    for c_obj in [master_cam, *cams.values()]:
        if c_obj.data.animation_data and c_obj.data.animation_data.action:
            for fc in c_obj.data.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    scene.frame_set(FRAME_START)


def build_racer_scene():
    """Build the complete native Blender Synthwave Neon Racer scene and return `scene`."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.denoising_use_gpu = True
    scene.cycles.denoising_prefilter = "NONE"
    scene.cycles.denoising_input_passes = "RGB"
    scene.render.use_persistent_data = True
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 2
    scene.cycles.volume_bounces = 0
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.35
    scene.view_settings.view_transform = "AgX"

    world = bpy.data.worlds.new("SynthWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.010, 0.004, 0.022, 1.0)
    bg.inputs["Strength"].default_value = 0.85
    scene.world = world

    highway = build_highway_and_world(scene)
    hero_car = build_wedge_car(scene, "HeroRacer", (0.14, 0.24, 0.42), (0.0, 0.92, 1.0), (1.0, 0.08, 0.45))
    rival_car = build_wedge_car(scene, "RivalRacer", (0.42, 0.08, 0.14), (1.0, 0.28, 0.04), (1.0, 0.45, 0.0))

    # Attach a soft follow key-light above the cars so their wedge bodywork gleams from both front and rear angles
    light_data = bpy.data.lights.new("CarKeyLight", type="POINT")
    light_data.energy = 900.0
    light_data.color = (0.65, 0.85, 1.0)
    light_data.shadow_soft_size = 2.5
    light_obj = bpy.data.objects.new("CarKeyLight", light_data)
    light_obj.parent = hero_car
    light_obj.location = (-1.2, 0.5, 4.2)
    scene.collection.objects.link(light_obj)

    shockwave = build_plasma_trails_and_fx(scene, hero_car, rival_car)
    cams, master_cam = _setup_cameras_and_markers(scene)
    hud_rig = _add_racer_hud(scene, master_cam)
    animate_racer_scene(scene, hero_car, rival_car, highway, shockwave, cams, master_cam, hud_rig)
    return scene
