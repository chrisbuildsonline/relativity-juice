"""Soundtrack generator for the animation (stdlib only, no numpy/bpy): write_wav(path, title, flight, end).

Delegates to src.synthwave so the video gets the full 124 BPM 90s Synthwave soundtrack (analog kick,
gated-reverb snare, 16th-note sawtooth arp bass, chorus polysynth pads, soaring lead melody, and
speed-synced turbo engine) while preserving the exact public API expected by src.media and tests.
"""
from src.synthwave import BPM, CUT_TIMES, DURATION, END, PEAK, RATE, START, STEP, beta, gamma, synthesize_stereo, write_synthwave_wav

__all__ = ["BPM", "CUT_TIMES", "DURATION", "END", "PEAK", "RATE", "START", "STEP", "beta", "gamma", "synthesize_stereo", "write_wav"]


def write_wav(path, title, flight, end, channels=1):
    """48 kHz 16-bit WAV of title + flight + end seconds (124 BPM 90s Synthwave soundtrack)."""
    write_synthwave_wav(path, title, flight, end, channels=channels)
