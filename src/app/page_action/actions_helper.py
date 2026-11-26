def clean_action(
    actions: list[dict],
    scroll_to_click: bool = True
) -> list[dict]:
    
    print("\nGenerated Selenium Replay Code:")
    saved_actions = []
    for idx, act in enumerate(actions):
        if act["type"] == "click":
            if scroll_to_click and idx > 0 and actions[idx - 1]["type"] == "scroll":
                prev_act = saved_actions.pop(-1)
                _target_y = int(act["y"] + (act["height"] // 1.3))
                saved_actions.append({
                    'order': prev_act['order'],
                    'action': 'scroll',
                    'target': (prev_act["target"][0], _target_y),
                    'mouse_pos': prev_act.get('mouse_pos', (0, 0)),
                    'xpath': prev_act.get('xpath', ''),
                })
                
            saved_actions.append({
                'order': idx + 1,
                'action': 'click',
                'target': act["target"],
                'xpath': act.get("xpath", ""),
                'text': act.get("text", ""),
                'coords': (act["x"], act["y"]),
                'height': act.get("height", 0),
                'wait_after_click': 0.0
            })
            
        elif act["type"] == "scroll":
            saved_actions.append({
                'order': idx + 1,
                'action': 'scroll',
                'target': (act["x"], act["y"]),
                'mouse_pos': (act.get("mouse_x", 0), act.get("mouse_y", 0)),
                'xpath': act.get("xpath", ""),
            })
            
    saved_actions.insert(
        0, 
        {
            'order': 0,
            'action': 'wait',
            'duration': 0.5
        }
    )
    return saved_actions