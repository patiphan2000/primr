def clean_action(
    actions: list[dict],
    scroll_to_click=True
) -> list[dict]:
    
    # Save or convert to Python code
    print("\nGenerated Selenium Replay Code:")
    saved_actions = []
    for idx, act in enumerate(actions):
        if act["type"] == "click":
            
            # Add scroll to click element
            if idx > 0 and actions[idx - 1]['type'] == 'scroll':
                prev_act = saved_actions.pop(-1)
                _target_y = act["y"] + (act["height"] // 1.3)
                saved_actions.append({
                    'order': idx + 1,
                    'action': 'scroll',
                    'target': (prev_act["target"][0], _target_y)
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