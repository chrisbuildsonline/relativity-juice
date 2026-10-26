"""Procedural 90s Synthwave soundtrack generator (124 BPM, 48 kHz stereo WAV, pure Python/stdlib + optional NumPy).

Synthesizes a 5-layer synthwave track synced to the 15 s Neon Racer animation and its 4 camera cuts:
1. 124 BPM drum machine: punchy pitch-enveloped analog kick, 90s gated-reverb snare, 16th hi-hats, and stereo tom fills at the 3 camera cuts (3.5 s, 7.0 s, 10.5 s).
2. Rolling 16th-note sawtooth arpeggiated bassline (Am - F - C - G) with sidechain ducking and a filter sweep that opens with speed.
3. Stereo chorus-detuned polysynth chord pads.
4. Soaring 90s lead synth melody with stereo dotted-eighth delay.
5. Synced twin-turbo plasma engine layer that shifts gears and boosts with beta(t).
"""
import math
import random
import struct
import wave

RATE = 48000
PEAK = 0.85  # under the -1 dBFS (0.89) ceiling
BPM = 124.0
BEAT = 60.0 / BPM  # ~0.4839 s per beat
STEP = BEAT / 4.0  # ~0.1210 s per 16th note
DURATION, START, END = 15.0, 0.1, 0.999
CUT_TIMES = (3.5, 7.0, 10.5, 17.5)  # camera cut timestamps inside the race (frames 85, 169, 253, 421)
SNARE_GATE = 0.14  # seconds of full gated-snare sustain on beats 2 and 4


def snare_on(t):
    """True during the 0.14 s gated-reverb snare hit on beats 2 and 4 of each 124 BPM bar (race time t >= 0)."""
    if t < 0.0:
        return False
    st = (t % (2.0 * BEAT)) - BEAT
    return 0.0 <= st < SNARE_GATE

# 4-bar chord progression in A minor: (bass_hz, (pad_chord_hz...))
PROGRESSION = (
    (55.00, (220.00, 261.63, 329.63, 392.00)),  # Am7
    (43.65, (174.61, 220.00, 261.63, 329.63)),  # Fmaj7
    (65.41, (261.63, 329.63, 392.00, 587.33)),  # Cadd9
    (49.00, (196.00, 246.94, 293.66, 392.00)),  # G
)

# 16-step lead melody per bar (Hz, 0.0 = sustain/rest) in A minor pentatonic / natural minor
LEAD_BARS = (
    (440.0, 0.0, 523.25, 0.0, 659.25, 0.0, 587.33, 523.25, 440.0, 0.0, 392.0, 0.0, 440.0, 523.25, 587.33, 0.0),
    (349.23, 0.0, 440.0, 0.0, 523.25, 0.0, 659.25, 587.33, 523.25, 0.0, 440.0, 0.0, 392.0, 440.0, 523.25, 0.0),
    (523.25, 0.0, 659.25, 0.0, 783.99, 0.0, 659.25, 587.33, 523.25, 0.0, 587.33, 0.0, 659.25, 0.0, 783.99, 0.0),
    (392.0, 0.0, 493.88, 0.0, 587.33, 0.0, 659.25, 587.33, 493.88, 0.0, 587.33, 0.0, 659.25, 783.99, 880.0, 0.0),
)

ARP_MULT = (1.0, 1.0, 2.0, 1.0, 1.0, 2.0, 1.5, 2.0, 1.0, 1.0, 2.0, 1.0, 1.5, 2.0, 1.5, 2.0)


def beta(t):
    """Smoothstep in rapidity from 0.1c to 0.999c over DURATION seconds."""
    u = min(max(t / DURATION, 0.0), 1.0)
    s = u * u * (3.0 - 2.0 * u)
    return math.tanh(math.atanh(START) * (1.0 - s) + math.atanh(END) * s)


def gamma(b):
    return 1.0 / math.sqrt(1.0 - b * b)


