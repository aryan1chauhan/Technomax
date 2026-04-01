VALID_TRANSITIONS = {
    "dispatched":   ["en_route",     "cancelled"],
    "en_route":     ["on_scene",     "cancelled"],
    "on_scene":     ["transporting", "cancelled"],
    "transporting": ["arrived",      "cancelled"],
    "arrived":      ["completed",    "cancelled"],
    "completed":    [],   # terminal — no further transitions
    "cancelled":    [],   # terminal — no further transitions
}

TERMINAL_STATUSES = {"completed", "cancelled"}
BED_RESTORE_STATUSES = {"completed", "cancelled"}

def validate_transition(current: str, next: str) -> bool:
    return next in VALID_TRANSITIONS.get(current, [])
