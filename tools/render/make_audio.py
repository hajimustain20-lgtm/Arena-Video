#!/usr/bin/env python3
"""
Beat bed for the Neon Club clip -- 142 BPM, 11.00 s, A minor.

Everything is synthesised from scratch (no samples, no external audio):
  kick      4-on-the-floor, pitch-swept sine + click
  clap      band-passed noise bursts on 2 and 4
  hats      8th / 16th shaker, swung
  bass      offbeat sub following the kick
  pad       sustained Am9 stack, low-passed
  riser     noise sweep over the 4 beats before the laser cut
  impact    sub boom + crash on the cut (beat 12)
  whoosh    laser sweep sfx across the transition
  shimmer   bell arpeggio in the club section

Writes 16-bit 48 kHz stereo WAV.
Usage:  python make_audio.py --out bed.wav
"""
from __future__ import annotations

import argparse
import wave

import numpy as np

SR = 48000
BPM = 142.0
BEAT = 60.0 / BPM
DUR = 11.0
N = int(round(SR * DUR))
rng = np.random.default_rng(2024)


def t_(sec):
    return np.arange(int(round(SR * sec)), dtype=np.float64) / SR


def env_ad(n, a, d, curve=2.0):
    t = np.arange(n, dtype=np.float64) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0)
    return e * np.exp(-np.maximum(t - a, 0) * d / max(curve, 1e-3))


def add(buf, sig, at, gain=1.0):
    i = int(round(at * SR))
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    if i < 0:
        sig = sig[-i:]
        n = min(len(sig), len(buf))
        i = 0
    buf[i:i + n] += sig[:n] * gain


def lp(x, fc, order=2):
    """one-pole cascade low-pass, cheap but fine for a bed"""
    y = x.copy()
    for _ in range(order):
        a = np.exp(-2 * np.pi * fc / SR)
        y = np.concatenate([[y[0]], y[1:]]) * 0 + y  # keep it simple
        out = np.empty_like(y)
        acc = y[0]
        for i in range(len(y)):  # too slow for full buffers; use fft below
            acc = a * acc + (1 - a) * y[i]
            out[i] = acc
        y = out
    return y


def lp_fft(x, fc, slope=2.0):
    n = len(x)
    if n == 0:
        return x
    z = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    h = 1.0 / (1.0 + (f / max(fc, 1.0)) ** slope)
    return np.fft.irfft(z * h, n)


def hp_fft(x, fc, slope=2.0):
    n = len(x)
    if n == 0:
        return x
    z = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    h = 1.0 - 1.0 / (1.0 + (f / max(fc, 1.0)) ** slope)
    return np.fft.irfft(z * h, n)


def bp_fft(x, lo, hi, slope=2.0):
    return hp_fft(lp_fft(x, hi, slope), lo, slope)


# ---------------------------------------------------------------- voices ----
def kick(vel=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 46.0 + 118.0 * np.exp(-t * 42.0)          # pitch drop
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 6.2)
    click = rng.normal(0, 1, n) * np.exp(-t * 480) * 0.45
    click = lp_fft(click, 5200)
    return (body + click) * vel * 0.92


def clap(vel=1.0):
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    nz = rng.normal(0, 1, n)
    nz = bp_fft(nz, 900, 5200, 1.6)
    e = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.023)):
        idx = int(off * SR)
        seg = np.arange(n - idx) / SR
        e[idx:] += np.exp(-seg * (58 - k * 8)) * (1.0 - 0.22 * k)
    return nz * e * vel * 0.34


def hat(vel=1.0, decay=70.0):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    nz = hp_fft(rng.normal(0, 1, n), 7200, 1.4)
    return nz * np.exp(-t * decay) * vel * 0.16


def bass_note(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) * 0.70
    sig += np.sin(2 * np.pi * freq * 2 * t) * 0.22
    sig += np.sin(2 * np.pi * freq * 3 * t) * 0.08
    e = np.minimum(t / 0.008, 1.0) * np.exp(-t * 3.2)
    e *= np.clip((dur - t) / 0.05, 0, 1)
    return lp_fft(sig * e, 260, 1.8) * vel