def _saw(phase):
    """Band-softened sawtooth wave on phase in radians."""
    p = (phase / (2.0 * math.pi)) % 1.0
    return (2.0 * p - 1.0) - 0.18 * math.sin(phase)


def synthesize_stereo(title, flight, end):
    """Return (left, right) float lists at 48 kHz for title + flight + end seconds."""
    total = title + flight + end
    n_samples = int(round(total * RATE))
    rng = random.Random(1984)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(4096)]

    left = [0.0] * n_samples
    right = [0.0] * n_samples

    bass_ph = 0.0
    bass_lp = 0.0
    lead_ph = 0.0
    lead_freq = 440.0
    eng_ph = 0.0
    pad_ph_l = [0.0, 0.0, 0.0, 0.0]
    pad_ph_r = [0.0, 0.0, 0.0, 0.0]

    # Dotted-eighth stereo delay buffer for the 90s lead synth
    delay_samples = max(1, int(STEP * 3.0 * RATE))
    delay_l = [0.0] * delay_samples
    delay_r = [0.0] * delay_samples
    di = 0

    inv_rate = 1.0 / RATE
    two_pi = 2.0 * math.pi

    for i in range(n_samples):
        t = i * inv_rate
        ft = t - title  # time inside the race (15 s or 25 s)
        in_flight = 0.0 <= ft < flight
        # Scale time into [0, DURATION] so beta(t_norm) ramps from 0.1c to 0.999c across any flight length
        t_norm = min(max(ft, 0.0), flight) * (DURATION / max(flight, 1e-6))
        b = beta(t_norm)
        # Drive envelope climbs steadily across the race and hits overdrive in the final top-overview hyper-launch
        overdrive = 1.0 / (1.0 + math.exp(-(ft - 17.5) * 3.0)) if flight > 18.0 else 0.0
        drive = min(1.15, 0.35 + 0.65 * min(max(ft / max(flight, 1.0), 0.0), 1.0) + 0.18 * overdrive) if in_flight else 0.25

        # Determine bar (4 beats) and 16th-note step relative to the race start
        race_beat = max(ft, 0.0) / BEAT
        bar_idx = int(race_beat // 4.0) % 4
        step_in_bar = int((max(ft, 0.0) / STEP) % 16)
        step_pos = (max(ft, 0.0) % STEP) / STEP  # 0..1 inside current 16th note
        beat_pos = (max(ft, 0.0) % BEAT) / BEAT  # 0..1 inside current quarter note

        root_hz, chord_hz = PROGRESSION[bar_idx]

        # 1. DRUMS (active during flight, with intro tom pickup at end of title card)
        drm_l = drm_r = 0.0
        sidechain = 1.0
        if in_flight:
            # Analog kick on every beat (beats 0, 1, 2, 3)
            bt = max(ft, 0.0) % BEAT
            sidechain = 1.0 - 0.62 * math.exp(-bt * 13.0)
            if bt < 0.16:
                # Integrated phase of f(u) = 46 + 115 * exp(-u * 55)
                k_ph = two_pi * (46.0 * bt + (115.0 / 55.0) * (1.0 - math.exp(-bt * 55.0)))
                kick = math.sin(k_ph) * math.exp(-bt * 16.0)
                click = noise[i & 4095] * math.exp(-bt * 180.0) * 0.35
                k_val = math.tanh((kick + click) * 1.6) * (0.48 + 0.22 * drive)
                drm_l += k_val
                drm_r += k_val

            # 90s gated-reverb snare on beats 2 and 4 (step_in_bar 4 and 12)
            sn_step = step_in_bar - 4 if step_in_bar >= 4 else -1
            if step_in_bar >= 12:
                sn_step = step_in_bar - 12
            if 0 <= sn_step <= 1:
                st = sn_step * STEP + step_pos * STEP
                if st < 0.20:
                    body = math.sin(two_pi * 182.0 * st) * math.exp(-st * 28.0)
                    # Gated reverb envelope: sustains then drops sharply at 0.17 s
                    gate = 1.0 if st < 0.14 else max(0.0, 1.0 - (st - 0.14) / 0.05)
                    n_l = noise[i & 4095] * gate * 0.42
                    n_r = noise[(i + 173) & 4095] * gate * 0.42
                    s_scale = 0.32 + 0.24 * drive
                    drm_l += (body * 0.55 + n_l) * s_scale
                    drm_r += (body * 0.55 + n_r) * s_scale

            # 16th-note hi-hats (open hat on off-beats, double-time energy in the top-overview finale)
            ht = step_pos * STEP
            h_decay = 18.0 if (step_in_bar % 4 == 2 or overdrive > 0.5) else 65.0
            hat = noise[(i * 3) & 4095] * math.exp(-ht * h_decay) * (0.10 + 0.14 * drive)
            drm_l += hat * 1.15
            drm_r += hat * 0.85

            # Stereo Simmons/Linn tom fill leading into each camera cut (3.5 s, 7.0 s, 10.5 s, 17.5 s)
            for cut_t in CUT_TIMES:
                if cut_t >= flight:
                    continue
                dt_cut = cut_t - ft
                if 0.0 < dt_cut <= 4.0 * STEP:
                    tom_idx = int((4.0 * STEP - dt_cut) / STEP)
                    tt = (4.0 * STEP - dt_cut) % STEP
                    tom_hz = (210.0, 165.0, 130.0, 98.0)[min(tom_idx, 3)]
                    tom = math.sin(two_pi * tom_hz * (1.0 + 0.35 * math.exp(-tt * 30.0)) * tt) * math.exp(-tt * 14.0)
                    pan = tom_idx / 3.0  # pans Left -> Right across the 4-hit fill
                    drm_l += tom * (1.0 - 0.6 * pan) * 0.42
                    drm_r += tom * (0.4 + 0.6 * pan) * 0.42
                elif -0.45 <= dt_cut <= 0.0:
                    # Crash shimmer right on the camera cut
                    ct = -dt_cut
                    cr = noise[(i * 7) & 4095] * math.exp(-ct * 6.5) * 0.22
                    drm_l += cr
                    drm_r += -cr

        # 2. ROLLING 16TH-NOTE SAWTOOTH ARP BASS
        arp_hz = root_hz * ARP_MULT[step_in_bar]
        bass_ph = (bass_ph + two_pi * arp_hz * inv_rate) % two_pi
        raw_bass = _saw(bass_ph) + 0.55 * math.sin(bass_ph * 0.5)
        # Filter envelope opens with each 16th note and widens as speed (drive) climbs
        env_mod = math.exp(-step_pos * 4.2)
        alpha = min(0.88, 0.08 + 0.35 * drive + 0.32 * env_mod * drive)
        bass_lp += alpha * (raw_bass - bass_lp)
        bass_amp = (0.34 * drive * sidechain) if in_flight else (0.14 * math.exp(-max(ft - flight, 0.0) * 1.1))

        # 3. STEREO CHORUS POLYSYNTH PADS
        pad_l = pad_r = 0.0
        for k, ch_hz in enumerate(chord_hz):
            pad_ph_l[k] = (pad_ph_l[k] + two_pi * (ch_hz * 0.9965) * inv_rate) % two_pi
            pad_ph_r[k] = (pad_ph_r[k] + two_pi * (ch_hz * 1.0035) * inv_rate) % two_pi
            pad_l += _saw(pad_ph_l[k])
            pad_r += _saw(pad_ph_r[k])
        pad_gain = 0.055 * (0.45 + 0.55 * drive) * (0.55 + 0.45 * sidechain)
        if ft >= flight:
            pad_gain = 0.065 * math.exp(-(ft - flight) / 1.4)
        elif ft < 0.0:
            pad_gain = 0.045 * (0.4 + 0.6 * (t / max(title, 0.01)))

        # 4. SOARING 90S LEAD SYNTH + STEREO DELAY (builds after launch, octave boost at 10.5 s, fifth harmony at 17.5 s)
        note_hz = LEAD_BARS[bar_idx][step_in_bar]
        if note_hz > 0.0:
            lead_freq = note_hz * (2.0 if ft >= 10.5 else 1.0)
        vib = 1.0 + 0.0045 * math.sin(two_pi * 5.8 * t)
        lead_ph = (lead_ph + two_pi * lead_freq * vib * inv_rate) % two_pi
        lead_env = math.exp(-step_pos * (1.6 if note_hz > 0.0 else 3.0))
        lead_active = 0.0
        if in_flight:
            if ft >= 17.5:
                lead_active = 0.27
            elif ft >= 10.5:
                lead_active = 0.23
            elif ft >= 3.5:
                lead_active = 0.16
            else:
                lead_active = 0.06 * (ft / 3.5)
        fifth_harm = 0.35 * math.sin(lead_ph * 1.5) if ft >= 17.5 else 0.0
        lead_sig = (_saw(lead_ph) + 0.4 * math.sin(lead_ph * 2.0) + fifth_harm) * lead_env * lead_active
        echo_l = delay_l[di]
        echo_r = delay_r[di]
        delay_l[di] = lead_sig * 0.75 + echo_r * 0.36
        delay_r[di] = lead_sig * 0.55 + echo_l * 0.36
        di = (di + 1) % delay_samples

        # 5. SYNCED TURBO ENGINE / PLASMA WHINE (rises with beta, screams into hyper-warp after 17.5 s)
        gear_progress = (max(ft, 0.0) % 3.5) / 3.5 if ft < 17.5 else min(1.5, (ft - 17.5) / 4.5)
        eng_hz = 68.0 + 210.0 * b + 65.0 * gear_progress + 110.0 * overdrive
        eng_ph = (eng_ph + two_pi * eng_hz * inv_rate) % two_pi
        eng = (math.sin(eng_ph) + 0.38 * math.sin(eng_ph * 2.0)) * (0.04 + 0.14 * (b ** 2) + 0.06 * overdrive) if in_flight else 0.0

        # Master stereo mix
        mix_l = drm_l + bass_lp * bass_amp + pad_l * pad_gain + lead_sig * 0.85 + echo_l * 0.45 + eng
        mix_r = drm_r + bass_lp * bass_amp + pad_r * pad_gain + lead_sig * 0.65 + echo_r * 0.55 + eng
        left[i] = mix_l
        right[i] = mix_r

    # Remove DC offset, apply cubic fade-in (0.5 s) and fade-out (1.0 s), and normalize under PEAK (0.85)
    mean_l = sum(left) / n_samples
    mean_r = sum(right) / n_samples
    peak = 1e-9
    for i in range(n_samples):
        t = i * inv_rate
        fade = (min(t / 0.5, 1.0) ** 3) * (min((total - t) / 1.0, 1.0) ** 3)
        left[i] = (left[i] - mean_l) * fade
        right[i] = (right[i] - mean_r) * fade
        al, ar = abs(left[i]), abs(right[i])
        if al > peak:
            peak = al
        if ar > peak:
            peak = ar
    scale = PEAK / peak
    for i in range(n_samples):
        left[i] *= scale
        right[i] *= scale
    return left, right


def write_synthwave_wav(path, title, flight, end, channels=1):
    """Write the 48 kHz 16-bit Synthwave soundtrack (channels=1 mono folddown or channels=2 stereo)."""
    left, right = synthesize_stereo(title, flight, end)
    n = len(left)
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(RATE)
        if channels == 2:
            interleaved = [0] * (2 * n)
            for i in range(n):
                interleaved[2 * i] = int(round(left[i] * 32767))
                interleaved[2 * i + 1] = int(round(right[i] * 32767))
            w.writeframes(struct.pack("<%dh" % (2 * n), *interleaved))
        else:
            mono = [0.5 * (left[i] + right[i]) for i in range(n)]
            pk = max(max(abs(v) for v in mono), 1e-9)
            sc = PEAK / pk
            w.writeframes(struct.pack("<%dh" % n, *(int(round(v * sc * 32767)) for v in mono)))
