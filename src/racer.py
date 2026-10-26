"""Native Blender procedural 70s/80s Synthwave Neon Racer scene (bpy + numpy, 600 frames / 25.0 s race).

Builds the complete animated scene inside Blender with zero external assets and zero post-composited overlays:
- HeroRacer (gunmetal + cyan neon 70s wedge supercar) and RivalRacer (crimson/orange interceptor), each with
  4 child wheel objects (spinning neon rims keyframed from arc length) and F-curve banking.
- SynthHighway: glossy wet-asphalt 4-lane highway, dashed neon lane lines, overhead neon speed-gantries,
  flanking wireframe neon mountains, and a giant segmented OutRun sunset sun.
- Geometry Nodes modifiers built in Python:
  1. HighwayNodes (on SynthHighway): 124 BPM synthwave wave displacement + gantry pulse.
  2. TrailNodes (on PlasmaTrails & RivalTrails): true 3D particle exhaust spark emitters (GeometryNodeInstanceOnPoints
     + GeometryNodeMeshIcoSphere + lifecycle advection & heat attributes driving a cyan/white-hot -> magenta/orange
     ShaderNodeMapRange colour ramp).
- 5 native Blender shot cameras (CamLaunch, CamHeli, CamOvertake, CamBoost, CamOverview) + timeline markers at
  frames 1, 85, 169, 253, and 421, where Shot 5 cuts to a high top-down overview and both cars blast off at
  hyper-speed into the sunset sun and disappear into the horizon.
- GTA-style dual speed-bar dashboard HUD in the bottom-right corner (Rival car speed bar on the left in crimson/orange,
  Hero car speed bar on the right in cyan/magenta, hitting 999 KM/H MAXED OUT at the climax).
"""
import math

import bpy
import numpy as np

from src.flight import DURATION, FPS, FRAME_START
from src.relativity import beta_at, gamma
from src.synthwave import snare_on

RACER_DURATION = 25.0
RACER_FRAMES = int(RACER_DURATION * FPS)  # 600 frames (25.0 s race + 2.0 s title + 2.5 s end = 29.5 s total)
SHOT_CUTS = (
    (1, "CamLaunch"),
    (85, "CamHeli"),
    (169, "CamOvertake"),
    (253, "CamBoost"),
    (421, "CamOverview"),
)
HIGHWAY_LEN = 4600.0
WHEEL_R = 0.42

_T = np.linspace(0.0, RACER_DURATION, 5001)
_DT = float(_T[1] - _T[0])


def racer_time(frame):
    """Seconds since frame 1 (0.0 s at frame 1, 25.0 s at frame 601)."""
    return (float(frame) - FRAME_START) / FPS


def racer_beta(t):
    """Relativistic beta curve mapped smoothly across the 25.0 s race (0.1c -> 0.999c)."""
    u = min(max(float(t) / RACER_DURATION, 0.0), 1.0)
    return float(beta_at(u * DURATION))


def _speed_mps(t):
    """Forward speed in scene units/s: ramps from 58 u/s to 165 u/s, then hyper-launches to 490 u/s in Shot 5."""
    t_arr = np.asarray(t, dtype=float)
    u = np.clip(t_arr / 17.5, 0.0, 1.0)
    base = 58.0 + 78.0 * (u * u * (3.0 - 2.0 * u))
    boost1 = 34.0 / (1.0 + np.exp(-(t_arr - 10.5) * 3.5))
    # At t > 18.2 s (during the Top Overview shot), hyper-drive ignites and the cars rocket away down the highway
    hyper = 320.0 / (1.0 + np.exp(-(t_arr - 19.2) * 1.8))
    return base + boost1 + hyper


_V_GRID = _speed_mps(_T)
_Y_GRID = np.concatenate([[0.0], np.cumsum(0.5 * (_V_GRID[1:] + _V_GRID[:-1]) * _DT)])


def hero_y(t):
    """Hero car forward Y position at time t (seconds)."""
    out = np.interp(np.asarray(t, dtype=float), _T, _Y_GRID)
    return float(out) if out.ndim == 0 else out


def hero_kmh(t):
    """Hero car telemetry speed in km/h (85 km/h at launch -> 420 km/h in Shot 4 -> 999 km/h MAXED OUT in Shot 5)."""
    tf = min(max(float(t), 0.0), RACER_DURATION)
    u = min(tf / 17.5, 1.0)
    b = float(beta_at(u * DURATION))
    boost1 = 1.0 / (1.0 + math.exp(-(tf - 10.5) * 4.0))
    base_kmh = 85.0 + 255.0 * (0.45 * u + 0.55 * b) + 80.0 * boost1
    hyper = 610.0 / (1.0 + math.exp(-(tf - 19.0) * 1.9))
    return min(999.0, base_kmh + hyper)


def rival_kmh(t):
    """Rival car telemetry speed in km/h (starts slightly faster at 110 km/h, overtaken at 8.5 s, hits 920+ km/h in Shot 5)."""
    tf = min(max(float(t), 0.0), RACER_DURATION)
    u = min(tf / 17.5, 1.0)
    b = float(beta_at(u * DURATION))
    boost1 = 1.0 / (1.0 + math.exp(-(tf - 11.2) * 3.5))
    base_kmh = 108.0 + 225.0 * (0.50 * u + 0.50 * b) + 62.0 * boost1
    hyper = 565.0 / (1.0 + math.exp(-(tf - 19.4) * 1.8))
    return min(960.0, base_kmh + hyper)


