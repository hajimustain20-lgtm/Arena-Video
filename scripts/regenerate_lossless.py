#!/usr/bin/env python3
import os, numpy as np
from PIL import Image
import imageio.v2 as imageio
import hashlib

INPUT_PATH = "/tmp/arena-coding-uploads/image-1.png"
OUTPUT_DIR = "public/generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
FPS = 24
DURATION_TOTAL = 5.0
FINAL_HOLD = 1.0

img = Image.open(INPUT_PATH).convert("RGB").resize((WIDTH,HEIGHT), Image.LANCZOS)
base_frame = np.array(img)
HEIGHT, WIDTH, _ = base_frame.shape

# Breathing params as before
BREATH_HZ = 0.22
BREATH_AMP_PX = 1.2
chest_y_frac = 0.48
chest_y = int(HEIGHT * chest_y_frac)
y_coords = np.arange(HEIGHT)
sigma = HEIGHT * 0.18
weights = np.exp(-0.5 * ((y_coords - chest_y) / sigma) ** 2)
weights = weights / weights.max()
# row mask
row_mask = np.zeros(HEIGHT)
for y in range(HEIGHT):
    y_frac = y / HEIGHT
    if y_frac < 0.20: w=0
    elif y_frac < 0.25: w=(y_frac-0.20)/0.05
    elif y_frac < 0.75: w=1.0
    elif y_frac < 0.85: w=1 - (y_frac-0.75)/0.10
    else: w=0
    row_mask[y]=w
final_weights = weights * row_mask

num_frames = int(DURATION_TOTAL * FPS)
num_hold = int(FINAL_HOLD * FPS)
num_breath = num_frames - num_hold

def apply_breathing(frame, t):
    phase = 2*np.pi*BREATH_HZ*t
    breath = np.sin(phase)
    displacements = breath * BREATH_AMP_PX * final_weights
    sign = np.sign(y_coords - chest_y)
    disp_signed = displacements * sign
    new_frame = np.zeros_like(frame)
    for y in range(HEIGHT):
        disp = disp_signed[y]
        src_y = y - disp
        src_y_floor = int(np.floor(src_y))
        src_y_ceil = src_y_floor+1
        frac = src_y - src_y_floor
        if src_y_floor <0:
            new_frame[y]=frame[0]
        elif src_y_ceil >=HEIGHT:
            new_frame[y]=frame[HEIGHT-1]
        else:
            if abs(frac)<0.001:
                new_frame[y]=frame[src_y_floor]
            else:
                upper=frame[src_y_floor].astype(np.float32)
                lower=frame[src_y_ceil].astype(np.float32)
                new_frame[y]=(upper*(1-frac)+lower*frac).astype(np.uint8)
    return new_frame

frames=[]
for i in range(num_breath):
    t=i/FPS
    frames.append(apply_breathing(base_frame, t))
hold_frame = frames[-1].copy() if frames else base_frame.copy()
for i in range(num_hold):
    frames.append(hold_frame.copy())

print(f"Generated {len(frames)} frames, hold unique {len(set(hashlib.md5(f.tobytes()).hexdigest() for f in frames[-num_hold:]))}")

# Encode lossless (CRF 0) for perfect decoded stability
for crf, preset, suffix in [
    ("0","ultrafast","lossless"),
    ("16","slow","hq"),
    ("18","medium","stream"),
]:
    out = f"{OUTPUT_DIR}/stable-final-frame-{suffix}-24fps.mp4"
    # CRF0 uses high444, not high
    if crf=="0":
        ffmpeg_params = ["-pix_fmt","yuv420p","-movflags","+faststart","-crf","0","-preset","ultrafast"]
    else:
        ffmpeg_params = ["-pix_fmt","yuv420p","-movflags","+faststart","-profile:v","high","-crf",crf,"-preset",preset]
    writer=imageio.get_writer(out, fps=FPS, codec="libx264", ffmpeg_params=ffmpeg_params, macro_block_size=1)
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f"✓ {out} size {os.path.getsize(out)/1024:.1f}KB crf{crf}")

# Also static lossless
for crf, preset, suffix in [("0","ultrafast","lossless-static"),("16","slow","hq-static")]:
    out = f"{OUTPUT_DIR}/stable-final-frame-{suffix}.mp4"
    if crf=="0":
        ffmpeg_params = ["-pix_fmt","yuv420p","-movflags","+faststart","-crf","0","-preset","ultrafast"]
    else:
        ffmpeg_params = ["-pix_fmt","yuv420p","-movflags","+faststart","-profile:v","high","-crf",crf,"-preset",preset]
    writer=imageio.get_writer(out, fps=FPS, codec="libx264", ffmpeg_params=ffmpeg_params, macro_block_size=1)
    for _ in range(num_frames):
        writer.append_data(base_frame)
    writer.close()
    print(f"✓ {out}")

# Also make 6s lossless
DURATION6=6.0
num_frames6=int(DURATION6*FPS)
num_hold6=int(FINAL_HOLD*FPS)
num_breath6=num_frames6-num_hold6
frames6=[]
for i in range(num_breath6):
    frames6.append(apply_breathing(base_frame, i/FPS))
hold6=frames6[-1].copy()
for i in range(num_hold6):
    frames6.append(hold6.copy())
out6=f"{OUTPUT_DIR}/stable-final-frame-lossless-6s.mp4"
writer=imageio.get_writer(out6, fps=FPS, codec="libx264", ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-crf","0","-preset","ultrafast"], macro_block_size=1)
for f in frames6:
    writer.append_data(f)
writer.close()
print(f"✓ {out6}")

# Poster
Image.fromarray(hold_frame).save(f"{OUTPUT_DIR}/stable-final-frame-poster.jpg", quality=95)
print("✓ poster")
