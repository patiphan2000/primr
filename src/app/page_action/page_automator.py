import base64
import os
import tempfile
import threading
import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

def _perform_click(driver, action: dict, timeout: float = 3.0) -> None:
    xpath = action.get("xpath")
    target = action.get("target")
    coords = action.get("coords")

    element = None

    if xpath:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
        except TimeoutException:
            element = None

    if element is None and target:
        try:
            element = WebDriverWait(driver, 1.0).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, target))
            )
        except (TimeoutException, NoSuchElementException):
            element = None

    if element is not None:
        try:
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)
        return

    if coords:
        x, y = coords
        for event_type in ("mousePressed", "mouseReleased"):
            driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {
                    "type": event_type,
                    "x": int(x),
                    "y": int(y),
                    "button": "left",
                    "clickCount": 1,
                },
            )

def _find_scroll_container(driver, mouse_x: float, mouse_y: float, xpath: str = ""):
    if xpath:
        try:
            return driver.find_element(By.XPATH, xpath)
        except NoSuchElementException:
            pass

    if mouse_x or mouse_y:
        return driver.execute_script(
            """
            let curr = document.elementFromPoint(arguments[0], arguments[1]);
            while (curr && curr !== document.body && curr !== document.documentElement) {
                const style = window.getComputedStyle(curr);
                const canScrollY = (
                    (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowY === 'overlay') &&
                    curr.scrollHeight > curr.clientHeight
                );
                const canScrollX = (
                    (style.overflowX === 'auto' || style.overflowX === 'scroll' || style.overflowX === 'overlay') &&
                    curr.scrollWidth > curr.clientWidth
                );
                if (canScrollY || canScrollX) {
                    return curr;
                }
                curr = curr.parentElement;
            }
            return null;
            """,
            mouse_x,
            mouse_y,
        )
    return None

def _smooth_scroll_element(
    driver,
    element,
    target_x: float,
    target_y: float,
    max_speed: float = 400,
    ease_distance: float = 300,
    min_speed_ratio: float = 0.0,
) -> None:
    """
    Smoothly scrolls a DOM container (or window if element is None) to
    (target_x, target_y) using the same ease-in / cruise / ease-out S-curve
    as smooth_scroll().
    """
    if max_speed <= 0:
        raise ValueError("max_speed must be greater than 0")

    script = """
    const el = arguments[0];
    const rawTargetX = arguments[1];
    const rawTargetY = arguments[2];
    const maxSpeed = arguments[3];
    const easeDist = Math.max(0, arguments[4]);
    const minRatio = Math.max(0, Math.min(1, arguments[5]));
    const done = arguments[6];

    const isWindow = !el;
    const startX = isWindow ? (window.scrollX || window.pageXOffset || 0) : el.scrollLeft;
    const startY = isWindow ? (window.scrollY || window.pageYOffset || 0) : el.scrollTop;

    const maxScrollX = Math.max(
        0,
        isWindow
            ? (document.documentElement.scrollWidth - window.innerWidth)
            : (el.scrollWidth - el.clientWidth)
    );
    const maxScrollY = Math.max(
        0,
        isWindow
            ? (document.documentElement.scrollHeight - window.innerHeight)
            : (el.scrollHeight - el.clientHeight)
    );

    const targetX = Math.max(0, Math.min(rawTargetX, maxScrollX));
    const targetY = Math.max(0, Math.min(rawTargetY, maxScrollY));

    const dx = targetX - startX;
    const dy = targetY - startY;
    const totalDist = Math.hypot(dx, dy);

    function applyScroll(x, y) {
        if (isWindow) {
            window.scrollTo({ left: x, top: y, behavior: 'instant' });
        } else {
            el.scrollTo({ left: x, top: y, behavior: 'instant' });
        }
    }

    if (totalDist < 1) {
        applyScroll(targetX, targetY);
        done();
        return;
    }

    const dirX = dx / totalDist;
    const dirY = dy / totalDist;

    const minSpeed = maxSpeed * minRatio;
    const activeEase = Math.min(easeDist, totalDist / 2);

    const tEase = activeEase > 0 ? (2 * activeEase) / (minSpeed + maxSpeed) : 0;
    const cruiseDist = totalDist - 2 * activeEase;
    const tCruise = cruiseDist / maxSpeed;
    const tTotal = 2 * tEase + tCruise;

    function easeDisplacement(t) {
        if (tEase === 0) return 0;
        const avgSpeed = (minSpeed + maxSpeed) * 0.5;
        const amp = (maxSpeed - minSpeed) * tEase / (2 * Math.PI);
        return avgSpeed * t - amp * Math.sin((Math.PI * t) / tEase);
    }

    let elapsed = 0;
    let lastTime = null;

    function step(currentTime) {
        if (!isWindow && !el.isConnected) {
            done();
            return;
        }

        if (lastTime === null) {
            lastTime = currentTime;
            requestAnimationFrame(step);
            return;
        }

        const dt = Math.min((currentTime - lastTime) / 1000, 0.05);
        lastTime = currentTime;
        elapsed += dt;

        if (elapsed >= tTotal) {
            applyScroll(targetX, targetY);
            done();
            return;
        }

        let traveled;
        if (elapsed < tEase) {
            traveled = easeDisplacement(elapsed);
        } else if (elapsed < tEase + tCruise) {
            traveled = activeEase + maxSpeed * (elapsed - tEase);
        } else {
            const remainingTime = tTotal - elapsed;
            traveled = totalDist - easeDisplacement(remainingTime);
        }

        applyScroll(
            startX + dirX * traveled,
            startY + dirY * traveled
        );
        requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
    """

    driver.set_script_timeout(120)
    driver.execute_async_script(
        script,
        element,
        target_x,
        target_y,
        max_speed,
        ease_distance,
        min_speed_ratio,
    )


def _perform_scroll(
    driver,
    action: dict,
    max_speed: float = 400,
    ease_distance: float = 300,
    min_speed_ratio: float = 0.0,
) -> None:
    target_x, target_y = action["target"]
    mouse_x, mouse_y = action.get("mouse_pos", (0, 0))
    xpath = action.get("xpath", "")

    if mouse_x or mouse_y:
        driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseMoved",
                "x": int(mouse_x),
                "y": int(mouse_y),
            },
        )

    container = _find_scroll_container(driver, mouse_x, mouse_y, xpath)
    if container is not None:
        _smooth_scroll_element(
            driver=driver,
            element=container,
            target_x=target_x,
            target_y=target_y,
            max_speed=max_speed,
            ease_distance=ease_distance,
            min_speed_ratio=min_speed_ratio,
        )
    elif target_x:
        # Use 2D S-curve on window when horizontal scroll is also present
        _smooth_scroll_element(
            driver=driver,
            element=None,
            target_x=target_x,
            target_y=target_y,
            max_speed=max_speed,
            ease_distance=ease_distance,
            min_speed_ratio=min_speed_ratio,
        )
    else:
        smooth_scroll(
            driver=driver,
            target_y=target_y,
            max_speed=int(max_speed),
            ease_distance=int(ease_distance),
            min_speed_ratio=min_speed_ratio,
        )
        
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
            
            match action["action"]:
                case "wait":
                    time.sleep(float(action["duration"]))
                case "scroll":
                    _perform_scroll(driver=driver, action=action)
                case "click":
                    _perform_click(driver=driver, action=action)

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