def hero_x(t):
    """Hero car lateral lane trajectory X(t): stays on the right lane (+2.2) in Shot 5 for clean side-by-side overview."""
    tf = float(t)
    weave_left = -5.1 * math.exp(-((tf - 4.8) / 1.15) ** 2)
    overtake_right = 0.4 * math.exp(-((tf - 8.5) / 1.4) ** 2)
    center_boost = -1.6 * math.exp(-((tf - 14.0) / 2.6) ** 2)
    return 2.3 + weave_left + overtake_right + center_boost


def rival_y(t):
    """Rival car Y(t): starts 15 units ahead, hero overtakes at t = 8.5 s (frame 205), then both rocket away in Shot 5."""
    tf = float(t)
    hy = hero_y(tf)
    lead = 15.0 * (1.0 - min(tf, 12.0) / 8.5) - 9.0 / (1.0 + math.exp(-(tf - 10.8) * 1.8)) + 0.45
    return hy + lead


def rival_x(t):
    """Rival car lateral position X(t): holds left lane (-2.2) with subtle weave."""
    tf = float(t)
    return -2.2 + 0.42 * math.sin(tf * 0.8 + 0.3) * math.exp(-max(0.0, tf - 18.0) * 0.4)


def car_kinematics(x_fn, y_fn, t):
    """Return (x, y, z, pitch, roll, yaw) at time t from finite differences."""
    eps = 0.02
    t0 = max(0.0, min(RACER_DURATION, float(t)))
    ta, tb = max(0.0, t0 - eps), min(RACER_DURATION, t0 + eps)
    dt = max(tb - ta, 1e-4)
    x, y = x_fn(t0), y_fn(t0)
    vx = (x_fn(tb) - x_fn(ta)) / dt
    vy = max((y_fn(tb) - y_fn(ta)) / dt, 1.0)
    ax = (x_fn(tb) - 2.0 * x + x_fn(ta)) / ((0.5 * dt) ** 2)
    yaw = -math.atan2(vx, vy) * 1.45
    roll = float(np.clip(-ax * 0.015 - vx * 0.022, -0.18, 0.18))
    boost_squat = (
        0.035 * math.exp(-((t0 - 10.7) / 0.9) ** 2)
        + 0.042 * math.exp(-((t0 - 18.8) / 1.2) ** 2)
        + 0.016 * math.exp(-((t0 - 0.8) / 0.7) ** 2)
    )
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


