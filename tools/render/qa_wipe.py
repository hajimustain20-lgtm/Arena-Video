#!/usr/bin/env python3
"""Numeric QA for the wipe: renders only the cut and reports frame deltas."""
import importlib.util
import sys

import cv2
import numpy as np

spec = importlib.util.spec_from_file_location("rt", "/home/user/Arena-Video/tools/render/render_timeline.py")
rt = importlib.util.module_from_spec(spec)
sys.argv = ["qa"]
spec.loader.exec_module(rt)

s2, s3 = rt.build_scenes()
N2, NT = rt.N2, rt.NT

frames = []
for i in range(NT):
    p = i / (NT - 1.0)
    old, _ = s2.render((N2 + i) / rt.FPS)
    old = rt.grade(old, exposure=1.0 + 0.30 * p)
    new, _ = s3.render(rt.S3_PREROLL + (i / (NT - 1.0)) * (NT / rt.FPS))
    new = rt.grade(new)
    soft = cv2.GaussianBlur(new, (0, 0), 4.2)
    frames.append(rt.laser_transition(old, new, i, new_soft=soft, old_blur=cv2.GaussianBlur(old, (0, 0), 9.0)))

prev = None
print(" i   mean |d|   max |d|   jitter(luma)")
for i, f in enumerate(frames):
    g = cv2.cvtColor((np.clip(f, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    luma = float(g.mean())
    if prev is not None:
        d = float(np.abs(g - prev[0]).mean())
        print(f"{i:3d}  {d:7.2f}  {float(np.abs(g-prev[0]).max()):7.1f}   luma {luma:6.1f} (d {luma-prev[1]:+5.1f})")
    else:
        print(f"{i:3d}        -        -   luma {luma:6.1f}")
    prev = (g, luma)

# also check the cut boundary from the last shot-02 frame and into shot 03
last2, _ = s2.render((N2 + NT - 1) / rt.FPS)
last2 = rt.grade(last2, 1.30)
glast = cv2.cvtColor((np.clip(last2, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
first3, _ = s3.render(0.0)
first3 = rt.grade(first3)
gf = cv2.cvtColor((np.clip(first3, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
g_prev_end = cv2.cvtColor((np.clip(frames[-1], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
print("last wipe frame -> first shot03 frame diff:", round(float(np.abs(g_prev_end - gf).mean()), 2))
