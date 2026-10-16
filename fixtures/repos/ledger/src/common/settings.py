"""Settings shipped with the service (config/schedules.json)."""
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "config" / "schedules.json"


def _load():
    return json.loads(_PATH.read_text(encoding="utf-8"))


def base_terms():
    """The payment terms every schedule starts from."""
    return dict(_load()["defaults"])


def schedule_names():
    """Every schedule an account can be on."""
    return sorted(_load()["schedules"])


def schedule_terms(name):
    """What a schedule sets differently from the base terms (may be empty)."""
    return dict(_load()["schedules"][name])
