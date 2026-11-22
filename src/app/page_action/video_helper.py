import base64
import io
import json
import os
import tempfile
import threading
import time
import urllib.request

import imageio.v3 as iio
import numpy as np
import websocket
from PIL import Image


def resize_to_720p(img: Image.Image, align_16: bool = False) -> Image.Image:
    w, h = img.size
    scale = 720 / min(w, h)
    
    # Avoid upscaling if viewport is already smaller than 720p
    scale = min(scale, 1.0)

    target_w = int(w * scale)
    target_h = int(h * scale)

    if align_16:
        target_w = max(16, round(target_w / 16) * 16)
        target_h = max(16, round(target_h / 16) * 16)

    return img.resize((target_w, target_h), Image.Resampling.BILINEAR)

def _get_cdp_ws_url(driver) -> str:
    addr = driver.capabilities["goog:chromeOptions"]["debuggerAddress"]
    with urllib.request.urlopen(f"http://{addr}/json", timeout=3) as resp:
        targets = json.loads(resp.read().decode())
    for t in targets:
        if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("Could not find Chrome CDP WebSocket URL")


def _screencast_loop(
    ws_url: str,
    frames: list[tuple[float, bytes]],
    capture_stop: threading.Event,
    start_t: float,
):
    ws = websocket.create_connection(ws_url, timeout=0.2)
    ws.send(json.dumps({
        "id": 1,
        "method": "Page.startScreencast",
        "params": {"format": "jpeg", "quality": 85, "everyNthFrame": 1},
    }))

    try:
        while not capture_stop.is_set():
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break

            msg = json.loads(raw)
            if msg.get("method") == "Page.screencastFrame":
                params = msg["params"]
                frames.append((time.perf_counter() - start_t, base64.b64decode(params["data"])))
                ws.send(json.dumps({
                    "id": 2,
                    "method": "Page.screencastFrameAck",
                    "params": {"sessionId": params["sessionId"]},
                }))
    finally:
        try:
            ws.send(json.dumps({"id": 3, "method": "Page.stopScreencast"}))
            ws.close()
        except Exception:
            pass


def _resample_frames(
    frames: list[tuple[float, object]],
    target_fps: int,
    total_duration: float,
) -> list:
    if not frames:
        return []
    duration = max(total_duration, frames[-1][0])
    num_out = max(1, int(duration * target_fps))
    out = []
    src_idx = 0
    for i in range(num_out):
        t = i / target_fps
        while src_idx + 1 < len(frames) and frames[src_idx + 1][0] <= t:
            src_idx += 1
        out.append(frames[src_idx][1])
    return out


def save_recording(
    raw_frames: list[tuple[float, bytes]],
    total_duration: float,
    preview_gif_path: str,
    gif_path: str,
    video_path: str,
    video_fps: int = 30,
    gif_fps: int = 15,
):
    if not raw_frames:
        return

    decoded = [
        (t, Image.open(io.BytesIO(data)).convert("RGB"))
        for t, data in raw_frames
    ]

    # 1. Compressed 720p GIF for UI preview only
    preview_resized = [
        (t, resize_to_720p(img).quantize(colors=128, method=Image.Quantize.FASTOCTREE))
        for t, img in decoded
    ]
    preview_out = _resample_frames(preview_resized, gif_fps, total_duration)
    preview_out[0].save(
        preview_gif_path,
        save_all=True,
        append_images=preview_out[1:],
        duration=int(1000 / gif_fps),
        loop=0,
    )

    # 2. Full-resolution GIF for saving
    full_gif_frames = [
        (t, img.quantize(colors=256, method=Image.Quantize.FASTOCTREE))
        for t, img in decoded
    ]
    full_gif_out = _resample_frames(full_gif_frames, gif_fps, total_duration)
    full_gif_out[0].save(
        gif_path,
        save_all=True,
        append_images=full_gif_out[1:],
        duration=int(1000 / gif_fps),
        loop=0,
    )

    # 3. Full-resolution 30 FPS MP4 (ensure even width/height for H.264)
    mp4_frames = []
    for t, img in decoded:
        w, h = img.size
        even_img = img.crop((0, 0, w - (w % 2), h - (h % 2)))
        mp4_frames.append((t, np.array(even_img)))

    mp4_out = _resample_frames(mp4_frames, video_fps, total_duration)
    iio.imwrite(video_path, mp4_out, fps=video_fps, macro_block_size=2)
    
def save_preview_gif(
    raw_frames: list[tuple[float, bytes]],
    total_duration: float,
    preview_gif_path: str,
    gif_fps: int = 15,
):
    if not raw_frames:
        return

    preview_resized = [
        (
            t,
            resize_to_720p(Image.open(io.BytesIO(data)).convert("RGB")).quantize(
                colors=128, method=Image.Quantize.FASTOCTREE
            ),
        )
        for t, data in raw_frames
    ]
    out = _resample_frames(preview_resized, gif_fps, total_duration)
    out[0].save(
        preview_gif_path,
        save_all=True,
        append_images=out[1:],
        duration=int(1000 / gif_fps),
        loop=0,
    )


def export_recording(
    raw_frames: list[tuple[float, bytes]],
    total_duration: float,
    gif_path: str,
    video_path: str,
    video_fps: int = 90,
    gif_fps: int = 30,
):
    if not raw_frames:
        return

    decoded = [
        (t, Image.open(io.BytesIO(data)).convert("RGB"))
        for t, data in raw_frames
    ]

    # Full-resolution GIF
    gif_frames = [
        (t, img.quantize(colors=256, method=Image.Quantize.FASTOCTREE))
        for t, img in decoded
    ]
    gif_out = _resample_frames(gif_frames, gif_fps, total_duration)
    gif_out[0].save(
        gif_path,
        save_all=True,
        append_images=gif_out[1:],
        duration=int(1000 / gif_fps),
        loop=0,
    )

    # Full-resolution 90 FPS MP4
    mp4_frames = []
    for t, img in decoded:
        w, h = img.size
        even_img = img.crop((0, 0, w - (w % 2), h - (h % 2)))
        mp4_frames.append((t, np.array(even_img)))

    mp4_out = _resample_frames(mp4_frames, video_fps, total_duration)
    iio.imwrite(video_path, mp4_out, fps=video_fps, macro_block_size=2)