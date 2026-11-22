import os
import tempfile
import threading
import time

import mss
from PIL import Image

from .driver_helper import get_driver
from .video_helper import save_recording


def smooth_scroll(driver, target_y, max_speed=400, ease_distance=300, min_speed_ratio=0.0):
    """
    Smoothly scrolls to target_y with a true ease-in / cruise / ease-out S-curve:
    - Smoothly accelerates from `max_speed * min_speed_ratio` (default 0 px/s)
      up to `max_speed` over the first `ease_distance` pixels.
    - Cruises at `max_speed` in the middle.
    - Smoothly decelerates over the final `ease_distance` pixels back to stop.
    - Uses execute_async_script so Python waits automatically without time.sleep().
    """
    if max_speed <= 0:
        raise ValueError("max_speed must be greater than 0")

    script = """
    const rawTargetY = arguments[0];
    const maxSpeed = arguments[1];
    const easeDist = Math.max(0, arguments[2]);
    const minRatio = Math.max(0, Math.min(1, arguments[3]));
    const done = arguments[4];

    const startY = window.scrollY || window.pageYOffset || 0;
    const maxScrollY = Math.max(
        0,
        document.documentElement.scrollHeight - window.innerHeight
    );
    const targetY = Math.max(0, Math.min(rawTargetY, maxScrollY));

    const totalDist = Math.abs(targetY - startY);
    const direction = targetY > startY ? 1 : -1;

    if (totalDist < 1) {
        window.scrollTo({ top: targetY, left: window.scrollX, behavior: 'instant' });
        done();
        return;
    }

    const minSpeed = maxSpeed * minRatio;
    const activeEase = Math.min(easeDist, totalDist / 2);

    // Exact duration of each phase from integrating the raised-cosine velocity curve:
    // v(t) = minSpeed + (maxSpeed - minSpeed) * 0.5 * (1 - cos(pi * t / tEase))
    const tEase = activeEase > 0 ? (2 * activeEase) / (minSpeed + maxSpeed) : 0;
    const cruiseDist = totalDist - 2 * activeEase;
    const tCruise = cruiseDist / maxSpeed;
    const tTotal = 2 * tEase + tCruise;

    // Position traveled after `t` seconds into an ease-in phase (0 <= t <= tEase)
    function easeDisplacement(t) {
        if (tEase === 0) return 0;
        const avgSpeed = (minSpeed + maxSpeed) * 0.5;
        const amp = (maxSpeed - minSpeed) * tEase / (2 * Math.PI);
        return avgSpeed * t - amp * Math.sin((Math.PI * t) / tEase);
    }

    let elapsed = 0;
    let lastTime = null;

    function step(currentTime) {
        if (lastTime === null) {
            lastTime = currentTime;
            requestAnimationFrame(step);
            return;
        }

        // Cap dt at 0.05s to prevent jumps after tab switches
        const dt = Math.min((currentTime - lastTime) / 1000, 0.05);
        lastTime = currentTime;
        elapsed += dt;

        if (elapsed >= tTotal) {
            window.scrollTo({ top: targetY, left: window.scrollX, behavior: 'instant' });
            done();
            return;
        }

        let traveled;
        if (elapsed < tEase) {
            // Ease-in phase
            traveled = easeDisplacement(elapsed);
        } else if (elapsed < tEase + tCruise) {
            // Cruise phase
            traveled = activeEase + maxSpeed * (elapsed - tEase);
        } else {
            // Ease-out phase (mirror of ease-in)
            const remainingTime = tTotal - elapsed;
            traveled = totalDist - easeDisplacement(remainingTime);
        }

        window.scrollTo({
            top: startY + direction * traveled,
            left: window.scrollX,
            behavior: 'instant'
        });
        requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
    """

    # Ensure timeout covers long scrolls safely
    driver.set_script_timeout(120)
    driver.execute_async_script(script, target_y, max_speed, ease_distance, min_speed_ratio)

def _capture_window_loop(
    rect: dict,
    frames: list[Image.Image],
    capture_stop: threading.Event,
    fps: int = 8,
    dpr: float = 1.0,
):
    monitor = {
        "left": max(0, int(rect["x"] * dpr)),
        "top": max(0, int(rect["y"] * dpr)),
        "width": int(rect["width"] * dpr),
        "height": int(rect["height"] * dpr),
    }
    interval = 1.0 / fps

    with mss.mss() as sct:
        while not capture_stop.is_set():
            t0 = time.perf_counter()
            shot = sct.grab(monitor)
            frames.append(Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX"))
            elapsed = time.perf_counter() - t0
            capture_stop.wait(max(0.0, interval - elapsed))

def re_run_actions(
    url: str, 
    saved_actions: list[dict], 
    stop_event: threading.Event | None = None, 
    on_saving=None
) -> str | None:
    
    driver = get_driver(
        url=url,
        web_options={
            'hide-scrollbars': True
        }
    )
    # driver.set_window_rect(x=50, y=50, width=1280, height=720)
    driver.switch_to.window(driver.current_window_handle)
    driver.execute_script("window.focus();")
    time.sleep(0.3)

    frames: list[Image.Image] = []
    temp_dir = tempfile.mkdtemp(prefix="primr_")
    video_path = os.path.join(temp_dir, "recording.mp4")
    gif_path = os.path.join(temp_dir, "recording.gif")

    capture_stop = threading.Event()
    dpr = driver.execute_script("return window.devicePixelRatio") or 1.0
    rect = driver.get_window_rect()

    rec_thread = threading.Thread(
        target=_capture_window_loop,
        args=(rect, frames, capture_stop, 8, dpr),
        daemon=True,
    )
    rec_thread.start()

    try:
        for idx, action in enumerate(saved_actions):
            if stop_event and stop_event.is_set():
                break

            if action["action"] != "scroll":
                continue

            _, target_y = action["target"]
            smooth_scroll(driver=driver, target_y=target_y)

            if stop_event:
                stop_event.wait(1)
            else:
                time.sleep(1)
    finally:
        capture_stop.set()
        rec_thread.join(timeout=2)
        driver.quit()

    if not frames:
        return None

    if on_saving:
        on_saving()

    save_recording(frames, gif_path=gif_path, video_path=video_path, fps=8)
    return gif_path

