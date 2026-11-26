import threading
import time
from typing import Literal

from .actions_helper import clean_action
from .driver_helper import get_driver


def record_page_actions(
    url: str, 
    stop_event: threading.Event | None = None,
    aspect_ratio: Literal['3:2', '4:3', '16:9']='4:3',
    orientation: Literal['portrait', 'landscape']='portrait',
) -> list[dict]:
    
    driver = get_driver(
        url,
        aspect_ratio=aspect_ratio,
        orientation=orientation
    )

    recorder_js = """
    window.recordedActions = [];

    let lastMouseX = 0;
    let lastMouseY = 0;

    document.addEventListener('mousemove', function(e) {
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
    }, { passive: true, capture: true });

    document.addEventListener('wheel', function(e) {
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
    }, { passive: true, capture: true });

    function escapeXPathAttr(val) {
        if (!val.includes('"')) return '"' + val + '"';
        if (!val.includes("'")) return "'" + val + "'";
        return 'concat(' + val.split('"').map(function(part) {
            return '"' + part + '"';
        }).join(', ' + "'" + '"' + "'" + ', ') + ')';
    }

    function getXPath(el) {
        if (!el || el.nodeType !== Node.ELEMENT_NODE) return '';
        if (el.id) {
            return '//*[@id=' + escapeXPathAttr(el.id) + ']';
        }
        const parts = [];
        while (el && el.nodeType === Node.ELEMENT_NODE) {
            if (el.id) {
                parts.unshift('*[@id=' + escapeXPathAttr(el.id) + ']');
                return '//' + parts.join('/');
            }
            let tag = el.tagName.toLowerCase();
            if (el.namespaceURI === 'http://www.w3.org/2000/svg') {
                tag = '*[local-name()="' + tag + '"]';
            }
            let index = 1;
            let sibling = el.previousElementSibling;
            while (sibling) {
                if (sibling.tagName === el.tagName) {
                    index++;
                }
                sibling = sibling.previousElementSibling;
            }
            parts.unshift(tag + '[' + index + ']');
            el = el.parentElement;
        }
        return '/' + parts.join('/');
    }

    document.addEventListener('click', function(e) {
        let target = e.target;
        let identifier = target.id ? '#' + target.id : target.tagName.toLowerCase();
        window.recordedActions.push({
            type: 'click',
            target: identifier,
            xpath: getXPath(target),
            text: target.innerText ? target.innerText.trim().slice(0, 30) : '',
            height: Math.round(target.getBoundingClientRect().height),
            x: Math.round(target.getBoundingClientRect().x),
            y: Math.round(target.getBoundingClientRect().y)
        });
    }, true);

    let scrollTimeout;
    window.addEventListener('scroll', function(e) {
        const target = e.target;
        const mouseX = lastMouseX;
        const mouseY = lastMouseY;

        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            const isDoc = (
                target === document ||
                target === document.documentElement ||
                target === document.scrollingElement
            );
            let relX = mouseX;
            let relY = mouseY;
            if (!isDoc && relX === 0 && relY === 0 && target.getBoundingClientRect) {
                const r = target.getBoundingClientRect();
                relX = r.left + r.width / 2;
                relY = r.top + r.height / 2;
            }
            window.recordedActions.push({
                type: 'scroll',
                x: Math.round(isDoc ? window.scrollX : target.scrollLeft),
                y: Math.round(isDoc ? window.scrollY : target.scrollTop),
                mouse_x: Math.round(relX),
                mouse_y: Math.round(relY),
                xpath: isDoc ? '' : getXPath(target)
            });
        }, 300);
    }, true);
    """
    
    driver.execute_script(recorder_js)

    actions = []
    try:
        # Loop until stop_event is set (or Ctrl+C if run from CLI)
        while stop_event is None or not stop_event.is_set():
            new_actions = driver.execute_script("""
                let acts = window.recordedActions || [];
                window.recordedActions = [];
                return acts;
            """)
            if new_actions:
                actions.extend(new_actions)
                for act in new_actions:
                    print("Recorded:", act)

            time.sleep(0.2)  # Prevent 100% CPU usage
    except KeyboardInterrupt:
        print("\nRecording stopped.")
    finally:
        driver.quit()  # Remove this line if you want to keep the browser open

    return clean_action(actions)