def pad_note(freqs, dur, vel=1.0, cutoff=1500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for k, f in enumerate(freqs):
        det = 1.0 + 0.0035 * (k - len(freqs) / 2)
        sig += np.sin(2 * np.pi * f * det * t + rng.uniform(0, 6.28)) * 0.16
        sig += np.sin(2 * np.pi * f * det * 2.0 * t) * 0.045
    e = np.minimum(t / 0.9, 1.0) * np.clip((dur - t) / 0.7, 0, 1)
    return lp_fft(sig * e, cutoff, 2.0) * vel


def sub_boom(freq=42.0, dur=1.6, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1.0 + 1.2 * np.exp(-t * 26))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 2.6) * vel


def noise_sweep(dur, lo0, hi0, lo1, hi1, vel=1.0, steps=96):
    """band-passed noise with a moving centre frequency (riser / whoosh)"""
    n = int(dur * SR)
    out = np.zeros(n)
    seg = n // steps + 1
    for k in range(steps):
        u = k / max(steps - 1, 1)
        c = 2 ** (np.log2(lo0) + (np.log2(hi0) - np.log2(lo0)) * u) if False else lo0 + (hi0 - lo0) * u
        c2 = lo1 + (hi1 - lo1) * u
        i0, i1 = k * seg, min((k + 1) * seg + 128, n)
        if i0 >= n:
            break
        nz = rng.normal(0, 1, i1 - i0)
        nz = bp_fft(nz, min(c, c2), max(c, c2) * 1.35, 1.4)
        w = np.hanning(i1 - i0) if k not in (0, steps - 1) else np.ones(i1 - i0)
        out[i0:i1] += nz * w
    t = np.arange(n) / SR
    e = np.minimum(t / 0.05, 1.0) * np.clip((dur - t) / (dur * 0.25), 0, 1)
    return out * e * vel


def bell(freq, dur=0.9, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) * np.exp(-t * 3.0)
    sig += np.sin(2 * np.pi * freq * 2.01 * t) * np.exp(-t * 6.0) * 0.4
    sig += np.sin(2 * np.pi * freq * 3.02 * t) * np.exp(-t * 9.0) * 0.22
    return sig * vel * 0.18


