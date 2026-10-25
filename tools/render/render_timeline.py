#!/usr/bin/env python3
"""
Neon Club -- shot renderer.

Turns the two keyframes into a moving 1080p30 sequence, beat-locked to 142 BPM.

    shot 02  frames   0..151   (5.07 s = 12 beats)  entrance push-in   <- image-2
    cut      frames 152..177   (0.87 s)             cyan laser wipe
    shot 03  frames 178..329   (5.07 s = 12 beats)  club wide push     <- image-1

Design notes
------------
* The camera move is a physical dolly simulation, not a cross-fade: a smooth
  inverse-mapped warp with a per-row depth term (shot 03) so the near floor
  expands faster than the far ceiling -> true travel parallax.
* Every light effect is driven by a beat clock derived from BPM, so pulses,
  crowd bounce and the laser cut all land on the grid.
* Shot 02 keeps the subject rigid on purpose: no local warps, no morphing.
  Only global camera + light passes touch those pixels.
* Deterministic: frame N is always identical, so re-renders are stable.

Usage
-----
    python render_timeline.py --out master.mp4 [--audio bed.wav]
    python render_timeline.py --preview 0 80 151 --outdir /tmp/prev
    python render_timeline.py --start 0 --end 152 --out shot02.mp4
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import cv2
import numpy as np

cv2.setNumThreads(2)

# ---------------------------------------------------------------- format ----
W, H = 1920, 1080
FPS = 30
BPM = 142.0
BEAT = 60.0 / BPM
N2, NT, N3 = 152, 26, 152
N_TOTAL = N2 + NT + N3                 # 330 frames = 11.00 s exactly
T2, T3 = N2 / FPS, N3 / FPS
SRC_W, SRC_H = 2560, 1440

IMG2 = "/tmp/arena-coding-uploads/image-2.png"
IMG1 = "/tmp/arena-coding-uploads/image-1.png"

CYAN = np.array([1.00, 0.90, 0.32], np.float32)
MAGENTA = np.array([0.86, 0.30, 0.96], np.float32)
GOLD = np.array([0.30, 0.68, 1.00], np.float32)
WHITE = np.array([1.0, 1.0, 1.0], np.float32)


# ------------------------------------------------------------------ math ----
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ease_steady(u):
    """Mostly linear dolly, soft on both ends -- what a motion-control head does."""
    return 0.62 * smoothstep(u) + 0.38 * u


def ease_out(u):
    return 1.0 - (1.0 - np.clip(u, 0, 1)) ** 2.6


def ease_in(u):
    return np.clip(u, 0, 1) ** 2.2


def _noise(rng, w, h, cell):
    gw, gh = max(2, int(w // cell)), max(2, int(h // cell))
    g = rng.random((gh, gw)).astype(np.float32)
    out = cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = float(out.min()), float(out.max())
    return (out - lo) / max(hi - lo, 1e-6)


def _fbm(rng, w, h, base_cell, octaves=4):
    out = np.zeros((h, w), np.float32)
    amp, cell, norm = 1.0, base_cell, 0.0
    for _ in range(octaves):
        out += amp * _noise(rng, w, h, max(2, cell))
        norm += amp
        amp *= 0.5
        cell = max(2, cell / 2)
    return np.clip(out / norm, 0, 1)


# --------------------------------------------------------------- assets ----
def load_scene(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    img = cv2.resize(img, (SRC_W, SRC_H), interpolation=cv2.INTER_LANCZOS4)
    # recover the detail lost in the 1672 -> 2560 upscale
    soft = cv2.GaussianBlur(img, (0, 0), 1.15)
    img = cv2.addWeighted(img, 1.30, soft, -0.30, 0)

    f = img.astype(np.float32) / 255.0
    v = f.max(axis=2)
    s = (f.max(axis=2) - f.min(axis=2)) / np.maximum(v, 1e-3)
    # emitter mask: bright and coloured = a neon tube / practical light
    m = np.clip((v - 0.55) / 0.45, 0, 1) ** 1.3
    m *= 0.45 + 0.75 * np.clip(s * 2.2, 0, 1)
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 2.0)
    rgba = np.dstack([img, (np.clip(m, 0, 1) * 255).astype(np.uint8)])
    return np.ascontiguousarray(rgba)


def build_vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (xx / W - 0.5) * 2, (yy / H - 0.5) * 2
    r = np.sqrt(nx * nx + ny * ny * 0.86)
    v = 1.0 - 0.34 * np.clip((r - 0.62) / 0.90, 0, 1) ** 1.5
    return v.astype(np.float32)[..., None]


def build_particles(rng, n):
    out = []
    for _ in range(n):
        out.append(dict(
            x=rng.uniform(-0.05, 1.05), y=rng.uniform(-0.05, 1.05),
            r=rng.uniform(0.003, 0.017), a=rng.uniform(0.04, 0.26),
            vy=rng.uniform(-0.016, -0.003), vx=rng.uniform(-0.008, 0.008),
            ph=rng.uniform(0, 6.28),
            col=[MAGENTA, CYAN, GOLD][int(rng.integers(0, 3))] * float(rng.uniform(0.6, 1.0)),
        ))
    return out


def draw_particles(parts, t, scale=0.25, shape=(H, W)):
    h, w = int(shape[0] * scale), int(shape[1] * scale)
    canvas = np.zeros((h, w, 3), np.float32)
    for p in parts:
        x = (p["x"] + p["vx"] * t + 0.004 * np.sin(t * 1.6 + p["ph"])) * w
        y = ((p["y"] + p["vy"] * t) % 1.10 - 0.02) * h
        r = max(1, int(p["r"] * w * (1.0 + 0.22 * np.sin(t * 1.9 + p["ph"]))))
        fl = 0.5 + 0.5 * np.sin(t * 2.7 + p["ph"])
        col = tuple(float(c * p["a"] * (0.45 + 0.55 * fl)) for c in p["col"])
        cv2.circle(canvas, (int(x), int(y)), r, col, -1, lineType=cv2.LINE_AA)
    canvas = cv2.GaussianBlur(canvas, (0, 0), max(1.0, 7.0 * scale))
    return cv2.resize(canvas, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


# --------------------------------------------------------------- cameras ----
class Cam:
    """Dolly state: zoom about a normalised source point + pixel offset."""

    def __init__(self, s=1.0, cx=0.5, cy=0.5, ox=0.0, oy=0.0, rot=0.0):
        self.s, self.cx, self.cy = s, cx, cy
        self.ox, self.oy = ox, oy          # lens offset in output px
        self.rot = rot

    def src_xy(self, x, y):
        """Output pixel -> source pixel (vectorised over arrays)."""
        a = SRC_W / (self.s * W)
        b = SRC_H / (self.s * H)
        sx = SRC_W * self.cx + (x - W * 0.5) * a + self.ox * a
        sy = SRC_H * self.cy + (y - H * 0.5) * b + self.oy * b
        return sx, sy


def handheld(t, amp=1.5, seed=3):
    """Smooth gimbal float -- deliberately no high frequency jitter."""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 6)
    fr = np.array([0.11, 0.19, 0.33, 0.17, 0.26, 0.09])
    dx = amp * (0.62 * np.sin(6.283185 * fr[0] * t + ph[0]) + 0.38 * np.sin(6.283185 * fr[1] * t + ph[1]))
    dy = amp * (0.62 * np.sin(6.283185 * fr[2] * t + ph[2]) + 0.38 * np.sin(6.283185 * fr[3] * t + ph[3]))
    return dx, dy


# ----------------------------------------------------------------- scene ----
class Scene:
    def __init__(self, name, path, seed, move, look, depth_parallax=0.0):
        self.name = name
        self.src = load_scene(path)
        self.move = move
        self.look = look
        self.depth_parallax = depth_parallax
        rng = np.random.default_rng(seed)
        self.haze_a = _fbm(rng, 480, 270, 64, 4)
        self.haze_b = _fbm(rng, 480, 270, 26, 3)
        self.phase_field = _fbm(np.random.default_rng(seed + 5), 160, 90, 14, 3)
        self.phase_field2 = _fbm(np.random.default_rng(seed + 9), 96, 54, 7, 3)
        self.parts = build_particles(rng, look.get("particles", 22))
        # static coordinate grids (built once, reused every frame)
        self.gx, self.gy = np.meshgrid(
            np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32)
        )
        yy = (np.arange(H, dtype=np.float32) / H)[:, None]
        self.crowd_band = (smoothstep((yy - 0.30) / 0.26) * (1.0 - 0.72 * smoothstep((yy - 0.88) / 0.14)))
        self.crowd_band = (self.crowd_band * np.ones((1, 1), np.float32)).astype(np.float32)

    # ---- geometry ---------------------------------------------------------
    def maps(self, cam, t):
        """Build dst->src maps: dolly + per-row depth + crowd sway."""
        if self.depth_parallax > 0:
            # depth proxies: 1 = near (bottom of frame), 0 = far (top)
            yy = (np.arange(H, dtype=np.float32) / H)[:, None]
            depth = np.clip((yy - 0.10) / 0.90, 0, 1) ** 0.85
            s_row = 1.0 + (cam.s - 1.0) * (1.0 + self.depth_parallax * (depth - 0.55) * 2.0)
            s_row = np.clip(s_row, 0.6, 3.0)
            a = (SRC_W / W) / s_row
            b = (SRC_H / H) / s_row
            sx = SRC_W * cam.cx + (self.gx - W * 0.5) * a + cam.ox * a
            sy = SRC_H * cam.cy + (self.gy - H * 0.5) * b + cam.oy * b
        else:
            sx, sy = cam.src_xy(self.gx, self.gy)

        if self.look.get("sway", 0) > 0:
            amp = self.look["sway"]
            ph = cv2.resize(self.phase_field, (W, H), interpolation=cv2.INTER_LINEAR)
            ph2 = cv2.resize(self.phase_field2, (W, H), interpolation=cv2.INTER_LINEAR)
            # half-note groove, with a second, slower layer for drift
            w = 6.283185 * (t / (2 * BEAT)) + 2.9 * ph + 1.3 * ph2
            band = self.crowd_band * (0.55 + 0.65 * ph2)
            sx = sx + amp * band * np.sin(w)
            sy = sy + 0.70 * amp * band * np.cos(w)
            # a little vertical bounce right on the kick
            kick = (0.5 + 0.5 * np.cos(6.283185 * ((t / BEAT) % 1.0))) ** 2.0
            sy = sy - 0.35 * amp * band * kick * float(self.look.get("bounce", 0.0))
        return (np.ascontiguousarray(sx, dtype=np.float32),
                np.ascontiguousarray(sy, dtype=np.float32))

    def warp(self, cam, t):
        sx, sy = self.maps(cam, t)
        rgb = cv2.remap(self.src[..., :3], sx, sy, interpolation=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REFLECT)
        alpha = cv2.remap(self.src[..., 3], sx, sy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        frame = rgb.astype(np.float32) * (1.0 / 255.0)
        light = alpha.astype(np.float32) * (1.0 / 255.0)
        return frame, light

    # ---- render -----------------------------------------------------------
    def render(self, t):
        cam = self.move(t)
        frame, light = self.warp(cam, t)
        look = self.look

        beat_phase = (t / BEAT) % 1.0
        bar = (t / (2 * BEAT)) % 1.0
        beat4 = (t / (4 * BEAT)) % 1.0
        pulse = 0.5 + 0.5 * np.cos(6.283185 * bar)                  # half-note breathe
        # raised-cosine kick: peaks on the beat but is continuous everywhere,
        # so the light breathes instead of strobing
        kick = (0.5 + 0.5 * np.cos(6.283185 * beat_phase)) ** 2.2
        glow = 0.42 * pulse + 0.58 * kick

        # 1. neon breathing on the practicals
        frame *= (1.0 + look["pulse"] * glow * light)[..., None]
        frame += (look["pulse_glow"] * glow * light)[..., None] * (CYAN * 0.5 + MAGENTA * 0.5)

        # 2. drifting haze, lit by the scene
        hz = look.get("haze", 0.0)
        if hz:
            hh, hw = self.haze_a.shape
            ox = int((t * 0.055) % 1.0 * hw)
            oy = int((0.5 + 0.10 * np.sin(0.42 * t)) % 1.0 * hh)
            h = 0.58 * np.roll(self.haze_a, -ox, axis=1) + 0.42 * np.roll(self.haze_b, -oy, axis=0)
            lum = cv2.resize(light, (hw, hh), interpolation=cv2.INTER_AREA)
            lum = cv2.GaussianBlur(lum, (0, 0), 5)
            m = h * (0.30 + 1.15 * lum)
            m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
            tint = (CYAN * 0.30 + MAGENTA * 0.55)[None, None, :]
            frame += (hz * m)[..., None] * tint

        # 3. floating bokeh dust
        pa = look.get("particles_a", 0.0)
        if pa:
            frame += pa * draw_particles(self.parts, t)

        # 4. booth accent: a warm hit on the downbeat
        acc = look.get("booth_accent", 0.0)
        if acc:
            downbeat = (0.5 + 0.5 * np.cos(6.283185 * beat4)) ** 3.0
            frame += (acc * downbeat * light)[..., None] * np.array([0.55, 0.85, 1.0], np.float32)

        # 5. bloom
        frame = self.bloom(frame, look["bloom"])
        return frame, light

    @staticmethod
    def bloom(frame, strength):
        small = cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        lum = small.max(axis=2)
        bright = np.clip((lum - 0.60) / 0.40, 0, 1) ** 1.15
        src = small * bright[..., None]
        b1 = cv2.GaussianBlur(src, (0, 0), 4.0)
        b2 = cv2.GaussianBlur(src, (0, 0), 13.0)
        b3 = cv2.GaussianBlur(src, (0, 0), 34.0)
        glow = 0.42 * b1 + 0.38 * b2 + 0.20 * b3
        glow = cv2.resize(glow, (W, H), interpolation=cv2.INTER_LINEAR)
        return frame + strength * glow


# ------------------------------------------------------------------ moves ----
# Both shots keep travelling through the wipe, so the cut never freezes the
# camera: shot 02 runs to the end of the transition, shot 03 starts before it.
S2_SPAN = (N2 + NT) / FPS
S3_SPAN = (N3 + NT) / FPS
S3_PREROLL = -NT / FPS


def move_shot02(t):
    u = float(np.clip(t / S2_SPAN, 0, 1))
    e = ease_steady(u)
    dx, dy = handheld(t, 1.3, seed=3)
    return Cam(s=1.0 + 0.175 * e, cx=0.500 + 0.055 * e, cy=0.470 - 0.038 * e, ox=dx, oy=dy)


def move_shot03(t):
    u = float(np.clip((t - S3_PREROLL) / S3_SPAN, 0, 1))
    e = ease_steady(u)
    dx, dy = handheld(t + 40.0, 1.1, seed=11)
    return Cam(s=1.015 + 0.150 * e, cx=0.500 + 0.010 * e, cy=0.430 - 0.058 * e, ox=dx, oy=dy)


# ------------------------------------------------------------------ grade ----
VIG = build_vignette()


def grade(frame, exposure=1.0):
    x = frame * exposure
    x = np.clip(x, 0, 1.8)
    # filmic S-curve
    k = 2.1
    x = x + 0.075 * (x - 0.42) * (1.4 - np.abs(k * x - 0.95))
    gray = x.mean(axis=2, keepdims=True)
    x = gray + (x - gray) * 1.06
    x = x + 0.006
    x[..., 0] += 0.003          # cool shadows / warm highs split
    x[..., 2] -= 0.002
    return x * VIG


def finish(frame, rng, grain=0.0055):
    x = np.clip(frame, 0, 1)
    if grain:
        x = x + rng.normal(0, grain, (H, W, 1)).astype(np.float32)
        x = x + rng.normal(0, grain * 0.5, (H, W, 3)).astype(np.float32)
    return (np.clip(x, 0, 1) * 255.0 + 0.5).astype(np.uint8)


# ------------------------------------------------------------- transition ----
def _mk_grid():
    xx, yy = np.meshgrid(
        np.arange(W, dtype=np.float32) / W, np.arange(H, dtype=np.float32) / H
    )
    return xx.astype(np.float32), yy.astype(np.float32)


GX, GY = _mk_grid()


def laser_transition(old, new, i, n=NT, new_soft=None, old_blur=None):
    """
    "Cyan laser strokes sweep the lens into a line of light -> next scene."

    n = 26 frames == 2 beats at 142 BPM. Phases:
      0 ..  6   the laser drops in from above frame, decelerating onto centre
      6 .. 12   it locks on the centre and collapses into a razor-thin blade
     12 .. 16   the blade blooms: additive cyan light, colour preserved
     16 .. 25   the blade tears open; the outgoing shot defocuses and sinks
                behind it while the club racks into focus
    Nothing is ever tinted flat to a colour card: the old shot keeps its
    chroma, it just loses focus and exposure as the light takes over.
    """
    if new_soft is None:
        new_soft = cv2.GaussianBlur(new, (0, 0), 4.5)
    if old_blur is None:
        old_blur = cv2.GaussianBlur(old, (0, 0), 9.0)

    # ---- 1. blade geometry ----------------------------------------------
    if i < 6:
        u = i / 6.0
        y_beam = -0.30 + 0.82 * ease_out(u) ** 1.25
        tilt = np.radians(13.0) * (1.0 - u) ** 1.4
    else:
        v = float(np.clip((i - 6) / 6.0, 0, 1))
        y_beam = 0.545 - 0.045 * ease_out(v)
        tilt = 0.0
    beam_in = float(smoothstep(i / 3.5))

    ct, st = float(np.cos(tilt)), float(np.sin(tilt))
    d = (((GX - 0.5) * st) + ((GY - y_beam) * ct)) * H
    ad = np.abs(d)

    # ---- 2. blade: collapse, intensity, dispersion ----------------------
    collapse = float(np.clip((i - 1) / 11.0, 0, 1))
    core_w = 5.6 - 4.0 * collapse ** 1.3
    core = np.exp(-(ad / core_w) ** 2) * (2.6 + 5.2 * collapse)
    halo = np.exp(-(ad / (38.0 - 20.0 * collapse)) ** 2) * (0.26 + 0.52 * collapse)
    spill = np.exp(-(ad / 170.0) ** 2) * (0.06 + 0.14 * collapse)
    gain = beam_in * (1.0 - 0.25 * (i / (n - 1.0)))

    # the leaving shot starts to soften + sink while the blade is still closed,
    # so nothing changes abruptly when the tear opens
    sink = float(smoothstep((i - 11.5) / 8.0) * 0.94)
    base = old * (1.0 - 0.75 * sink) + old_blur * (0.75 * sink)
    base = base * (1.0 - 0.22 * sink)

    out = base * (1.0 - 0.10 * collapse)
    out = out + (spill * gain)[..., None] * CYAN * 0.85
    out = out + (halo * gain)[..., None] * CYAN
    out = out + (core * gain)[..., None] * np.array([1.0, 1.0, 0.97], np.float32)
    out += (np.exp(-((d + 4.0) / 3.0) ** 2) * 0.12 * gain)[..., None] * np.array([0.40, 0.88, 1.0], np.float32)
    out += (np.exp(-((d - 5.0) / 4.5) ** 2) * 0.07 * gain)[..., None] * np.array([1.00, 0.70, 0.50], np.float32)

    # anamorphic streak + lens ghosts on the blade axis
    inside = float(np.clip((1.02 - abs(y_beam - 0.5)) / 0.30, 0, 1))
    if inside > 0:
        streak = np.exp(-((GY - y_beam) / (0.0056 - 0.0022 * collapse)) ** 2) \
                 * np.exp(-((GX - 0.5) / 0.58) ** 2)
        out += (streak * (0.20 + 0.70 * collapse) * inside * gain)[..., None] * CYAN
        for gxo, sz, amp in ((0.30, 0.0016, 0.13), (0.71, 0.0027, 0.08), (0.50, 0.0080, 0.05)):
            gy = 0.5 - (y_beam - 0.5) * 0.75
            g = np.exp(-(((GX - gxo) ** 2 + (GY - gy) ** 2) / sz)) * inside
            out += (g * amp * gain)[..., None] * np.array([0.55, 0.95, 1.0], np.float32)

    # ---- 3. bloom: additive light on the shot (chroma preserved) --------
    flare = float(smoothstep((i - 8) / 8.5) * (1.0 - smoothstep((i - 20) / 5.5)))
    if flare > 0.002:
        band = np.exp(-((GY - 0.5) / (0.018 + 0.075 * flare)) ** 2)
        rad = 1.0 - 0.42 * np.clip(((GX - 0.5) ** 2 + (GY - 0.5) ** 2) / 0.95, 0, 1)
        # screen-style light: keeps hue, lifts exposure, rolls off softly
        lift = flare * (0.10 + 0.85 * band) * rad
        out = 1.0 - (1.0 - np.clip(out, 0, 1.6)) * np.exp(-lift[..., None] * 1.7)
        out += (np.exp(-((GY - 0.5) / 0.0075) ** 2) * flare * 1.25)[..., None] * WHITE
        out += (np.exp(-((GY - 0.5) / 0.070) ** 2) * flare * 0.22)[..., None] * CYAN

    # ---- 4. tear open: defocus the outgoing shot behind the blade -------
    if i >= 15:
        r = float(np.clip((i - 15) / 9.0, 0, 1))
        h = smoothstep(r) ** 0.92 * (H * 1.06)
        dy = np.abs(GY - 0.5) * H
        open_mask = smoothstep((h - dy) / 110.0)

        # incoming frame lands soft, then racks into focus
        sharp = float(smoothstep((i - 17) / 6.0))
        new_mix = new * sharp + new_soft * (1.0 - sharp)

        out = out * (1.0 - open_mask)[..., None] + new_mix * open_mask[..., None]

        # edges of the tear + a bloom that dies away
        edge = np.exp(-((dy - h) / 8.0) ** 2) * (1.25 * (1.0 - r ** 2))
        glow_e = np.exp(-((dy - h) / 44.0) ** 2) * 0.45 * (1.0 - r)
        out += ((edge + glow_e) * (0.50 + 0.70 * flare))[..., None] * np.array([1.0, 1.0, 0.97], np.float32)
        out += (open_mask * 0.04 * (1.0 - r))[..., None] * CYAN
    return out


# ------------------------------------------------------------------- main ----
def build_scenes():
    s2 = Scene("entrance", IMG2, seed=21, move=move_shot02,
               look=dict(pulse=0.26, pulse_glow=0.09, haze=0.17, particles_a=0.9,
                         particles=22, sway=0.0, bloom=0.50, booth_accent=0.0))
    s3 = Scene("club", IMG1, seed=44, move=move_shot03,
               look=dict(pulse=0.34, pulse_glow=0.13, haze=0.30, particles_a=0.8,
                         particles=30, sway=2.4, bloom=0.56, booth_accent=0.10),
               depth_parallax=0.055)
    return s2, s3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/master.mp4")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=N_TOTAL)
    ap.add_argument("--preview", type=int, nargs="*")
    ap.add_argument("--outdir", default="/tmp/preview")
    ap.add_argument("--audio", default=None)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    s2, s3 = build_scenes()

    def frame_at(idx):
        if idx < N2 + NT:
            # shot 02, still travelling while the laser takes over
            f, _ = s2.render(idx / FPS)
            return grade(f, exposure=1.0)
        t3 = (idx - N2 - NT) / FPS
        f, _ = s3.render(t3)
        return grade(f)

    def wipe_at(idx):
        i = idx - N2
        p = i / (NT - 1.0)
        old, _ = s2.render(idx / FPS)
        old = grade(old, exposure=1.0 + 0.30 * p)
        # the incoming shot starts a touch before the cut and keeps moving
        new, _ = s3.render(S3_PREROLL + p * (NT / FPS))
        new = grade(new)
        soft = cv2.GaussianBlur(new, (0, 0), 4.5)
        ob = cv2.GaussianBlur(old, (0, 0), 9.0)
        return laser_transition(old, new, i, new_soft=soft, old_blur=ob)

    if args.preview:
        os.makedirs(args.outdir, exist_ok=True)
        for idx in args.preview:
            fr = wipe_at(idx) if N2 <= idx < N2 + NT else frame_at(idx)
            rgb = finish(fr, np.random.default_rng(idx))
            if args.scale != 1.0:
                rgb = cv2.resize(rgb, (int(W * args.scale), int(H * args.scale)),
                                 interpolation=cv2.INTER_AREA)
            p = os.path.join(args.outdir, f"f{idx:04d}.png")
            cv2.imwrite(p, rgb)
            print("wrote", p)
        return

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0"]
    if args.audio:
        cmd += ["-i", args.audio, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-movflags", "+faststart", "-g", "60", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = args.end - args.start
    for k, idx in enumerate(range(args.start, args.end)):
        fr = wipe_at(idx) if N2 <= idx < N2 + NT else frame_at(idx)
        proc.stdin.write(finish(fr, np.random.default_rng(idx * 7919 + 13)).tobytes())
        if k % 15 == 0 or k == n - 1:
            print(f"\rframe {idx + 1}/{args.end}", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"\nencoded {args.out}  ({n} frames, {n / FPS:.2f}s)")
    if proc.returncode != 0:
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
