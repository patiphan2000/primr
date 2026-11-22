from typing import Literal

from selenium import webdriver

ASPECT_RATION_RESOLUTION = {
    '4:3': (1280, 960),
    '16:9': (1280, 960),
    '18:9': (1280, 960),
}

def get_driver(
    url: str,
    aspect_ratio: Literal['4:3', '16:9', '18:9'] = '4:3',
    orientation: Literal['portrait', 'landscape'] = 'portrait',
    web_options: dict[str, bool]={},
):
    # Set options
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--remote-allow-origins=*")
    
    # Add URL
    options.add_argument(f"--app={url}")
    
    # Set resolution
    w, h = ASPECT_RATION_RESOLUTION.get(aspect_ratio, (1280, 960))
    x, y = w, h
    if orientation == 'portrait':
        x, y = h, w
    options.add_argument(f"--window-size={x},{y}")
    
    # More Option
    if web_options.get('hide-scrollbars'):
        options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options)
    
    return driver