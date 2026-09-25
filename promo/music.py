# A 60 s modern (future-house) backing track plus sound design cued to the
# promo's timeline, synthesised from scratch — no samples, nothing licensed.
# Needs numpy and scipy.  Writes music.wav next to this file.
import os
import wave
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, fftconvolve

SR = 44100
DUR = 60.0
N = int(SR * DUR)
rng = np.random.default_rng(11)

# stereo buses
BUS = {k: np.zeros((N, 2)) for k in ("drums", "bass", "chords", "lead", "fx", "verb")}


def add(bus, sig, at, gain=1.0, pan=0.0, send=0.0):
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l, sig * r], axis=1) * np.sqrt(2)
    i = int(at * SR)
    if i >= N or i + len(sig) <= 0:
        return
    j = min(N, i + len(sig))
    BUS[bus][i:j] += sig[: j - i] * gain
    if send:
        BUS["verb"][i:j] += sig[: j - i] * gain * send


def ts(sec):
    return np.arange(int(SR * sec)) / SR


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR * 0.45), fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


def adsr(n, a=0.005, d=0.2, s=0.0, r=0.05):
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = int(r * SR)
    if rel and rel < n:
        e[-rel:] *= np.linspace(1, 0, rel)
    return e


def saw(f, n, phase=0.0):
    """Band-limited (polyBLEP) sawtooth."""
    dt = np.broadcast_to(np.asarray(f, float) / SR, (n,))
    p = (phase + np.concatenate([[0], np.cumsum(dt)[:-1]])) % 1.0
    y = 2 * p - 1
    a = p < dt
    t = p[a] / dt[a]
    y[a] -= t + t - t * t - 1
    b = p > 1 - dt
    t = (p[b] - 1) / dt[b]
    y[b] -= t * t + t + t + 1
    return y


# ---------------------------------------------------------------- instruments
def supersaw(notes, dur, cutoff=3000, attack=0.02, release=0.3):
    n = int(SR * dur)
    out = np.zeros((n, 2))
    for m in notes:
        for v, det in enumerate(np.linspace(-0.22, 0.22, 7)):
            s = saw(hz(m + det), n, rng.random())
            pan = np.linspace(-0.9, 0.9, 7)[v]
            out[:, 0] += s * np.cos((pan + 1) * np.pi / 4)
            out[:, 1] += s * np.sin((pan + 1) * np.pi / 4)
    out = lp(out, cutoff, 4) / (len(notes) * 4)
    return out * adsr(n, attack, 10, 1, release)[:, None]


def pluck(m, dur=0.4):
    n = int(SR * dur)
    x = saw(hz(m), n, 0) + saw(hz(m + 0.12), n, 0.3) + 0.5 * np.sin(2 * np.pi * hz(m - 12) * ts(dur)[:n])
    # a closing filter gives the "pluck"
    y = np.zeros(n)
    zi = None
    for k in range(0, n, 256):
        fc = 700 + 5200 * np.exp(-k / SR / 0.07)
        sos = butter(2, fc, fs=SR, output="sos")
        if zi is None:
            zi = sosfilt_zi(sos) * 0
        y[k : k + 256], zi = sosfilt(sos, x[k : k + 256], zi=zi)
    return y * adsr(n, 0.002, 0.22, 0.0, 0.03) * 0.5


def bass(m, dur):
    n = int(SR * dur)
    t = ts(dur)[:n]
    sub = np.tanh(1.6 * np.sin(2 * np.pi * hz(m) * t))
    # a growl an octave up so phone speakers still carry the bassline
    mid = lp(saw(hz(m + 12), n), 900, 2) * 0.35
    return (sub + mid) * adsr(n, 0.004, 10, 1, 0.03) * 0.8


def kick():
    t = ts(0.45)
    f = 48 + 140 * np.exp(-t / 0.035)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)
    click = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.004) * 0.4
    return np.tanh(2.0 * (body + click)) * 0.9


def clap():
    t = ts(0.35)
    n = rng.standard_normal(len(t))
    e = np.zeros(len(t))
    for k, off in enumerate((0, 0.011, 0.022)):
        e += (t >= off) * np.exp(-np.maximum(t - off, 0) / (0.006 if k < 2 else 0.09))
    return bp(n, 900, 3500) * e * 0.9