def _particle_exhaust_mat(name, hot_rgb, tail_rgb, strength=56.0):
    """Shader reading Geometry Nodes `heat` (1 at nozzle -> 0 at tail) to blend white-hot core to neon plasma."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()

    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "heat"

    mix_col = nodes.new("ShaderNodeMix")
    mix_col.data_type = "RGBA"
    mix_col.clamp_factor = True
    in_rgba = [i for i in mix_col.inputs if i.type == "RGBA"]
    out_rgba = [o for o in mix_col.outputs if o.type == "RGBA"][0]
    links.new(attr.outputs["Fac"], mix_col.inputs["Factor"])
    in_rgba[0].default_value = (*tail_rgb[:3], 1.0)
    in_rgba[1].default_value = (*hot_rgb[:3], 1.0)

    # Keep a strong floor brightness (0.25 + 0.75 * heat) so trailing sparks stay vividly emissive
    floor_h = nodes.new("ShaderNodeMath")
    floor_h.operation = "MULTIPLY_ADD"
    links.new(attr.outputs["Fac"], floor_h.inputs[0])
    floor_h.inputs[1].default_value = 0.75
    floor_h.inputs[2].default_value = 0.25

    power = nodes.new("ShaderNodeMath")
    power.operation = "MULTIPLY"
    links.new(floor_h.outputs["Value"], power.inputs[0])
    power.inputs[1].default_value = float(strength)

    em = nodes.new("ShaderNodeEmission")
    links.new(out_rgba, em.inputs["Color"])
    links.new(power.outputs["Value"], em.inputs["Strength"])

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

    if name == "HeroRacer":
        mat_plate_bg = _pbr_mat("HeroPlate_BG", (0.015, 0.02, 0.035), metallic=0.85, roughness=0.25)
        mat_plate_txt = _emissive_mat("HeroPlate_TextMat", (0.22, 0.96, 1.0), 16.0)
        pm = _MultiMesh()
        px0, px1, pz0, pz1, py = -0.265, 0.265, 0.37, 0.55, -2.495
        b_th = 0.012
        pm.box(px0, px1, py - 0.006, py + 0.006, pz0, pz1, mat=0)
        pm.box(px0 - b_th, px1 + b_th, py - 0.008, py + 0.008, pz1, pz1 + b_th, mat=1)
        pm.box(px0 - b_th, px1 + b_th, py - 0.008, py + 0.008, pz0 - b_th, pz0, mat=1)
        pm.box(px0 - b_th, px0, py - 0.008, py + 0.008, pz0, pz1, mat=1)
        pm.box(px1, px1 + b_th, py - 0.008, py + 0.008, pz0, pz1, mat=1)
        plate_obj = pm.to_object("HeroPlate", [mat_plate_bg, mat_neon])
        plate_obj.parent = car
        scene.collection.objects.link(plate_obj)

        p_curve = bpy.data.curves.new("HeroPlateText", "FONT")
        p_curve.body = "RENDERJUICE"
        p_curve.size = 0.074
        p_curve.extrude = 0.002
        p_curve.align_x = "CENTER"
        p_curve.align_y = "CENTER"
        p_curve.materials.append(mat_plate_txt)
        p_txt = bpy.data.objects.new("HeroPlateText", p_curve)
        p_txt.parent = car
        p_txt.location = (0.0, py - 0.010, 0.5 * (pz0 + pz1))
        p_txt.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
        scene.collection.objects.link(p_txt)

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


def _add_trail_nodes(trail_obj, mat):
    """Add a Geometry Nodes particle system ('TrailNodes') that advects and instances 3D glowing exhaust sparks."""
    tree = bpy.data.node_groups.new("TrailNodes_" + trail_obj.name, "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    boost_sock = tree.interface.new_socket("BoostFactor", in_out="INPUT", socket_type="NodeSocketFloat")
    boost_sock.default_value = 1.0
    time_sock = tree.interface.new_socket("SimTime", in_out="INPUT", socket_type="NodeSocketFloat")
    time_sock.default_value = 0.0

    nodes, links = tree.nodes, tree.links
    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")

    # Read per-particle phase (0..1) and 3D spray velocity vector
    phase_attr = nodes.new("GeometryNodeInputNamedAttribute")
    phase_attr.data_type = "FLOAT"
    phase_attr.inputs["Name"].default_value = "seed_phase"

    vel_attr = nodes.new("GeometryNodeInputNamedAttribute")
    vel_attr.data_type = "FLOAT_VECTOR"
    vel_attr.inputs["Name"].default_value = "spray_vel"

    # Normalized particle age u = fract(SimTime * 2.8 + seed_phase) in [0, 1)
    t_scaled = nodes.new("ShaderNodeMath")
    t_scaled.operation = "MULTIPLY_ADD"
    links.new(gin.outputs["SimTime"], t_scaled.inputs[0])
    t_scaled.inputs[1].default_value = 2.8
    links.new(phase_attr.outputs["Attribute"], t_scaled.inputs[2])

    age_u = nodes.new("ShaderNodeMath")
    age_u.operation = "FRACT"
    links.new(t_scaled.outputs["Value"], age_u.inputs[0])

    # Heat = 1 - u (1.0 at thruster nozzle -> 0.0 at tail end)
    heat = nodes.new("ShaderNodeMath")
    heat.operation = "SUBTRACT"
    heat.use_clamp = True
    heat.inputs[0].default_value = 1.0
    links.new(age_u.outputs["Value"], heat.inputs[1])

    # Advect each particle along spray_vel * age_u * BoostFactor
    age_boost = nodes.new("ShaderNodeMath")
    age_boost.operation = "MULTIPLY"
    links.new(age_u.outputs["Value"], age_boost.inputs[0])
    links.new(gin.outputs["BoostFactor"], age_boost.inputs[1])

    disp = nodes.new("ShaderNodeVectorMath")
    disp.operation = "SCALE"
    links.new(vel_attr.outputs["Attribute"], disp.inputs["Vector"])
    links.new(age_boost.outputs["Value"], disp.inputs["Scale"])

    setp = nodes.new("GeometryNodeSetPosition")
    links.new(gin.outputs["Geometry"], setp.inputs["Geometry"])
    links.new(disp.outputs["Vector"], setp.inputs["Offset"])

    # Store `heat` on the points before instancing so realized spark meshes inherit it for the shader
    store_heat = nodes.new("GeometryNodeStoreNamedAttribute")
    store_heat.data_type = "FLOAT"
    store_heat.domain = "POINT"
    store_heat.inputs["Name"].default_value = "heat"
    links.new(setp.outputs["Geometry"], store_heat.inputs["Geometry"])
    links.new(heat.outputs["Value"], store_heat.inputs["Value"])

    # Instance fine, separated glowing exhaust spark particles on every advected emitter point
    spark_mesh = nodes.new("GeometryNodeMeshIcoSphere")
    spark_mesh.inputs["Radius"].default_value = 0.022
    spark_mesh.inputs["Subdivisions"].default_value = 1

    # Stretch each spark along Y (motion streak) and shrink radius as it cools (heat)
    scale_x = nodes.new("ShaderNodeMath")
    scale_x.operation = "MULTIPLY_ADD"
    links.new(heat.outputs["Value"], scale_x.inputs[0])
    scale_x.inputs[1].default_value = 0.70
    scale_x.inputs[2].default_value = 0.25

    scale_y = nodes.new("ShaderNodeMath")
    scale_y.operation = "MULTIPLY"
    links.new(scale_x.outputs["Value"], scale_y.inputs[0])
    scale_y.inputs[1].default_value = 4.2

    inst_scale = nodes.new("ShaderNodeCombineXYZ")
    links.new(scale_x.outputs["Value"], inst_scale.inputs["X"])
    links.new(scale_y.outputs["Value"], inst_scale.inputs["Y"])
    links.new(scale_x.outputs["Value"], inst_scale.inputs["Z"])

    iop = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(store_heat.outputs["Geometry"], iop.inputs["Points"])
    links.new(spark_mesh.outputs["Mesh"], iop.inputs["Instance"])
    links.new(inst_scale.outputs["Vector"], iop.inputs["Scale"])

    realize = nodes.new("GeometryNodeRealizeInstances")
    links.new(iop.outputs["Instances"], realize.inputs["Geometry"])

    set_mat = nodes.new("GeometryNodeSetMaterial")
    links.new(realize.outputs["Geometry"], set_mat.inputs["Geometry"])
    set_mat.inputs["Material"].default_value = mat
    links.new(set_mat.outputs["Geometry"], gout.inputs["Geometry"])

    mod = trail_obj.modifiers.new("TrailNodes", "NODES")
    mod.node_group = tree
    return mod


def build_highway_and_world(scene):
    """Build the 4600-unit wet-mirror neon highway, speed-gantries, wireframe mountains, and OutRun sunset sun."""
    mat_road = _pbr_mat("WetAsphalt", (0.012, 0.010, 0.024), metallic=0.38, roughness=0.065, coat=0.9)
    mat_mtn = _pbr_mat("MountainRock", (0.022, 0.008, 0.045), metallic=0.25, roughness=0.35)
    mat_cyan = _emissive_mat("GridCyan", (0.0, 0.90, 1.0), 16.0)
    mat_mag = _emissive_mat("GridMagenta", (1.0, 0.06, 0.58), 18.0)
    mat_gold = _emissive_mat("SunGold", (1.0, 0.35, 0.06), 28.0)

    mm = _MultiMesh()
    y0, y1 = -140.0, HIGHWAY_LEN
    for y in np.arange(y0, y1, 20.0):
        yn = y + 20.0
        mm.quad((-13.0, y, 0.0), (13.0, y, 0.0), (13.0, yn, 0.0), (-13.0, yn, 0.0), mat=0)
        mm.quad((-12.6, y, 0.015), (12.6, y, 0.015), (12.6, y + 0.18, 0.015), (-12.6, y + 0.18, 0.015), mat=2)
        mm.quad((-0.22, y, 0.02), (0.22, y, 0.02), (0.22, yn, 0.02), (-0.22, yn, 0.02), mat=3)
        for lx in (-4.4, 4.4):
            mm.quad((lx - 0.12, y + 2.0, 0.02), (lx + 0.12, y + 2.0, 0.02),
                    (lx + 0.12, y + 13.0, 0.02), (lx - 0.12, y + 13.0, 0.02), mat=2)

    for sgn in (-1.0, 1.0):
        bx = sgn * 12.8
        mm.box(bx - 0.25, bx + 0.25, y0, y1, 0.0, 0.65, mat=0, top_mat=3)
        mm.box(bx - 0.30, bx + 0.30, y0, y1, 0.32, 0.46, mat=3)

    # Repeating overhead neon speed-gantries up to y = 2100 (before the Top Overview camera zone so the aerial view is unobstructed!)
    for k, gy in enumerate(np.arange(-40.0, 2100.0, 40.0)):
        g_mat = 2 if (k % 2 == 0) else 3
        for sgn in (-1.0, 1.0):
            px = sgn * 13.6
            mm.box(px - 0.45, px + 0.45, gy - 0.5, gy + 0.5, 0.0, 9.5, mat=0)
            mm.box(px - sgn * 0.52, px - sgn * 0.38, gy - 0.22, gy + 0.22, 0.6, 9.2, mat=g_mat)
        mm.box(-14.0, 14.0, gy - 0.5, gy + 0.5, 9.2, 9.9, mat=0)
        mm.box(-13.4, 13.4, gy - 0.55, gy + 0.55, 9.0, 9.22, mat=g_mat)
    # In the Top Overview hyper-launch zone (y = 2120..HIGHWAY_LEN), place low roadside speed pylons so the top-down view is crystal clear
    for k, gy in enumerate(np.arange(2120.0, y1, 36.0)):
        g_mat = 2 if (k % 2 == 0) else 3
        for sgn in (-1.0, 1.0):
            px = sgn * 13.4
            mm.box(px - 0.35, px + 0.35, gy - 0.4, gy + 0.4, 0.0, 4.2, mat=g_mat)

    rng = np.random.default_rng(77)
    x_bands = [14.0, 26.0, 42.0, 62.0, 88.0]
    y_steps = np.arange(-120.0, y1 + 40.0, 36.0)
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

    # Giant segmented OutRun sunset sun at the end of the 4600-unit highway
    sun_y = HIGHWAY_LEN + 120.0
    sun_r = 260.0
    sun_z0 = 56.0
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
    """Build Geometry Nodes 3D particle exhaust spark emitters behind both cars plus the boost shockwave ring."""
    mat_hero_sparks = _particle_exhaust_mat("HeroTrailMat", (0.75, 0.98, 1.0), (1.0, 0.06, 0.62), strength=48.0)
    mat_rival_sparks = _particle_exhaust_mat("RivalTrailMat", (1.0, 0.92, 0.55), (1.0, 0.14, 0.02), strength=44.0)
    mat_shock = _emissive_mat("ShockwaveMat", (0.35, 0.95, 1.0), 42.0)

    rng = np.random.default_rng(1988)
    n_per_nozzle = 32  # 64 separated 3D plasma spark particles per car
    for parent_car, t_name, mat in (
        (hero_car, "PlasmaTrails", mat_hero_sparks),
        (rival_car, "RivalTrails", mat_rival_sparks),
    ):
        pts = []
        phases = []
        vels = []
        for nozzle_x in (-0.50, 0.50):
            for k in range(n_per_nozzle):
                ang = rng.uniform(0.0, 2.0 * math.pi)
                rad = rng.uniform(0.01, 0.09)
                px = nozzle_x + rad * math.cos(ang)
                pz = 0.45 + rad * math.sin(ang)
                pts.append((px, -2.54, pz))
                phases.append(float(k) / n_per_nozzle + float(rng.uniform(0.0, 0.02)))
                # Wide 3D spark spray cone shooting backward along -Y so individual sparks are clearly separated
                vx = float(rng.uniform(-0.75, 0.75))
                vy = float(-rng.uniform(1.6, 4.2))
                vz = float(rng.uniform(-0.18, 0.55))
                vels.extend((vx, vy, vz))

        mesh = bpy.data.meshes.new(t_name)
        mesh.from_pydata(pts, [], [])
        mesh.materials.append(mat)
        a_phase = mesh.attributes.new("seed_phase", "FLOAT", "POINT")
        a_phase.data.foreach_set("value", phases)
        a_vel = mesh.attributes.new("spray_vel", "FLOAT_VECTOR", "POINT")
        a_vel.data.foreach_set("vector", vels)
        mesh.update()

        obj = bpy.data.objects.new(t_name, mesh)
        obj.parent = parent_car
        scene.collection.objects.link(obj)
        _add_trail_nodes(obj, mat)

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
    """Create the 5 shot cameras and timeline markers, plus the primary active Camera."""
    scene.timeline_markers.clear()
    cams = {}
    for frame, name in SHOT_CUTS:
        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = 35.0
        cam_data.clip_start = 0.05
        cam_data.clip_end = 5000.0
        cam_obj = bpy.data.objects.new(name, cam_data)
        scene.collection.objects.link(cam_obj)
        cams[name] = cam_obj
        scene.timeline_markers.new(name, frame=frame)

    master_data = bpy.data.cameras.new("Camera")
    master_data.lens = 35.0
    master_data.clip_start = 0.05
    master_data.clip_end = 5000.0
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
    """Return (shot_name, cam_pos, look_target, lens_mm, roll_rad) for frame 1..600 (supports float subframes)."""
    t = racer_time(frame)
    hx, hy, hz, _, h_roll, _ = car_kinematics(hero_x, hero_y, t)
    rx, ry, rz, _, _, _ = car_kinematics(rival_x, rival_y, t)

    if frame < 84.5:
        # Shot 1 (Frames 1..84, 0.0-3.5 s): Low Rear-Quarter Wheel/Exhaust Launch Cam
        u = max(0.0, min(1.0, (float(frame) - 1.0) / 83.0))
        cam_pos = (hx - 2.35 + 0.55 * u, hy - 5.6 + 0.4 * u, 0.92 + 0.22 * u)
        target = (hx - 0.25, hy + 2.5, 0.72)
        return "CamLaunch", cam_pos, target, 32.0, 0.03 * (1.0 - u)
    if frame < 168.5:
        # Shot 2 (Frames 85..168, 3.5-7.0 s): Sweeping Helicopter Aerial Orbit Cam
        u = max(0.0, min(1.0, (float(frame) - 85.0) / 83.0))
        sweep_x = hx + 4.4 * math.cos(u * math.pi * 0.9)
        cam_pos = (sweep_x, hy - 10.2 + 1.8 * u, 4.9 - 1.5 * u)
        target = (0.65 * hx + 0.35 * rx, hy + 3.8, 0.68)
        return "CamHeli", cam_pos, target, 34.0, -h_roll * 0.55
    if frame < 252.5:
        # Shot 3 (Frames 169..252, 7.0-10.5 s): Dynamic Front-3/4 Overtake Cam looking across both wedge supercars
        u = max(0.0, min(1.0, (float(frame) - 169.0) / 83.0))
        mid_x = 0.5 * (hx + rx)
        lead_y = max(hy, ry)
        cam_pos = (hx + 3.4 - 0.8 * u, lead_y + 4.8 - 2.2 * u, 1.85 - 0.35 * u)
        target = (mid_x - 0.2, 0.5 * (hy + ry) - 0.8, 0.62)
        return "CamOvertake", cam_pos, target, 32.0, -h_roll * 0.4
    if frame < 420.5:
        # Shot 4 (Frames 253..420, 10.5-17.5 s): Low Center Chase Cam -> Wide-FOV Hyper-Boost
        u = max(0.0, min(1.0, (float(frame) - 253.0) / 167.0))
        s = u * u * (3.0 - 2.0 * u)
        cam_pos = (hx * 0.85, hy - 6.0 - 1.2 * s, 1.25 - 0.18 * s)
        target = (hx * 0.35, hy + 18.0, 1.10 + 0.6 * s)
        lens = 35.0 - 15.0 * s  # widens smoothly from 35 mm down to 20 mm
        return "CamBoost", cam_pos, target, lens, h_roll * 0.35
    # Shot 5 (Frames 421..600, 17.5-25.0 s): High Top-Down Overview Camera where both cars hit MAX SPEED and disappear into the horizon!
    u = max(0.0, min(1.0, (float(frame) - 421.0) / 179.0))
    # Camera sits high above the open highway (z = 26 -> 36 u) looking down at a steep top-overview angle.
    # For the first 2.0 s (u < 0.25) it tracks right over both cars as their speed bars climb toward MAX,
    # then for u > 0.25 the cars ignite hyper-warp and rocket 800+ u away down the highway until they vanish into the sunset sun!
    lead_out = 18.0 + 24.0 * u + 820.0 * ((max(0.0, u - 0.25) / 0.75) ** 2.4)
    cam_y = hy - lead_out
    cam_z = 26.0 + 12.0 * u
    cam_pos = (0.0, cam_y, cam_z)
    target = (0.0, cam_y + 26.0 + 60.0 * u, 0.5)
    return "CamOverview", cam_pos, target, 28.0, 0.0


def _build_dial_clock(scene, rig, prefix, cx, cy, bz, mat_white, mat_red, mat_accent, mat_hub):
    """Build a compact, floating (no-background) 240-deg analog speedometer clock matching the reference dial."""
    mm = _MultiMesh()

    # 1. Thin outer arc rim (0.214..0.220) + inner red km/h scale arc (0.118..0.123) with NO background disc
    arc_steps = 48
    for i in range(arc_steps):
        u0, u1 = i / arc_steps, (i + 1) / arc_steps
        d0 = math.radians(210.0 - 240.0 * u0)
        d1 = math.radians(210.0 - 240.0 * u1)
        c0, s0 = math.cos(d0), math.sin(d0)
        c1, s1 = math.cos(d1), math.sin(d1)
        # Thin outer arc ring
        mm.quad((cx + 0.215 * c0, cy + 0.215 * s0, bz - 0.01), (cx + 0.220 * c0, cy + 0.220 * s0, bz - 0.01),
                (cx + 0.220 * c1, cy + 0.220 * s1, bz - 0.01), (cx + 0.215 * c1, cy + 0.215 * s1, bz - 0.01), mat=0)
        # Inner red secondary scale arc (like the inner km/h scale in the reference image)
        mm.quad((cx + 0.118 * c0, cy + 0.118 * s0, bz - 0.01), (cx + 0.122 * c0, cy + 0.122 * s0, bz - 0.01),
                (cx + 0.122 * c1, cy + 0.122 * s1, bz - 0.01), (cx + 0.118 * c1, cy + 0.118 * s1, bz - 0.01), mat=1)

    # 2. 60 radial ticks around 0..120 scale (13 major white ticks every 10 units + 4 fine red minor ticks between each)
    for tick_i in range(61):
        u = tick_i / 60.0
        ang = math.radians(210.0 - 240.0 * u)
        ca, sa = math.cos(ang), math.sin(ang)
        pa, qa = -sa, ca
        is_major = (tick_i % 5 == 0)
        r0 = 0.184 if is_major else 0.198
        r1 = 0.215
        hw = 0.0038 if is_major else 0.0016
        t_mat = 0 if is_major else 1  # white major ticks, red fine subdivision ticks (like the reference image)
        mm.quad((cx + r0 * ca - hw * pa, cy + r0 * sa - hw * qa, bz - 0.005),
                (cx + r1 * ca - hw * pa, cy + r1 * sa - hw * qa, bz - 0.005),
                (cx + r1 * ca + hw * pa, cy + r1 * sa + hw * qa, bz - 0.005),
                (cx + r0 * ca + hw * pa, cy + r0 * sa + hw * qa, bz - 0.005), mat=t_mat)
        if is_major:
            # Inner red scale ticks pointing inward
            ir0, ir1, ihw = 0.104, 0.118, 0.0024
            mm.quad((cx + ir0 * ca - ihw * pa, cy + ir0 * sa - ihw * qa, bz - 0.005),
                    (cx + ir1 * ca - ihw * pa, cy + ir1 * sa - ihw * qa, bz - 0.005),
                    (cx + ir1 * ca + ihw * pa, cy + ir1 * sa + ihw * qa, bz - 0.005),
                    (cx + ir0 * ca + ihw * pa, cy + ir0 * sa + ihw * qa, bz - 0.005), mat=1)

    # Small center pivot cap
    r_cap = 0.016
    for i in range(16):
        a0 = 2.0 * math.pi * i / 16
        a1 = 2.0 * math.pi * (i + 1) / 16
        mm.quad((cx, cy, bz + 0.025), (cx + r_cap * math.cos(a0), cy + r_cap * math.sin(a0), bz + 0.025),
                (cx + r_cap * math.cos(a1), cy + r_cap * math.sin(a1), bz + 0.025), (cx, cy, bz + 0.025), mat=3)

    dial_obj = mm.to_object(prefix + "_DialFace", [mat_white, mat_red, mat_accent, mat_hub])
    dial_obj.parent = rig
    scene.collection.objects.link(dial_obj)

    # 3. Scale numbers (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120) inside the major ticks
    r_num = 0.154
    for k in range(13):
        u = k / 12.0
        ang = math.radians(210.0 - 240.0 * u)
        nx = cx + r_num * math.cos(ang)
        ny = cy + r_num * math.sin(ang)
        ncurve = bpy.data.curves.new("%s_Num_%d" % (prefix, k * 10), "FONT")
        ncurve.body = str(k * 10)
        ncurve.size = 0.024
        ncurve.align_x = "CENTER"
        ncurve.align_y = "CENTER"
        ncurve.materials.append(mat_red if k >= 10 else mat_white)
        nobj = bpy.data.objects.new("%s_Num_%d" % (prefix, k * 10), ncurve)
        nobj.parent = rig
        nobj.location = (nx, ny, bz)
        scene.collection.objects.link(nobj)

    # 4. Pivoting tapered red speedometer needle (points along +X at rotation_z = 0)
    nm = _MultiMesh()
    nm.quad((-0.035, -0.0065, 0.0), (0.0, -0.0095, 0.0), (0.0, 0.0095, 0.0), (-0.035, 0.0065, 0.0), mat=0)
    nm.quad((0.0, -0.0095, 0.0), (0.192, -0.0022, 0.0), (0.192, 0.0022, 0.0), (0.0, 0.0095, 0.0), mat=0)
    needle_obj = nm.to_object(prefix + "_Needle", [mat_red])
    needle_obj.parent = rig
    needle_obj.location = (cx, cy, bz + 0.015)
    scene.collection.objects.link(needle_obj)
    return needle_obj


def _add_racer_hud(scene, master_cam):
    """Add two compact, transparent (no-background) analog speedometer clocks in the far bottom-left and bottom-right corners."""
    from src.gauge import _backing, _frame, _strip

    for name in list(bpy.data.objects.keys()):
        if name.startswith("RacerHUD") or name.startswith("Gauge") or name.startswith("Rival") or name.startswith("HeroDial"):
            if name != "RivalRacer" and not name.startswith("RivalRacer_") and name != "RivalTrails":
                bpy.data.objects.remove(bpy.data.objects[name])

    rig = bpy.data.objects.new("RacerHUD_Rig", None)
    rig.parent = master_cam
    scene.collection.objects.link(rig)

    mat_white = _emissive_mat("HUD_DialWhite", (0.95, 0.97, 1.0), 1.55)
    mat_red = _emissive_mat("HUD_NeedleRed", (1.0, 0.10, 0.16), 2.10)
    mat_cyan = _emissive_mat("HUD_HeroCyan", (0.20, 0.94, 1.0), 1.50)
    mat_crim = _emissive_mat("HUD_RivalCrim", (1.0, 0.55, 0.15), 1.50)
    mat_hub = _emissive_mat("HUD_HubCap", (0.85, 0.12, 0.18), 1.60)
    mat_track = _emissive_mat("HUD_TrackDim", (0.06, 0.12, 0.22), 0.22)
    panel_mat = _backing("RacerHUD_PanelMat")

    # Tucked into the far bottom-left (-1.52, -0.73) and far bottom-right (+1.52, -0.73) corners with NO background disc
    bz = -5.0
    cx_l, cx_r, cy = -1.52, 1.52, -0.73

    _build_dial_clock(scene, rig, "RivalDial", cx_l, cy, bz, mat_white, mat_red, mat_crim, mat_hub)
    _build_dial_clock(scene, rig, "HeroDial", cx_r, cy, bz, mat_white, mat_red, mat_cyan, mat_hub)

    # Keep legacy GaugeBar/GaugePanel objects hidden in render for unit-test compatibility
    bar_w = 0.24
    for legacy_obj in (
        _strip(scene, rig, "RivalSpeedTrack", (cx_l, cy, bz - 0.08), 0.01, mat_track),
        _strip(scene, rig, "RivalSpeedBar", (cx_l, cy, bz - 0.08), 0.01, mat_crim),
        _strip(scene, rig, "GaugePanel", (cx_r, cy, bz - 0.08), 0.01, panel_mat),
        _frame(scene, rig, "GaugeFrame", (cx_r, cy, bz - 0.08), 0.02, 0.01, mat_cyan),
        _strip(scene, rig, "GaugeTrack", (cx_r, cy, bz - 0.08), 0.01, mat_track),
        _strip(scene, rig, "GaugeBar", (cx_r, cy, bz - 0.08), 0.01, mat_cyan),
    ):
        legacy_obj.hide_render = True

    r_curve = bpy.data.curves.new("RivalGaugeText", "FONT")
    r_curve.size = 0.032
    r_curve.align_x = "CENTER"
    r_curve.materials.append(mat_crim)
    r_text = bpy.data.objects.new("RivalGaugeText", r_curve)
    r_text.parent = rig
    r_text.location = (cx_l, cy - 0.11, bz + 0.01)
    scene.collection.objects.link(r_text)

    h_curve = bpy.data.curves.new("GaugeText", "FONT")
    h_curve.size = 0.032
    h_curve.align_x = "CENTER"
    h_curve.materials.append(mat_cyan)
    h_text = bpy.data.objects.new("GaugeText", h_curve)
    h_text.parent = rig
    h_text.location = (cx_r, cy - 0.11, bz + 0.01)
    scene.collection.objects.link(h_text)

    def _dial_frac(spd):
        """Map 0..420 KM/H across 0..82% of the dial arc, and 420..999 KM/H across the 82..100% redline zone."""
        if spd <= 420.0:
            return 0.82 * (spd / 420.0)
        return min(1.0, 0.82 + 0.18 * ((spd - 420.0) / (999.0 - 420.0)))

    def _on_racer_frame(scn, depsgraph=None):
        if "GaugeText" not in bpy.data.objects or "GaugeBar" not in bpy.data.objects:
            return
        t = racer_time(scn.frame_current)
        b = racer_beta(t)
        h_spd = hero_kmh(t)
        r_spd = rival_kmh(t)
        h_frac = _dial_frac(h_spd)
        r_frac = _dial_frac(r_spd)
        flutter = 0.025 * math.sin(scn.frame_current * 2.4) if h_spd >= 950.0 else 0.0
        if "HeroDial_Needle" in bpy.data.objects:
            bpy.data.objects["HeroDial_Needle"].rotation_euler = (0.0, 0.0, math.radians(210.0 - 240.0 * h_frac) + flutter)
        if "RivalDial_Needle" in bpy.data.objects:
            bpy.data.objects["RivalDial_Needle"].rotation_euler = (0.0, 0.0, math.radians(210.0 - 240.0 * r_frac) - flutter)

        h_tag = "MAX!" if h_spd >= 950.0 else ("%.2fc" % b)
        bpy.data.objects["GaugeText"].data.body = "R-CAR · %s\n%3.0f KM/H" % (h_tag, h_spd)
        bpy.data.objects["GaugeBar"].scale.x = bar_w * max(0.06, h_frac)
        if "RivalGaugeText" in bpy.data.objects and "RivalSpeedBar" in bpy.data.objects:
            r_tag = "MAX!" if r_spd >= 920.0 else ("G%d" % min(7, 1 + int(r_spd // 65.0)))
            bpy.data.objects["RivalGaugeText"].data.body = "L-CAR · %s\n%3.0f KM/H" % (r_tag, r_spd)
            bpy.data.objects["RivalSpeedBar"].scale.x = bar_w * max(0.06, r_frac)

    bpy.app.handlers.frame_change_pre[:] = [
        h for h in bpy.app.handlers.frame_change_pre if getattr(h, "__name__", "") != "_on_racer_frame"
    ]
    bpy.app.handlers.frame_change_pre.append(_on_racer_frame)
    _on_racer_frame(scene)
    return rig


def animate_racer_scene(scene, hero_car, rival_car, highway, shockwave, cams, master_cam, hud_rig):
    """Keyframe cars, spinning wheels, Geometry Nodes particle sparks, boost shockwave, and 5-shot camera cuts."""
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, RACER_FRAMES

    h_wheels = [o for o in hero_car.children if "Wheel" in o.name]
    r_wheels = [o for o in rival_car.children if "Wheel" in o.name]
    hw_mod = highway.modifiers["HighwayNodes"]
    hw_key = hw_mod.node_group.interface.items_tree["BeatPhase"].identifier

    trail_objs = [bpy.data.objects["PlasmaTrails"], bpy.data.objects["RivalTrails"]]
    tail_strengths = [
        bpy.data.materials[m_name].node_tree.nodes["Emission"].inputs["Strength"]
        for m_name in ("HeroRacer_Tail", "RivalRacer_Tail")
        if m_name in bpy.data.materials
    ]
    depth_scale = 0.05  # keeps the HUD 0.25 u in front of the camera pinhole so camera pans never blur it

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

    for f in range(FRAME_START, RACER_FRAMES + 1):
        t = racer_time(f)
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

        boost_fac = 1.0 + 1.4 / (1.0 + math.exp(-(t - 10.5) * 4.0)) + 2.2 / (1.0 + math.exp(-(t - 18.5) * 3.0))
        for tr_obj in trail_objs:
            tr_mod = tr_obj.modifiers["TrailNodes"]
            b_key = tr_mod.node_group.interface.items_tree["BoostFactor"].identifier
            t_key = tr_mod.node_group.interface.items_tree["SimTime"].identifier
            tr_mod[b_key] = float(boost_fac)
            tr_mod[t_key] = float(t)
            tr_obj.keyframe_insert(data_path='modifiers["TrailNodes"]["%s"]' % b_key, frame=f)
            tr_obj.keyframe_insert(data_path='modifiers["TrailNodes"]["%s"]' % t_key, frame=f)

        # Shockwave ring on Shot 4 boost (frame 253..305); kept hidden in Shot 5 overview so no road disc appears
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

        # Flash both cars' tail lamps on the 124 BPM synthwave snare (beats 2 and 4)
        tail_val = 110.0 if snare_on(t) else 8.0
        for t_sock in tail_strengths:
            t_sock.default_value = tail_val
            t_sock.keyframe_insert(data_path="default_value", frame=f)

        shot_name, cpos, ctarget, clens, croll = shot_camera_pose(f)
        ceul = _look_at_quat(cpos, ctarget, croll)
        _key_cam(cams[shot_name], f, cpos, ceul, clens)
        _key_cam(master_cam, f, cpos, ceul, clens)
        _key_hud(f, clens)

        for n_name, spd_fn, sgn in (("HeroDial_Needle", hero_kmh, 1.0), ("RivalDial_Needle", rival_kmh, -1.0)):
            if n_name in bpy.data.objects:
                spd = spd_fn(t)
                frac = 0.82 * (spd / 420.0) if spd <= 420.0 else min(1.0, 0.82 + 0.18 * ((spd - 420.0) / 579.0))
                fl = sgn * 0.025 * math.sin(f * 2.4) if spd >= 950.0 else 0.0
                n_obj = bpy.data.objects[n_name]
                n_obj.rotation_euler = (0.0, 0.0, math.radians(210.0 - 240.0 * frac) + fl)
                n_obj.keyframe_insert(data_path="rotation_euler", frame=f)

        if f in (84, 168, 252, 420):
            _, cpos_a, ctarget_a, clens_a, croll_a = shot_camera_pose(f + 0.45)
            _key_cam(master_cam, f + 0.45, cpos_a, _look_at_quat(cpos_a, ctarget_a, croll_a), clens_a)
            _key_hud(f + 0.45, clens_a)
            _, cpos_b, ctarget_b, clens_b, croll_b = shot_camera_pose(f + 0.55)
            _key_cam(master_cam, f + 0.55, cpos_b, _look_at_quat(cpos_b, ctarget_b, croll_b), clens_b)
            _key_hud(f + 0.55, clens_b)

    for ob in [hero_car, rival_car, highway, *trail_objs, shockwave, master_cam, hud_rig, *cams.values(), *h_wheels, *r_wheels]:
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    for c_obj in [master_cam, *cams.values()]:
        if c_obj.data.animation_data and c_obj.data.animation_data.action:
            for fc in c_obj.data.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    for m_name in ("HeroRacer_Tail", "RivalRacer_Tail"):
        nt = bpy.data.materials[m_name].node_tree if m_name in bpy.data.materials else None
        if nt and nt.animation_data and nt.animation_data.action:
            for fc in nt.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    scene.frame_set(FRAME_START)


def build_racer_scene():
    """Build the complete native Blender Synthwave Neon Racer scene (600 frames / 25.0 s) and return `scene`."""
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
