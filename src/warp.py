"""Relativistic warp as a Geometry Nodes modifier, plus the keyframed flight (bpy).

Per vertex, with v = pos - cam, r = |v|, d = v / r, c = d.y (city frame):
    d' = ((c + b) Y + (d - c Y) / g) / (1 + b c),  new pos = cam + r d',  D = g (1 + b c)
which is relativity.aberrate / relativity.doppler. Near the backward axis
1 + c and c + b cancel badly in float32, so they are built from 1 + c, using
1 + c = sin^2 / (1 - c) for c < 0, and from 1 - b (exact in float32 for b >= 0.5).
"""
import bpy

from src.flight import FPS, FRAME_END, FRAME_START, camera_y, time_of
from src.relativity import beta_at

NAME = "Warp"


def _build_tree(camera):
    tree = bpy.data.node_groups.new(NAME, "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    sock = tree.interface.new_socket("Beta", in_out="INPUT", socket_type="NodeSocketFloat")
    sock.default_value, sock.min_value, sock.max_value = 0.0, 0.0, 0.9999
    nodes, links = tree.nodes, tree.links

    def put(node, args):
        for i, v in enumerate(args):
            if isinstance(v, bpy.types.NodeSocket):
                links.new(v, node.inputs[i])
            elif v is not None:
                node.inputs[i].default_value = v
        return node

    def math(op, *args):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        return put(n, args).outputs[0]

    def vec(op, *args):
        n = nodes.new("ShaderNodeVectorMath")
        n.operation = op
        return put(n, args)

    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    beta = gin.outputs["Beta"]
    pos = nodes.new("GeometryNodeInputPosition").outputs[0]
    info = nodes.new("GeometryNodeObjectInfo")
    info.transform_space = "ORIGINAL"
    info.inputs["Object"].default_value = camera
    cam = info.outputs["Location"]

    omb = math("SUBTRACT", 1.0, beta)  # 1 - b
    gam = math("INVERSE_SQRT", math("MULTIPLY", omb, math("ADD", beta, 1.0)))
    v = vec("SUBTRACT", pos, cam).outputs[0]
    r = vec("LENGTH", v).outputs["Value"]
    unit = vec("SCALE", v)
    links.new(math("DIVIDE", 1.0, r), unit.inputs["Scale"])
    d = unit.outputs[0]
    split = nodes.new("ShaderNodeSeparateXYZ")
    links.new(d, split.inputs[0])
    dx, c, dz = split.outputs

    sin2 = math("MULTIPLY_ADD", dx, dx, math("MULTIPLY", dz, dz))
    behind = nodes.new("FunctionNodeCompare")
    behind.data_type, behind.operation = "FLOAT", "LESS_THAN"
    put(behind, (c, 0.0))
    onepc = nodes.new("GeometryNodeSwitch")
    onepc.input_type = "FLOAT"
    flt = [i for i in onepc.inputs if i.type == "VALUE"]  # False, True
    links.new(behind.outputs["Result"], onepc.inputs["Switch"])
    links.new(math("ADD", 1.0, c), flt[0])
    links.new(math("DIVIDE", sin2, math("SUBTRACT", 1.0, c)), flt[1])
    one_plus_c = onepc.outputs[0]

    denom = math("MULTIPLY_ADD", beta, one_plus_c, omb)  # 1 + b c
    new_y = math("DIVIDE", math("SUBTRACT", one_plus_c, omb), denom)  # (c + b) / (1 + b c)
    k = math("DIVIDE", 1.0, math("MULTIPLY", gam, denom))
    comb = nodes.new("ShaderNodeCombineXYZ")
    links.new(math("MULTIPLY", dx, k), comb.inputs["X"])
    links.new(new_y, comb.inputs["Y"])
    links.new(math("MULTIPLY", dz, k), comb.inputs["Z"])
    scaled = vec("SCALE", comb.outputs[0])
    links.new(r, scaled.inputs["Scale"])
    new_pos = vec("ADD", cam, scaled.outputs[0]).outputs[0]

    # fields read Position, so store D before Set Position moves the vertices
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT", "POINT"
    links.new(gin.outputs["Geometry"], store.inputs["Geometry"])
    store.inputs["Name"].default_value = "doppler"
    value = [i for i in store.inputs if i.name == "Value" and i.type == "VALUE"][0]
    links.new(math("MULTIPLY", gam, denom), value)
    setp = nodes.new("GeometryNodeSetPosition")
    links.new(store.outputs["Geometry"], setp.inputs["Geometry"])
    links.new(new_pos, setp.inputs["Position"])
    links.new(setp.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _beta_key(city):
    return city.modifiers[NAME].node_group.interface.items_tree["Beta"].identifier


def add_warp(city, camera):
    """Add the warp modifier to `city`; it reads the position of `camera` live."""
    mod = city.modifiers.new(NAME, "NODES")
    mod.node_group = _build_tree(camera)
    return mod


def set_beta(city, beta):
    """Set the warp's beta (plain value, no keyframes)."""
    city.modifiers[NAME][_beta_key(city)] = float(beta)
    city.update_tag()


def animate_flight(scene, city, camera):
    """Keyframe beta and the camera Y at every frame (linear) and set scene timing."""
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, FRAME_END
    path = 'modifiers["%s"]["%s"]' % (NAME, _beta_key(city))
    for f in range(FRAME_START, FRAME_END + 1):
        t = time_of(f)
        city.modifiers[NAME][_beta_key(city)] = float(beta_at(t))
        city.keyframe_insert(data_path=path, frame=f)
        camera.location.y = camera_y(t)
        camera.keyframe_insert(data_path="location", frame=f)
    for ob, dp in ((city, path), (camera, "location")):
        for fc in ob.animation_data.action.fcurves:
            if fc.data_path == dp:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    scene.frame_set(FRAME_START)
