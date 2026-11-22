import threading
import time

from .actions_helper import clean_action
from .driver_helper import get_driver


def record_page_actions(url: str, stop_event: threading.Event | None = None) -> list[dict]:
    
    driver = get_driver(url)

    recorder_js = """
    window.recordedActions = [];

    document.addEventListener('click', function(e) {
        let target = e.target;
        let identifier = target.id ? '#' + target.id : target.tagName.toLowerCase();
        window.recordedActions.push({
            type: 'click',
            target: identifier,
            text: target.innerText ? target.innerText.trim().slice(0, 30) : '',
            height: Math.round(target.getBoundingClientRect().height),
            x: Math.round(target.getBoundingClientRect().x),
            y: Math.round(target.getBoundingClientRect().y)
        });
    }, true);

    let scrollTimeout;
    window.addEventListener('scroll', function() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            window.recordedActions.push({
                type: 'scroll',
                x: Math.round(window.scrollX),
                y: Math.round(window.scrollY)
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
