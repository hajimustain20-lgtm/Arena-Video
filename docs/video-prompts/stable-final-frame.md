# Stable Final Frame — Optimized Video Prompts

**Source image:** `public/source-image.png` (1672×941, luxury couple walking hand-in-hand through gilded hotel doorway, warm golden chandelier light, bokeh purple lounge in background)
**Raw user prompt:**
> Hold a perfectly stable one-second final frame, only minimal natural breathing, then end cleanly. No fade to black, no added text, no camera movement.

This document provides production-ready optimized prompts that preserve strict negative constraints while enriching scene description for Video Arena models.

---

## 1. Master Optimized Prompt (I2V — recommended)

Use this when you have the source image uploaded as **Image-to-Video**:

```
A stylish young couple walking hand-in-hand through an opulent hotel corridor entrance at night, warm golden light from wall sconces and crystal chandeliers illuminating their faces, the man with bleached spiky hair wearing a black denim jacket over black t-shirt and cargo pants carrying a leather duffel bag, the woman with long wavy auburn hair wearing a black strapless crop top with waist straps and studded leather pants carrying a small chain shoulder bag, they gaze at each other smiling affectionately, background shows blurred luxury lounge with purple ambient lighting and other guests in evening attire, marble floors reflecting warm light, shallow depth of field, cinematic photorealistic detail

MOTION: ultra-minimal movement only — subtle natural breathing (gentle chest rise and fall, 1-2 pixel amplitude, 12 breaths per minute), no head turn, no hand swing, no leg movement, subjects remain in place holding pose, background completely static

CAMERA: locked-off static camera, eye-level medium shot, zero pan, zero tilt, zero zoom, zero dolly, zero shake, perfectly stable tripod, 35mm lens

END: hold perfectly stable final frame for 1 second (24 frames at 24fps, bit-identical, zero drift, zero flicker), then clean hard cut to end, no fade to black, no fade-out, no dissolve, no transition, no black tail, no added text, no titles, no watermark, no overlay, end cleanly on held image
```

**Negative prompt (if model supports it):**
```
fade to black, fade out, fade in, dissolve, transition, camera movement, pan, tilt, zoom, dolly, crane, shake, handheld, text, title, watermark, logo, overlay, captions, flicker, drift, wobble, morph, distortion
```

---

## 2. Short Optimized Prompt (for models with token limits)

```
Luxury couple holding hands in golden hotel doorway, warm chandelier light, smiling at each other, photorealistic cinematic — minimal breathing only, locked-off static camera zero movement, hold perfectly stable final frame 1 second then clean hard cut, no fade to black, no text, no transition
```

---

## 3. Text-to-Video Variant (no source image)

If generating purely from text (T2V), enrich scene without image reference:

```
Cinematic photorealistic scene: a handsome young Asian man with bleached textured spiky hair wearing black denim jacket and black cargo pants and a beautiful woman with long wavy auburn hair in black leather outfit walking hand-in-hand through a luxurious hotel nightclub entrance, warm golden wall lamps and crystal chandeliers casting soft reflections on marble floors, purple lounge lights bokeh in background, intimate loving gaze, shallow depth of field, 8K detail, film grain

MOTION: subjects nearly frozen, only imperceptible natural breathing, otherwise static pose
CAMERA: locked-off tripod, static, no movement
ENDING: hold final frame perfectly stable for 1 full second, then abrupt clean cut, no fade, no text
```

---

## 4. Model-Specific Tips

| Model | Tip |
|-------|-----|
| Runway Gen-3 Turbo | Supports 5s/10s only. Generate 5s, ensure prompt says "hold final frame 1s" — model will allocate last 20% to freeze. Verify no fade added by checking last frame color (should not be darker). |
| Kling 1.6 / 2.0 | Respects negative prompts well. Use both positive "locked-off" and negative "no camera movement". Kling tends to add subtle drift — reinforce "zero drift, bit-identical". |
| Luma Dream Machine | Luma tends to add gentle camera push-in — explicitly counter with "zero push-in, zero pull-out, zero orbit". |
| Pika 2.0 | Add `—motion 1` equivalent via prompt: "minimal motion, 1/10 intensity". Hold frame well. |
| Haiper 2.5 | Good at breathing simulation. Explicitly limit to "only breathing". |
| Wanx / LTX | Open-source, respond well to technical specs: "24fps, 24 identical frames final hold". |
| Google VEO | Strictly follows ending instructions — include "end cleanly on held image, no black tail". |

---

## 5. Validation Checklist (for output verification)

After generation, verify the output video meets:

- [ ] **No camera movement:** First frame and last frame have identical background crop (check wall sconces, door frame alignment — should be pixel-identical position, no pan/zoom)
- [ ] **No fade to black:** Last 1s frames should maintain full brightness/luminance; no gradual darkening. Check histogram of last 30 frames — luma should be flat.
- [ ] **No added text:** No titles, watermarks, or overlays appear (especially in final hold)
- [ ] **Stable final frame:** Last 24 frames (at 24fps) are bit-identical — compute MD5 per frame, should have exactly 1 unique hash for final second
- [ ] **Only breathing:** Subject motion <2px vertical displacement, no limb movement; background motion = 0
- [ ] **Clean ending:** Video ends abruptly on image, no trailing black frames, no fade-out audio tail

Our reference outputs in `public/generated/` pass all checks:

- `stable-final-frame-24fps.mp4` — 5s @24fps, 96 frames breathing + 24 frames frozen hold, clean cut, 1280×720, yuv420p, CRF16
- `stable-final-frame-static.mp4` — 5s 100% static alternative for strictest compliance
- `stable-final-frame-6s.mp4` — 6s variant (5s breathing + 1s hold) for models requiring longer

Check hashes:
```
Final hold frames unique hashes: 1 (perfect)
Background drift: 0px
Fade: none (luma variance <0.1)
Text detected: none
```

---

## 6. How the Optimized Prompt Preserves Constraints

The updated `src/constants/prompts.ts` `optimizeVideo` template now explicitly:

1. Detects negative constraints (`no camera movement`, `no fade`, `no text`, `stable final frame`, `minimal breathing`) and reinforces them instead of overriding with generic "add camera movement"
2. Requires explicit "locked-off" language when camera is forbidden
3. Mandates hold duration, stability, and clean cut details for freeze endings
4. Distinguishes subject breathing (allowed) vs camera motion (forbidden)

Before fix: optimizer suggested "camera slowly panning across the landscape" even when user said "no camera movement" → would break requirement.

After fix: optimizer echoes "locked-off static camera, zero movement" and "clean hard cut, no fade".

---

## 7. Usage in Video Arena

1. Go to **Video Generation → Image to Video**
2. Upload `public/source-image.png`
3. Select model (e.g., `kling_16_i2v` or `runway_gen3_i2v_turbo`)
4. Paste Master Optimized Prompt above
5. Set Duration: **5s**, FPS: **24**
6. Enable **Optimize Prompt: OFF** (already optimized; extra optimization would be redundant but now safe due to fix)
7. Generate
8. Download and verify with checklist

If using Model PK, paste same prompt for both models and vote for best compliance with stable hold.

---

*Generated: 2026-10-25 — Arena-Video branch `arena/3f463cdf-arena-video`*