def hat(open_=False):
    t = ts(0.3 if open_ else 0.06)
    return hp(rng.standard_normal(len(t)), 7500, 4) * np.exp(-t / (0.09 if open_ else 0.015)) * 0.5


def snare():
    t = ts(0.2)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    noise = bp(rng.standard_normal(len(t)), 1500, 8000) * np.exp(-t / 0.07)
    return (tone * 0.5 + noise) * 0.7


def tick(high=True):
    t = ts(0.04)
    return bp(rng.standard_normal(len(t)), 2500 if high else 1800, 6000) * np.exp(-t / 0.006) * 0.6


# -------------------------------------------------------------- sound design
def whoosh(dur=0.7, up=True):
    n = int(SR * dur)
    x = rng.standard_normal(n)
    y = np.zeros(n)
    zi = None
    for k in range(0, n, 256):
        u = k / n
        c = 400 * (12 ** (u if up else 1 - u))
        sos = butter(2, [c * 0.6, c * 1.6], "band", fs=SR, output="sos")
        if zi is None:
            zi = sosfilt_zi(sos) * 0
        y[k : k + 256], zi = sosfilt(sos, x[k : k + 256], zi=zi)
    return y * np.hanning(n) * 1.6


def impact(dur=1.6, low=42):
    t = ts(dur)
    f = low + 90 * np.exp(-t / 0.06)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.5)
    crack = lp(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.05) * 0.6
    return np.tanh(1.8 * (boom + crack))


def stamp():
    t = ts(0.5)
    thump = np.sin(2 * np.pi * np.cumsum(60 + 80 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.12)
    slap = bp(rng.standard_normal(len(t)), 500, 2500) * np.exp(-t / 0.025)
    return np.tanh(2 * (thump + 0.8 * slap))


def riser(dur):
    n = int(SR * dur)
    u = np.linspace(0, 1, n)
    noise = whoosh(dur, True) * u
    f = 180 + 900 * u**2
    tone = sum(saw(f * r, n) for r in (1, 1.005, 1.5)) * 0.12
    return (noise * 0.6 + lp(tone, 4000)) * u**1.5


def reverse_swell(notes, dur=1.5):
    s = supersaw(notes, dur, 5000, 0.001, 0.05)
    t = np.arange(len(s)) / SR
    s *= np.exp(-t / 0.5)[:, None]
    return s[::-1] * 1.4


def coin():
    t = ts(0.4)
    parts = [(2600, 1), (3900, 0.6), (6100, 0.35), (8300, 0.2)]
    return sum(a * np.sin(2 * np.pi * f * (1 + rng.normal(0, 0.004)) * t) for f, a in parts) * np.exp(-t / 0.09) * 0.25


def mallet(m):
    t = ts(0.35)
    f = hz(m)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / 0.02)) * np.exp(-t / 0.12) * 0.6


def heartbeat():
    t = ts(0.35)
    return np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.09)


# ------------------------------------------------------------------- harmony
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
# Am9 · Fmaj9 · Cadd9 · G6/9 — roots for the bass
PROG = [
    (33, [57, 60, 64, 67, 71]),
    (29, [53, 57, 60, 64, 67]),
    (36, [55, 60, 64, 67, 74]),
    (31, [55, 59, 62, 67, 69]),
]
DARK = [(33, [45, 52, 57, 60, 64]), (29, [41, 48, 53, 57, 60])]
# the hook: (beat within a four-bar phrase, midi note)
HOOK = [
    (0, 76), (0.75, 74), (1.5, 72), (2.5, 69), (3.5, 72),
    (4, 76), (4.75, 79), (5.5, 76), (6.5, 74),
    (8, 72), (8.75, 74), (9.5, 76), (10.5, 79), (11.5, 81),
    (12, 79), (12.75, 76), (13.5, 74), (14.5, 72),
]


