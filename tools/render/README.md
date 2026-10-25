# Neon Club — shot render

Turns the two keyframes into an 11 s, 1080p30, beat-locked sequence:

| frames | time | shot | source |
| --- | --- | --- | --- |
| 0–151 | 0.00–5.07 s | 02 · entrance push-in | `image-2.png` |
| 152–177 | 5.07–5.93 s | cyan laser wipe | 02 → 03 |
| 178–329 | 5.93–11.00 s | 03 · club wide push | `image-1.png` |

Timing is derived from the 142 BPM brief: one beat = 0.422 535 s, so each shot is
exactly 12 beats and the laser cut lands on beat 12. The clip is 26 beats long.

## What the renderer actually does

Everything is procedural and deterministic — frame _N_ always renders identically,
so the cut can be re-rendered or re-timed without drift.

```
render_timeline.py
├─ Cam / Scene          physical dolly: inverse-mapped warp of the 2560×1440 plate
│  ├─ depth_parallax    per-row zoom term (shot 03): the near floor expands faster
│  │                    than the far ceiling → real travel parallax, no 2D slide
│  ├─ crowd sway        band-masked, spatially decorrelated twice-per-bar warp
│  │                    confined to the dance floor; the ceiling stays rigid
│  ├─ neon pulse        raised-cosine beat envelope driving an emitter mask
│  │                    (bright + saturated pixels) — light breathes, never strobes
│  ├─ haze              fBm field advected sideways, modulated by scene luma
│  ├─ bokeh             floating dust particles, beat-independent drift
│  └─ bloom             3-scale bright-pass
├─ grade                filmic S-curve, slight saturation lift, cool-shadow split,
│                       vignette
└─ laser_transition     26 frames, see below
```

Shot 02 deliberately gets **no local warps at all** — the subject is only touched by
global camera and light passes, so identity and wardrobe stay rigid (no morphing).

### The wipe (26 frames)

1. **0–6** laser drops in from above frame, decelerating onto centre (eased, no pop-in —
   intensity also fades up over the first 3 frames).
2. **6–12** it locks on the centre line and collapses into a razor blade, with a cyan /
   warm chromatic fringe and an anamorphic streak plus mirrored lens ghosts.
3. **12–16** the blade blooms: *additive* light, so the outgoing shot keeps its chroma
   while exposure lifts and it starts to defocus — it sinks rather than tinting flat
   to a cyan card.
4. **16–25** the blade tears open vertically. The new frame lands slightly soft and
   racks into focus; the tear edge carries a bloom that dies before the cut.

## Audio

`make_audio.py` synthesises the bed from scratch (no samples): 4-on-the-floor kick,
claps on 2 and 4, swung hats, offbeat bass in A minor, Am9 pad, a 4-beat noise riser
into the **cut on beat 12**, sub-boom + crash on the cut, laser-gated whoosh that rides
the wipe, and a bell arpeggio in the club section.

## Usage

```bash
python3 -m venv .venv && .venv/bin/pip install pillow numpy opencv-python-headless imageio-ffmpeg

# 142 BPM bed
.venv/bin/python tools/render/make_audio.py --out bed.wav

# full 11 s master (1080p30 + audio)
.venv/bin/python tools/render/render_timeline.py \
    --out output/neon-club/neon-club-loop.mp4 --audio bed.wav --crf 17 --preset slow

# inspect stills without encoding
.venv/bin/python tools/render/render_timeline.py --preview 0 80 151 170 200 --outdir /tmp/prev

# numbers instead of eyes: per-frame delta / luma trace of the wipe
.venv/bin/python tools/render/qa_wipe.py
```

`ffmpeg` must be on `PATH` (or point `imageio_ffmpeg` at it). The source stills are read
from `/tmp/arena-coding-uploads/`; edit `IMG1` / `IMG2` at the top of
`render_timeline.py` to point elsewhere.

## QA numbers for the delivered master

Measured on the encoded file (320×180 luma, mean absolute frame delta):

| segment | mean delta | max |
| --- | --- | --- |
| shot 02 | 3.48 | 4.72 |
| wipe | 3 → 13.7 → 38 (on the tear) → 3 | 41 |
| shot 03 | 3.33 | 5.02 |

- Odd/even motion ratio **0.980** → no frame-alternating flicker.
- Luma standard deviation 3.9 inside each shot → no exposure pumping.
- Cut boundary between wipe and shot 03: **0.00** delta (identity hand-off).

## Deliverables

- `neon-club-loop.mp4` — 1920×1080, 30 fps, 11.00 s, H.264 High + AAC 48 kHz stereo
- `neon-club-poster.jpg` — the moment the club is revealed
- `neon-club-entrance.jpg`, `neon-club-club.jpg` — full-res stills of each shot
