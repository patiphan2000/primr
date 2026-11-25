def clean_action(
    actions: list[dict],
    scroll_to_click: bool = True
) -> list[dict]:
    
    # Save or convert to Python code
    print("\nGenerated Selenium Replay Code:")
    saved_actions = []
    for idx, act in enumerate(actions):
        if act["type"] == "click":
            
            # Normalize scroll to click element
            if scroll_to_click and idx > 0 and actions[idx - 1]["type"] == "scroll":
                prev_act = saved_actions.pop(-1)
                _target_y = int(act["y"] + (act["height"] // 1.3))
                saved_actions.append({
                    'order': prev_act['order'],
                    'action': 'scroll',
                    'target': (prev_act["target"][0], _target_y)
                })
                
            # Add click element
            saved_actions.append({
                'order': idx + 1,
                'action': 'click',
                'target': act["target"],
                'text': act.get("text", ""),
                'coords': (act["x"], act["y"]),
                'height': act.get("height", 0)
            })
            
        elif act["type"] == "scroll":
            saved_actions.append({
                'order': idx + 1,
                'action': 'scroll',
                'target': (act["x"], act["y"])
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