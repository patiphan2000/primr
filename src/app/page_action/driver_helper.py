from typing import Literal

from selenium import webdriver

ASPECT_RATIOS = {
    '3:2': (3, 2),
    '4:3': (4, 3),
    '16:9': (16, 9),
}

def get_driver(
    url: str,
    aspect_ratio: Literal['3:2', '4:3', '16:9'] = '4:3',
    orientation: Literal['portrait', 'landscape'] = 'portrait',
    web_options: dict[str, bool] = {},
):
    # Set options
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--remote-allow-origins=*")

    # Add URL
    options.add_argument(f"--app={url}")

    # More Options
    if web_options.get('hide-scrollbars'):
        options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)

    # Get usable screen area (excludes taskbar/dock, respects DPI scaling)
    avail_left, avail_top, avail_w, avail_h = driver.execute_script(
        """
        return [
            window.screen.availLeft || 0,
            window.screen.availTop || 0,
            window.screen.availWidth,
            window.screen.availHeight
        ];
        """
    )

    # Calculate largest dimensions that fit the screen for the given aspect ratio
    rw, rh = ASPECT_RATIOS.get(aspect_ratio, (4, 3))
    if orientation == 'portrait':
        rw, rh = rh, rw

    scale = min(avail_w / rw, avail_h / rh)
    width = min(int(rw * scale), avail_w)
    height = min(int(rh * scale), avail_h)

    # Center the window in the usable screen area
    pos_x = avail_left + (avail_w - width) // 2
    pos_y = avail_top + (avail_h - height) // 2

    driver.set_window_rect(x=pos_x, y=pos_y, width=width, height=height)

    return driver