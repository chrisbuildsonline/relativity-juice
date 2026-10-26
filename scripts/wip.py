"""Work-in-progress screenshot of the Blender UI -> media/wip.png (run with the GUI, via bin/wip).

Builds the same scene the render builds (city, warp, gauge, flight), jumps to frame 220, puts every 3D
viewport in camera view with material shading (EEVEE, no Cycles), then screenshots the whole window and quits.
"""
import os
import subprocess
import sys
import tempfile

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.encode import tool  # noqa: E402
from src.racer import build_racer_scene  # noqa: E402

FRAME = 205
PNG = os.path.join(ROOT, "media", "wip.png")
os.makedirs(os.path.dirname(PNG), exist_ok=True)
if os.path.exists(PNG):
    os.remove(PNG)  # a stale screenshot must not pass for a fresh one

scene = build_racer_scene()
scene.render.engine = "BLENDER_EEVEE_NEXT"  # viewport material shading only; nothing is rendered
scene.frame_set(FRAME)
TMP = os.path.join(tempfile.mkdtemp(), "wip.blend")


def window():
    return bpy.context.window_manager.windows[0]


def set_views():
    for area in window().screen.areas:
        if area.type == "VIEW_3D":
            area.spaces[0].shading.type = "MATERIAL"
            area.spaces[0].region_3d.view_perspective = "CAMERA"
            area.tag_redraw()
    # reopening the scene from disk clears the splash popup that a factory-startup GUI opens over it
    bpy.ops.wm.save_as_mainfile(filepath=TMP, copy=True)
    bpy.ops.wm.open_mainfile(filepath=TMP)
    return None


def shoot():
    win = window()
    with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)  # draw the window so there is something to grab
        bpy.ops.screen.screenshot(filepath=PNG, check_existing=False)
    if not has_pixels(PNG):  # software GL: Blender's own grab can come back black, so grab the X screen
        display = os.environ.get("DISPLAY", ":0")
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "x11grab", "-i", display,
                        "-frames:v", "1", "-update", "1", PNG], check=True)
    print("wip: screenshot -> %s" % PNG, flush=True)
    return None


def has_pixels(path):
    if not os.path.exists(path):
        return False
    img = bpy.data.images.load(path)
    lit = np.array(img.pixels[:]).reshape(-1, 4)[:, :3].max() > 0.0  # RGB only: alpha is always 1
    bpy.data.images.remove(img)
    return lit


def quit_blender():
    print("wip: exists=%s" % os.path.exists(PNG), flush=True)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(set_views, first_interval=4.0)
bpy.app.timers.register(shoot, first_interval=14.0, persistent=True)  # persistent: survive the file reopen
bpy.app.timers.register(quit_blender, first_interval=18.0, persistent=True)
