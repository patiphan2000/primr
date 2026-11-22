import base64
import io
import os
import tempfile
import threading
import time

from PIL import Image

from .driver_helper import get_driver
from .video_helper import _get_cdp_ws_url, _screencast_loop, save_preview_gif


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

def re_run_actions(
    url: str,
    saved_actions: list[dict],
    stop_event: threading.Event | None = None,
    on_saving=None,
) -> tuple[str, list[tuple[float, bytes]], float] | None:
    
    driver = get_driver(url=url, web_options={"hide-scrollbars": True})

    frames: list[tuple[float, bytes]] = []
    temp_dir = tempfile.mkdtemp(prefix="primr_")
    preview_gif_path = os.path.join(temp_dir, "preview.gif")
    gif_path = os.path.join(temp_dir, "recording.gif")
    video_path = os.path.join(temp_dir, "recording.mp4")

    # Initial frame at t=0 (screencast only emits when the screen changes)
    init_shot = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "jpeg", "quality": 85})
    frames.append((0.0, base64.b64decode(init_shot["data"])))

    start_t = time.perf_counter()
    capture_stop = threading.Event()
    ws_url = _get_cdp_ws_url(driver)
    rec_thread = threading.Thread(
        target=_screencast_loop,
        args=(ws_url, frames, capture_stop, start_t),
        daemon=True,
    )
    rec_thread.start()

    try:
        for action in saved_actions:
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
        total_duration = time.perf_counter() - start_t
        capture_stop.set()
        rec_thread.join(timeout=2)
        driver.quit()

    if not frames:
        return None

    if on_saving:
        on_saving()

    save_preview_gif(frames, total_duration, preview_gif_path, gif_fps=15)
    return preview_gif_path, frames, total_duration