def groove(start, end, kick_on=True, clap_on=True, hats=2, lead=False, lead_oct=False, cutoff=(5500, 5500), bassline=True, chord_gain=1.2):
    """House groove on its own grid from `start`; chords sweep `cutoff`."""
    bars = int(np.ceil((end - start) / BAR))
    for b in range(bars):
        t0 = start + b * BAR
        root, chord = PROG[b % 4]
        u = b / max(1, bars - 1)
        fc = cutoff[0] * (cutoff[1] / cutoff[0]) ** u
        length = min(BAR, end - t0)
        if length <= 0:
            break
        add("chords", supersaw(chord, length + 0.3, fc, 0.01, 0.3), t0, chord_gain, send=0.35)
        for k in range(4):
            bt = t0 + k * BEAT
            if bt >= end:
                break
            if kick_on:
                add("drums", kick(), bt, 0.55)
            if clap_on and k in (1, 3):
                add("drums", clap(), bt, 0.6, send=0.25)
            if hats >= 1:
                add("drums", hat(True), bt + BEAT / 2, 0.35, pan=0.2)
            if hats >= 2:
                for s in (0.25, 0.75):
                    add("drums", hat(), bt + s * BEAT, 0.22, pan=-0.3)
            if bassline:
                # offbeat house bass, with a pickup to the next root
                add("bass", bass(root + 12, BEAT * 0.42), bt + BEAT / 2, 0.3)
                if k == 3:
                    add("bass", bass(root + 24, BEAT * 0.2), bt + BEAT * 0.75, 0.22)
        if lead:
            for beat, m in HOOK:
                if 4 * (b % 4) <= beat < 4 * (b % 4) + 4:
                    at = t0 + (beat - 4 * (b % 4)) * BEAT
                    if at < end:
                        p = pluck(m, 0.45)
                        add("lead", p, at, 1.0, pan=-0.15, send=0.3)
                        # dotted-eighth echo, panned the other way
                        add("lead", p, at + BEAT * 0.75, 0.4, pan=0.5, send=0.3)
                        if lead_oct:
                            add("lead", pluck(m + 12, 0.35), at, 0.35, pan=0.2, send=0.3)


def sidechain(start, end, depth=0.7):
    t = np.arange(N) / SR
    e = np.ones(N)
    m = (t >= start) & (t < end)
    ph = ((t[m] - start) % BEAT) / BEAT
    e[m] = 1 - depth * np.exp(-ph * BEAT / 0.09) * np.minimum(1, ph * BEAT / 0.004)
    return e


# =================================================================== score
# 0–13.5  the problem: a dark filtered pad, a clock ticking
for b in range(4):
    root, chord = DARK[b % 2]
    t0 = b * 3.2
    add("chords", supersaw(chord, 3.6, 1300, 0.6, 0.8), t0, 1.6, send=0.5)
    add("bass", bass(root + 12, 3.0), t0, 0.12)
for k in range(int(12.6 / 0.5)):
    add("drums", tick(k % 2 == 0), k * 0.5, 0.35, pan=0.3 if k % 2 else -0.3, send=0.1)
for k in range(8):  # a heartbeat that quickens as the family chaos builds
    at = 7.6 + k * 0.75
    add("fx", heartbeat(), at, 0.5)
    add("fx", heartbeat(), at + 0.2, 0.35)
add("fx", riser(2.0), 11.4, 0.55, send=0.3)
add("fx", reverse_swell(PROG[0][1], 1.4), 12.1, 0.55)

# 13.5–19  the reveal: impact, then the groove opens up
groove(13.5, 19.0, clap_on=False, hats=1, cutoff=(500, 4000))
# 19–33  the group and the pot: full groove, the hook comes in with the pot
groove(19.0, 26.0, cutoff=(4500, 5500))
groove(26.0, 33.0, lead=True, cutoff=(5500, 5500))
# 33–37.8  the draw: drums drop out, a snare roll and the filter climb
groove(33.0, 37.8, kick_on=False, clap_on=False, hats=0, cutoff=(900, 6000), bassline=False, chord_gain=2.0)
roll_t = 33.4
while roll_t < 37.7:
    u = (roll_t - 33.4) / 4.3
    add("drums", snare(), roll_t, 0.25 + 0.5 * u, send=0.2)
    roll_t += BEAT / (1 if u < 0.3 else 2 if u < 0.6 else 4 if u < 0.85 else 8)
add("fx", riser(4.2), 33.5, 0.45)
# 37.8–41.5  the winner: the drop
groove(37.8, 41.5, lead=True, lead_oct=True, cutoff=(6000, 6000))
# 41.5–44.5  a missed payment: everything sinks under a low filter
groove(41.5, 43.5, kick_on=False, clap_on=False, hats=0, cutoff=(350, 250), bassline=False, chord_gain=2.0)
for k in range(4):
    add("fx", heartbeat(), 41.8 + k * 0.6, 0.7)
    add("fx", heartbeat(), 42.0 + k * 0.6, 0.45)
