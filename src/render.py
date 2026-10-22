"""Frame-by-frame, resumable render of the flight (bpy)."""
import os
import time

import bpy

from src.city import build_city, setup_view
from src.gauge import add_gauge
from src.warp import add_warp, animate_flight


def build_scene(**city_args):
    """The full animated scene: warped city, camera flight, gauge."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    city = build_city(**city_args)
    setup_view(scene)
    add_warp(city, scene.camera)
    animate_flight(scene, city, scene.camera)
    add_gauge(scene, scene.camera)
    return scene


def _device(scene, device):
    """'cpu', 'gpu' (CUDA) or 'auto' (CUDA if there is one)."""
    scene.cycles.device = "CPU"
    if device == "cpu":
        return
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "CUDA"
        if any(d.type == "CUDA" for d in prefs.devices):
            scene.cycles.device = "GPU"
    except Exception as e:  # no CUDA backend in this build/machine
        print("render: no CUDA (%s), using CPU" % e)


def render_frames(scene, out_dir, frames, width=1920, height=1080, samples=48, device="auto", denoise=True):
    """Render `frames` to out_dir/NNNN.png, skipping existing ones. Returns the frames rendered."""
    os.makedirs(out_dir, exist_ok=True)
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    r.image_settings.file_format = "PNG"
    r.use_lock_interface = True  # keep the frame-change handler (gauge) in step with each render
    r.use_file_extension = False
    scene.cycles.samples = samples
    scene.cycles.use_denoising = denoise
    _device(scene, device)
    done = []
    for f in frames:
        png = os.path.join(out_dir, "%04d.png" % f)
        if os.path.exists(png):
            continue
        t0 = time.perf_counter()
        scene.frame_set(f)  # fires frame_change_pre: gauge text and bar
        r.filepath = png[:-4] + ".part"
        bpy.ops.render.render(write_still=True)
        os.replace(r.filepath, png)  # only a finished frame ever has the .png name
        done.append(f)
        print("render: frame %d %.2fs device=%s" % (f, time.perf_counter() - t0, scene.cycles.device), flush=True)
    return done
