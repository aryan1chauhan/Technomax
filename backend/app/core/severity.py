from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    MODERATE = "moderate"
    LOW = "low"


# Per-severity scoring weights and operational constraints.
# Weights must sum to 1.0 within each severity tier.
SEVERITY_CONFIG: dict[str, dict] = {
    Severity.CRITICAL: {
        "weights": {
            "distance":   0.55,
            "beds":       0.10,
            "specialist": 0.30,
            "equipment":  0.05,
        },
        "min_beds": 1,            # Even 1 bed is acceptable in a critical case
        "max_distance_km": 60,    # Wider search radius for critical
        "badge": {
            "label": "CRITICAL",
            "bg": "#7f1d1d",
            "text": "#fecaca",
            "border": "#ef4444",
        },
    },
    Severity.MODERATE: {
        "weights": {
            "distance":   0.35,
            "beds":       0.25,
            "specialist": 0.25,
            "equipment":  0.15,
        },
        "min_beds": 2,
        "max_distance_km": 45,
        "badge": {
            "label": "MODERATE",
            "bg": "#78350f",
            "text": "#fef3c7",
            "border": "#f59e0b",
        },
    },
    Severity.LOW: {
        "weights": {
            "distance":   0.15,
            "beds":       0.45,   # Capacity matters more for non-urgent cases
            "specialist": 0.15,
            "equipment":  0.25,
        },
        "min_beds": 3,
        "max_distance_km": 30,
        "badge": {
            "label": "LOW",
            "bg": "#14532d",
            "text": "#dcfce7",
            "border": "#22c55e",
        },
    },
}


def get_severity_config(severity: str) -> dict:
    """Return config for given severity string, defaulting to MODERATE."""
    key = severity.lower() if severity else Severity.MODERATE
    return SEVERITY_CONFIG.get(key, SEVERITY_CONFIG[Severity.MODERATE])
