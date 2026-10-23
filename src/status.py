"""Render progress (no bpy): python3 -m src.status. Frames done, process alive, last log line, ETA."""
import os
import re
import sys
import time

from src.encode import ROOT


def status(frames_dir, log, pid_file, total=360):
    done = len([f for f in os.listdir(frames_dir) if re.fullmatch(r"\d{4}\.png", f)]) if os.path.isdir(frames_dir) else 0
    alive = False
    if os.path.exists(pid_file):
        try:
            os.kill(int(open(pid_file).read()), 0)
            alive = True
        except (OSError, ValueError):
            pass
    lines = open(log).read().splitlines() if os.path.exists(log) else []
    secs = [float(m.group(1)) for m in (re.search(r"frame \d+ ([\d.]+)s", s) for s in lines) if m][-10:]
    out = ["frames %d/%d, render %s" % (done, total, "running" if alive else "not running")]
    if secs:
        eta = sum(secs) / len(secs) * (total - done)
        out.append("last %.1fs/frame, eta %.0f min" % (secs[-1], eta / 60))
    mine = [s for s in lines if s.startswith("render:")]
    if lines:
        out.append((mine or lines)[-1])
    return "\n".join(out)


def wait(frames_dir, log, pid_file, total=360, max_min=None, poll=30, sleep=time.sleep, clock=time.monotonic):
    """Block until all frames exist or the render process is gone. Returns (code, status text):
    0 complete, 1 stopped short, 2 gave up after max_min minutes."""
    start = clock()
    while True:
        text = status(frames_dir, log, pid_file, total)
        if "frames %d/%d" % (total, total) in text:
            return 0, text
        if "not running" in text:
            return 1, text
        if max_min is not None and clock() - start >= max_min * 60:
            return 2, text
        sleep(poll)


if __name__ == "__main__":
    o = os.path.join(ROOT, "out")
    args = (os.path.join(o, "frames"), os.path.join(o, "render.log"), os.path.join(o, "render.pid"))
    if "--wait" in sys.argv:
        i = sys.argv.index("--max-min") if "--max-min" in sys.argv else 0
        code, text = wait(*args, max_min=float(sys.argv[i + 1]) if i else None)
        print(text)
        sys.exit(code)
    print(status(*args))
