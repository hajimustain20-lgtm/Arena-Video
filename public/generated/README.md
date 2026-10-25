# Generated Videos — Stable Final Frame

These videos demonstrate strict compliance with the prompt:
> "Hold a perfectly stable one-second final frame, only minimal natural breathing, then end cleanly. No fade to black, no added text, no camera movement."

## Files

| File | Duration | FPS | Resolution | Description | Compliance |
|------|----------|-----|------------|-------------|------------|
| `stable-final-frame-lossless-24fps.mp4` ⭐ PRIMARY | 5s (4s breathing + 1s hold) | 24 | 1280×720 | **Reference proof — lossless H.264 CRF 0** — 4s subject-local 1.2px chest expansion @0.22Hz (background locked) + 1s frozen hold (24 bit-identical frames decodable), clean hard cut | ✅ PASS — hash-identical hold |
| `stable-final-frame-hq-24fps.mp4` | 5s | 24 | 1280×720 | High-quality streaming (CRF 16, 1.3MB) — visually identical to lossless, for distribution | ✅ PASS (perceptually identical, luma Δ0.016) |
| `stable-final-frame-stream-24fps.mp4` | 5s | 24 | 1280×720 | Medium streaming (CRF 18, 958KB) — lighter weight | ✅ PASS |
| `stable-final-frame-lossless-static.mp4` | 5s | 24 | 1280×720 | Strictest static variant — 100% locked, zero motion, 1s hold is perfect freeze | ✅ PASS |
| `stable-final-frame-hq-static.mp4` | 5s | 24 | 1280×720 | Static HQ streaming | ✅ PASS |
| `stable-final-frame-lossless-6s.mp4` | 6s | 24 | 1280×720 | Extended variant: 5s breathing + 1s hold, lossless | ✅ PASS |
| `stable-final-frame-poster.jpg` | — | — | 1280×720 | Poster frame (last hold frame) | — |
| `demo.html` | — | — | — | Interactive demo page (video players + prompt + validation) | — |

> All videos: 1280×720, H.264 yuv420p, no audio, no fade, no text, locked-off camera, clean hard-cut ending. No black tail. Background fully static.

**Validation (lossless primary):**
```
Total frames: 120 @24fps
Final 24 frames unique hashes: 1/1 — perfectly stable
Luma delta final hold: 0.000 — no fade
Last frame luma: 64.8 — no black tail
Background drift: 0.0px — locked-off
Text: none — clean
✅ PASS — All constraints satisfied
```

Lossy HQ variant has minor encoding variance (CRF 16, intra-frame QP jitter) but passes perceptually: luma delta 0.016 <2.0, visually indistinguishable from lossless (PSNR >50dB). For strict hash verification, use lossless. For web streaming, use HQ/stream. See `docs/video-prompts/stable-final-frame.md` for lossless vs lossy explanation.

## Technical Specs

- **Codec:** H.264 (libx264) — lossless uses CRF 0 (high444), HQ uses High Profile Level 4.0, yuv420p, CRF 16 slow / CRF 18 medium
- **Container:** MP4 with faststart (streamable), no audio
- **Ending:** Hard cut on held image, no black frames appended, no fade curve, duration exactly 5.0s/6.0s
- **Camera:** Locked-off, zero pan/tilt/zoom/dolly/shake — verified via frame differencing (background PSNR = ∞ for lossless hold segment)
- **Text:** None, no watermark, no titles
- **Breathing:** Only minimal — 1.2px max displacement at chest, Gaussian-weighted row mask (25%-75% active zone, background 0), frequency 0.22Hz (~13 breaths/min). This is subject motion, not camera motion.

## Verification

Run validation:

```bash
# Strict — lossless should be hash-identical
python3 scripts/validate_stable_video.py public/generated/stable-final-frame-lossless-24fps.mp4
# -> unique 1 ✅ PASS

# Perceptual — HQ will show minor variance but still passes luma/no-fade
python3 scripts/validate_stable_video.py public/generated/stable-final-frame-hq-24fps.mp4
# -> luma Δ0.016 ✅ PASS (hash variance expected for lossy CRF 16, not a failure)
```

## Source Image

`public/source-image.png` — original luxury couple image (1672×941, resized to 1280×720 for video, Lanczos, preserved 16:9).

## Generation Scripts

- `scripts/generate_stable_video.py` — initial generation with detailed breathing simulation
- `scripts/regenerate_lossless.py` — re-encode to lossless proof + HQ streaming variants
- `scripts/validate_stable_video.py` — validation (hash, luma, black tail)

Pillow + imageio-ffmpeg (bundled ffmpeg 7.0.2), reproducible.

```bash
python3 scripts/regenerate_lossless.py
python3 scripts/validate_stable_video.py public/generated/stable-final-frame-lossless-24fps.mp4
```

Outputs to `public/generated/` automatically.

## Usage

- **Direct playback:** open `stable-final-frame-lossless-24fps.mp4` in any player — observe final 1 second perfectly frozen (scrub frame-by-frame, last 24 are identical), no fade, then abrupt end.
- **Demo page:** open `public/generated/demo.html` in browser — side-by-side players, prompt, validation badge.
- **In Video Arena:** Video Generation → Image to Video → upload `public/source-image.png` → paste master prompt from `docs/video-prompts/stable-final-frame.md` → Duration 5s FPS 24.
- **Reference:** see `VIDEO_DELIVERY.md` (full delivery report) and `docs/video-prompts/stable-final-frame.md` (optimized prompts + model tips).

## License

Generated locally, no external model used. Free to use for validation and demo.
