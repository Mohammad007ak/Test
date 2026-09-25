# A 60 s upbeat backing track plus sound effects cued to the promo's
# timeline, synthesised from scratch (no samples, nothing licensed).
import wave
import numpy as np

SR = 44100
DUR = 60.0
N = int(SR * DUR)
mix = np.zeros(N)
rng = np.random.default_rng(7)

def t_(sec):
    return np.arange(int(SR * sec)) / SR

def add(sig, at, gain=1.0):
    i = int(at * SR)
    if i >= N:
        return
    j = min(N, i + len(sig))
    mix[i:j] += sig[: j - i] * gain

def env(n, a=0.005, d=0.25):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)

def note(f):
    return 440 * 2 ** ((f - 69) / 12)

# ---------- instruments ----------
def kick():
    t = t_(0.3)
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)

def clap():
    t = t_(0.2)
    n = rng.standard_normal(len(t))
    n = np.convolve(n, [1, -1], "same")
    return n * np.exp(-t * 25) * 0.5

def hat(open_=False):
    t = t_(0.12 if not open_ else 0.25)
    n = np.diff(rng.standard_normal(len(t) + 1))
    return n * np.exp(-t * (60 if not open_ else 18)) * 0.25

def pluck(midi, length=0.5, bright=1.0):
    t = t_(length)
    f = note(midi)
    tri = 2 * np.abs(2 * ((t * f) % 1) - 1) - 1
    sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.3 * bright
    return (tri + sq) * env(len(t), 0.003, 0.18)

def bass(midi, length=0.24):
    t = t_(length)
    f = note(midi)
    return np.tanh(2.2 * np.sin(2 * np.pi * f * t)) * env(len(t), 0.004, 0.16)

def bell(midi, length=1.2):
    t = t_(length)
    f = note(midi)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t)) * env(len(t), 0.002, 0.35)

# ---------- sound effects ----------
def pop():
    t = t_(0.12)
    f = 300 + 900 * np.exp(-t * 40)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.8

def whoosh(length=0.6):
    t = t_(length)
    n = rng.standard_normal(len(t))
    k = np.hanning(len(t))
    lp = np.convolve(n, np.ones(8) / 8, "same")
    return lp * k * 0.6

def coin():
    t = t_(0.35)
    return (np.sin(2 * np.pi * 1976 * t) + 0.6 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 14) * 0.5

def thud():
    t = t_(0.25)
    f = 70 + 120 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)

def drumroll(length):
    out = np.zeros(int(SR * length))
    t = 0.0
    while t < length:
        k = t / length
        s = clap() * (0.3 + 0.5 * k)
        i = int(t * SR)
        out[i : i + len(s)] += s[: len(out) - i]
        t += 0.09 - 0.05 * k
    return out

def riser(length=1.2):
    t = t_(length)
    f = 200 + 1600 * (t / length) ** 2
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / length) * 0.25 + whoosh(length) * 0.4

# ---------- the music ----------
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
# C  G  Am  F (roots and triads, midi)
PROG = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
SAD = [(45, [57, 60, 64]), (41, [57, 60, 65])]  # Am  F, for the problem
MELODY = [72, 74, 76, 79, 76, 74, 72, 67, 69, 72, 74, 72, 76, 74, 72, 74]

def section(start, end, drums=True, hats=True, melody=False, chords=PROG, busy=1.0):
    bar_no = 0
    t = start
    while t < end - 1e-6:
        root, triad = chords[bar_no % len(chords)]
        for b in range(4):
            bt = t + b * BEAT
            if bt >= end:
                break
            if drums:
                if b in (0, 2):
                    add(kick(), bt, 0.9)
                if b in (1, 3):
                    add(clap(), bt, 0.55)
            if hats:
                add(hat(), bt + BEAT / 2, 0.5 * busy)
                if drums:
                    add(hat(), bt, 0.3 * busy)
            # bass on the beat and the offbeat
            add(bass(root), bt, 0.55)
            if drums:
                add(bass(root + 12, 0.14), bt + BEAT / 2, 0.3)
            # chord stabs on the offbeats
            for m in triad:
                add(pluck(m, 0.35, 0.7), bt + BEAT / 2, 0.16)
        if melody:
            for k in range(8):
                mt = t + k * BEAT / 2
                if mt < end and (k % 2 == 0 or bar_no % 2):
                    add(pluck(MELODY[(bar_no * 8 + k) % len(MELODY)], 0.3, 1.2), mt, 0.2)
        t += BAR
        bar_no += 1

# 0–13.5: the problems — hesitant minor plucks, a ticking hat, no drums
section(0.0, 13.5, drums=False, hats=True, chords=SAD, busy=0.6)
add(riser(1.3), 12.2, 1.0)
# 13.5–41.5: Digi Gharz — the groove
section(13.5, 41.5, drums=True, melody=True)
# 41.5–44.5: a skipped payment — the drums drop out
section(41.5, 44.5, drums=False, hats=False, chords=SAD)
# 44.5–60: back to the groove, bigger to the end
section(44.5, 59.0, drums=True, melody=True, busy=1.2)
for m in [48, 60, 64, 67, 72]:
    add(pluck(m, 1.8, 0.8), 59.0, 0.22)
add(kick(), 59.0, 1.0)

# ---------- effects, cued to the picture ----------
scenes = {"bank": 0, "family": 7.5, "reveal": 13.5, "group": 19, "pot": 26, "draw": 33, "guarantee": 41.5, "free": 48.5, "cta": 53.5}
captions = [0.3, 3.1, 7.9, 19.4, 26.3, 33.3, 41.8, 48.8]
for c in captions:
    add(pop(), c, 0.45)
for s in list(scenes.values())[1:]:
    add(whoosh(0.5), s - 0.25, 0.35)
for at in (1.9, 2.6, 3.3):  # the bank's stamps
    add(thud(), at, 0.9)
add(thud(), 14.3, 1.2)  # Digi Gharz lands
add(bell(79, 1.5), 14.8, 0.35)
for i in range(12):  # the twelve land
    add(pop(), 19 + 0.3 + i * 0.16 + 0.5, 0.25)
for i in range(6):  # coins into the pot
    add(coin(), 26 + 0.5 + i * 0.28 + 0.95, 0.45)
add(bell(84, 1.2), 29.2, 0.35)
add(drumroll(4.3), 33.4, 0.8)  # the draw
add(bell(84, 1.6), 37.8, 0.5)
add(bell(88, 1.6), 37.9, 0.35)
add(thud(), 42.6, 0.6)  # the late payer fumes
add(whoosh(0.9), 43.5, 0.5)  # Digi Gharz swoops in
add(bell(79, 1.2), 44.4, 0.35)
for i in range(4):  # the family hops in
    add(pop(), 48.5 + 0.2 + i * 0.22 + 0.4, 0.3)
add(bell(84, 1.4), 53.7, 0.4)

# ---------- master ----------
mix = np.tanh(mix * 0.9)
mix /= np.max(np.abs(mix)) + 1e-9
fade = int(SR * 0.8)
mix[-fade:] *= np.linspace(1, 0, fade)
mix[: int(SR * 0.05)] *= np.linspace(0, 1, int(SR * 0.05))
pcm = (mix * 0.85 * 32767).astype(np.int16)
stereo = np.stack([pcm, pcm], axis=1)
with wave.open(__import__("os").path.join(__import__("os").path.dirname(__file__), "music.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(stereo.tobytes())
print("music.wav", len(pcm) / SR, "s")