# ----------------------------------------------------------------- build ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="bed.wav")
    ap.add_argument("--gain", type=float, default=0.92)
    args = ap.parse_args()

    n_beats = int(DUR / BEAT)                 # 26
    CUT = 12                                  # beat index of the laser cut
    L = np.zeros(N)
    R = np.zeros(N)

    def st(sig, at, g=1.0, pan=0.0):
        """stereo add with constant-power pan"""
        l = np.cos((pan + 1) * np.pi / 4) * 1.4142
        r = np.sin((pan + 1) * np.pi / 4) * 1.4142
        add(L, sig, at, g * l)
        add(R, sig, at, g * r)

    # --- drums ------------------------------------------------------------
    for b in range(n_beats):
        t = b * BEAT
        fade = 1.0
        if b >= CUT:
            fade = 1.0
        st(kick(1.1 if b % 4 == 0 else 0.95), t, 0.95 * fade)
    for b in range(n_beats):
        if b % 4 in (2, 3):
            st(clap(0.9 if b % 4 == 3 else 0.7), b * BEAT, 0.85)
    # hats: 8ths with a 16th skip for groove, light swing
    for k in range(n_beats * 2):
        t = k * BEAT / 2 + (0.012 if k % 2 else 0.0)
        acc = 1.0 if k % 2 else 0.55
        st(hat(acc), t, 0.9, pan=0.35 if k % 2 else -0.2)
    for k in range(n_beats * 4):
        if k % 4 == 3:
            st(hat(0.35, 110.0), k * BEAT / 4, 0.5, pan=-0.45)

    # --- bass (A minor) ---------------------------------------------------
    roots = [55.00, 55.00, 65.41, 49.00]      # A1 A1 C2 G1
    for b in range(n_beats):
        root = roots[(b // 2) % len(roots)]
        # pushed offbeat figure
        st(bass_note(root, BEAT * 0.42, 0.85), b * BEAT + BEAT * 0.48, 0.55)
        if b % 4 == 3:
            st(bass_note(root * 1.5, BEAT * 0.30, 0.6), b * BEAT + BEAT * 0.78, 0.35)

    # --- pad --------------------------------------------------------------
    chords = [
        [220.00, 261.63, 329.63, 392.00],     # Am7
        [196.00, 246.94, 293.66, 349.23],     # G
        [174.61, 220.00, 261.63, 329.63],     # Fmaj7
        [164.81, 207.65, 246.94, 329.63],     # E
    ]
    bar = BEAT * 4
    for k in range(int(DUR / bar) + 1):
        ch = chords[k % len(chords)]
        st(pad_note(ch, bar * 1.02, 0.60, cutoff=1250), k * bar, 0.22)
        st(pad_note([f / 2 for f in ch], bar * 1.02, 0.42, cutoff=600), k * bar, 0.16)

    # --- riser into the cut ----------------------------------------------
    ris = noise_sweep(BEAT * 4.2, 400, 900, 2600, 9000, 0.9)
    st(ris, CUT * BEAT - BEAT * 4.0, 0.30)
    st(sub_boom(46, 1.2, 0.5), CUT * BEAT - BEAT * 4.0, 0.25)

    # --- impact on the cut ------------------------------------------------
    st(sub_boom(38, 2.0, 1.0), CUT * BEAT, 0.85)
    crash = hp_fft(rng.normal(0, 1, int(2.2 * SR)), 3800, 1.2) * np.exp(-np.arange(int(2.2 * SR)) / SR * 2.4)
    st(crash * 0.30, CUT * BEAT, 0.75)
    # laser whoosh rides the wipe (2 beats)
    wh = noise_sweep(BEAT * 1.9, 9000, 3200, 2600, 700, 0.9)
    st(wh, CUT * BEAT - BEAT * 0.15, 0.34)
    ping = np.sin(2 * np.pi * 2350 * np.arange(int(0.5 * SR)) / SR) * np.exp(-np.arange(int(0.5 * SR)) / SR * 9)
    st(ping * 0.10, CUT * BEAT + BEAT * 0.15, 0.5)

    # --- club-section shimmer --------------------------------------------
    scale = [880.00, 1046.50, 1174.66, 1318.51, 1567.98]
    for k in range(24):
        t = CUT * BEAT + BEAT * 0.5 + k * BEAT / 2
        if t > DUR - 0.4:
            break
        f = scale[int(rng.integers(0, len(scale)))]
        st(bell(f, 1.1, 0.55), t, 0.5, pan=float(rng.uniform(-0.7, 0.7)))

    # --- space / glue -----------------------------------------------------
    def verb(x, decay=0.55, mix=0.22):
        n = int(0.6 * SR)
        ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / SR * (5.0 / decay))
        ir = lp_fft(ir, 6000)
        ir /= np.max(np.abs(ir)) + 1e-9
        wet = np.fft.irfft(np.fft.rfft(x, len(x) + n) * np.fft.rfft(ir, len(x) + n), len(x) + n)[:len(x)]
        return x * (1 - mix) + wet * mix * 0.55

    L, R = verb(L), verb(R, 0.6, 0.26)

    # --- master -----------------------------------------------------------
    st_mix = np.stack([L, R], 1)
    # gentle glue compression (soft knee on peaks)
    peak = np.max(np.abs(st_mix)) + 1e-9
    st_mix = np.tanh(st_mix / peak * 1.15) / np.tanh(1.15)
    # fades
    t = np.arange(N) / SR
    fade_in = np.clip(t / 0.18, 0, 1)[:, None]
    fade_out = np.clip((DUR - t) / 0.55, 0, 1)[:, None]
    st_mix *= fade_in * fade_out * args.gain
    st_mix *= 0.92 / (np.max(np.abs(st_mix)) + 1e-9)

    pcm = (np.clip(st_mix, -1, 1) * 32767.0).astype("<i2")
    with wave.open(args.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", args.out, pcm.shape, f"{DUR:.2f}s @ {BPM:.0f} BPM")


if __name__ == "__main__":
    main()