# 44.5–59  Digi Gharz has it covered — the groove, fuller, to the end
groove(44.5, 48.5, lead=True, cutoff=(5500, 6000))
groove(48.5, 59.0, lead=True, lead_oct=True, cutoff=(6000, 6000))
# the last chord rings out
add("chords", supersaw([45, 57, 60, 64, 67, 71, 76], 2.5, 5000, 0.005, 1.5), 59.0, 1.6, send=0.6)
add("bass", bass(33, 1.2), 59.0, 0.6)
add("drums", kick(), 59.0, 0.6)
add("fx", impact(2.0), 59.0, 0.45, send=0.3)

# ------------------------------------------------ sound effects, cued to the picture
scenes = [7.5, 13.5, 19, 26, 33, 41.5, 48.5, 53.5]
for s in scenes:
    add("fx", whoosh(0.6), s - 0.35, 0.28, pan=0.0, send=0.2)
for c in [0.3, 3.1, 7.9, 19.4, 26.3, 33.3, 41.8, 48.8]:  # captions appear
    add("fx", tick(), c, 0.22, send=0.3)
for at in (1.9, 2.6, 3.3):  # the bank's stamps
    add("fx", stamp(), at, 0.8, send=0.25)
add("fx", impact(), 13.5, 0.9, send=0.4)  # Digi Gharz lands
SCALE = [69, 72, 74, 76, 79, 81, 84, 86, 88, 91, 93, 96]
for i in range(12):  # the twelve land, rising up the scale
    add("fx", mallet(SCALE[i] - 12), 19.8 + i * 0.16, 0.3, pan=-0.6 + i * 0.11, send=0.35)
for i in range(6):  # coins into the pot
    add("fx", coin(), 26.5 + i * 0.28 + 0.95, 0.35, pan=rng.uniform(-0.4, 0.4), send=0.3)
add("fx", impact(1.8, 38), 37.8, 1.0, send=0.5)  # the winner
add("fx", whoosh(0.8, False), 41.3, 0.4)
add("fx", stamp(), 42.6, 0.6)  # the late payer fumes
add("fx", reverse_swell(PROG[0][1], 1.0), 43.5, 0.5)
add("fx", whoosh(0.9), 43.5, 0.45)  # Digi Gharz swoops in
add("fx", impact(1.4, 45), 44.5, 0.7, send=0.4)
for i in range(4):  # the family hops in
    add("fx", mallet([76, 79, 81, 84][i]), 49.1 + i * 0.22, 0.3, send=0.3)
add("fx", reverse_swell(PROG[2][1], 1.0), 52.6, 0.45)
add("fx", impact(1.6, 44), 53.6, 0.7, send=0.4)

# =================================================================== mix
duck = sidechain(13.5, 33.0) * sidechain(37.8, 41.5) * sidechain(44.5, 59.0)
duck = duck[:, None]
music = BUS["chords"] * duck + BUS["bass"] * duck + BUS["lead"] * (0.6 + 0.4 * duck) + BUS["drums"]

# the missed payment: music sinks under a low-pass (smoothly in and out)
t = np.arange(N) / SR
w = np.clip(np.minimum((t - 41.3) / 0.35, (44.5 - t) / 0.2), 0, 1)[:, None]
music = music * (1 - w) + lp(music, 280, 4) * w

# reverb: a stereo decaying-noise impulse
ir_t = np.arange(int(SR * 2.4)) / SR
ir = np.stack([rng.standard_normal(len(ir_t)), rng.standard_normal(len(ir_t))], 1)
ir = lp(ir, 5000) * np.exp(-ir_t / 0.55)[:, None]
ir /= np.sqrt((ir**2).sum(0))
wet = np.stack([fftconvolve(hp(BUS["verb"][:, c], 250), ir[:, c])[:N] for c in range(2)], 1)

mix = music + BUS["fx"] + wet * 0.55
mix = hp(mix, 28)
mix = np.tanh(mix * 0.8) / 0.8  # glue
mix /= np.max(np.abs(mix)) + 1e-9
fade = int(SR * 0.6)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
pcm = (mix * 0.89 * 32767).astype(np.int16)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.wav")
with wave.open(out, "wb") as f:
    f.setnchannels(2)
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes(pcm.tobytes())
print(out, len(pcm) / SR, "s")
