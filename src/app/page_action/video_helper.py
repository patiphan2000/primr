import base64
import io
import json
import threading
import time
import urllib.request

import imageio.v2 as iio_v2
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
            except Exception as e:
                print("Screencast stopped early:", repr(e))
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

def _decode_frames(raw_frames: list[tuple[float, bytes]]) -> list[tuple[float, Image.Image]]:
    return [
        (t, Image.open(io.BytesIO(data)).convert("RGB"))
        for t, data in raw_frames
    ]


def export_gif(
    raw_frames: list[tuple[float, bytes]],
    total_duration: float,
    gif_path: str,
    gif_fps: int = 15,
):
    if not raw_frames:
        return

    print(
        f"[Export GIF] frames={len(raw_frames)}, "
        f"last_frame_t={raw_frames[-1][0]:.2f}s, "
        f"total_duration={total_duration:.2f}s"
    )

    decoded = _decode_frames(raw_frames)
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


def export_video(
    raw_frames: list[tuple[float, bytes]],
    total_duration: float,
    video_path: str,
    video_fps: int = 30,
):
    if not raw_frames:
        return

    print(
        f"[Export MP4] frames={len(raw_frames)}, "
        f"last_frame_t={raw_frames[-1][0]:.2f}s, "
        f"total_duration={total_duration:.2f}s"
    )

    decoded = _decode_frames(raw_frames)
    duration = max(total_duration, decoded[-1][0])
    num_out = max(1, int(duration * video_fps))
    src_idx = 0

    with iio_v2.get_writer(
        video_path, fps=video_fps, codec="libx264", macro_block_size=2
    ) as writer:
        cached_idx = -1
        cached_arr = None
        for i in range(num_out):
            t = i / video_fps
            while src_idx + 1 < len(decoded) and decoded[src_idx + 1][0] <= t:
                src_idx += 1
            if src_idx != cached_idx:
                img = decoded[src_idx][1]
                w, h = img.size
                even_img = img.crop((0, 0, w - (w % 2), h - (h % 2)))
                cached_arr = np.array(even_img)
                cached_idx = src_idx
            writer.append_data(cached_arr)