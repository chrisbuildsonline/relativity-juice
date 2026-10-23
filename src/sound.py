"""Sound bed from the physics (stdlib only, no numpy/bpy): write_wav(path, title, flight, end).

A drone whose pitch follows log(gamma) (70 Hz to 280 Hz), a detuned fifth, and a seeded noise
rush that opens up with beta. Quiet under the title, swells through the flight, decays over the end card.
"""
import math
import random
import struct
import wave

RATE = 48000
PEAK = 0.85  # fraction of full scale, under the -1 dBFS (0.89) ceiling
DURATION, START, END = 15.0, 0.1, 0.999  # same flight as src.relativity.beta_at


def beta(t):
    """Stdlib copy of src.relativity.beta_at: smoothstep in rapidity, clamped to [0, DURATION]."""
    u = min(max(t / DURATION, 0.0), 1.0)
    s = u * u * (3.0 - 2.0 * u)
    return math.tanh(math.atanh(START) * (1.0 - s) + math.atanh(END) * s)


def gamma(b):
    return 1.0 / math.sqrt(1.0 - b * b)


def write_wav(path, title, flight, end):
    """48 kHz mono 16-bit WAV of title + flight + end seconds."""
    total = title + flight + end
    rng = random.Random(7)
    top = math.log(gamma(END))
    ph = ph2 = lp = 0.0
    out = []
    for i in range(int(total * RATE)):
        t = i / RATE
        b = beta(min(max(t - title, 0.0), flight))
        x = math.log(gamma(b)) / top  # 0 at the start of the flight, 1 at 0.999c
        f = 70.0 * 4.0 ** x
        ph += 2 * math.pi * f / RATE
        ph2 += 2 * math.pi * f * 1.5 * 1.004 / RATE
        lp += (0.02 + 0.6 * b) * (rng.gauss(0.0, 1.0) - lp)  # noise opens up as beta rises
        v = (0.15 + 0.85 * x) * (math.sin(ph) + 0.5 * math.sin(2 * ph) + 0.4 * math.sin(ph2)) + 1.2 * x * b ** 3 * lp
        v *= math.exp(-max(t - title - flight, 0.0) / 1.2)  # resolve over the end card
        v *= min(t / 0.5, 1.0) ** 2 * min((total - t) / 1.0, 1.0) ** 2  # fade in 0.5 s, out 1 s
        out.append(v)
    scale = PEAK / max(abs(v) for v in out)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack("<%dh" % len(out), *(int(round(v * scale * 32767)) for v in out)))
