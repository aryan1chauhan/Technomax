VALID_TRANSITIONS = {
    "dispatched":   ["en_route",     "cancelled"],
    "en_route":     ["on_scene",     "cancelled"],
    "on_scene":     ["transporting", "cancelled"],
    "transporting": ["arrived",      "cancelled"],
    "arrived":      ["stabilized",   "completed", "cancelled"],
    "stabilized":   ["en_route_secondary", "completed", "cancelled"],
    "completed":    [],   # terminal — no further transitions
    "cancelled":    [],   # terminal — no further transitions
}

TERMINAL_STATUSES = {"completed", "cancelled"}
BED_RESTORE_STATUSES = {"stabilized", "completed", "cancelled"}

def validate_transition(current: str, next_status: str) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, [])
