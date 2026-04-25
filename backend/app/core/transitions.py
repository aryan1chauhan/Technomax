VALID_TRANSITIONS = {
    "dispatched":   ["accepted", "declined", "en_route", "cancelled"],
    "accepted":     ["en_route",     "cancelled"],
    "declined":     [],   # terminal for this hospital assignment; admin/re-dispatch must follow
    "en_route":     ["on_scene",     "cancelled"],
    "on_scene":     ["transporting", "cancelled"],
    "transporting": ["arrived",      "cancelled"],
    "arrived":      ["stabilized",   "completed", "cancelled"],
    "stabilized":   ["en_route_secondary", "completed", "cancelled"],
    "completed":    [],   # terminal — no further transitions
    "cancelled":    [],   # terminal — no further transitions
}

TERMINAL_STATUSES = {"completed", "cancelled", "declined"}
BED_RESTORE_STATUSES = {"stabilized", "completed", "cancelled", "declined"}

def validate_transition(current: str, next_status: str) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, [])
