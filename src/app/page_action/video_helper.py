import imageio.v3 as iio
import numpy as np
from PIL import Image


def resize_to_480p(img: Image.Image, align_16: bool = False) -> Image.Image:
    w, h = img.size
    target_h = 480
    target_w = int(w * (target_h / h))
    if align_16:
        target_w = max(16, round(target_w / 16) * 16)
    return img.resize((target_w, target_h), Image.Resampling.BILINEAR)

def save_recording(frames: list[Image.Image], gif_path: str, video_path: str | None = None, fps: int = 8):
    if not frames:
        return

    gif_frames = [resize_to_480p(f) for f in frames]
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=int(1000 / fps),
        loop=0,
    )

    if video_path:
        mp4_frames = [np.array(resize_to_480p(f, align_16=True)) for f in frames]
        iio.imwrite(video_path, mp4_frames, fps=fps)
        