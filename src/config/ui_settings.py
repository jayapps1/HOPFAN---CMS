import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "ui_preferences.json"


def load_appearance_mode() -> str:
    if not SETTINGS_FILE.exists():
        return "light"

    try:
        data = json.loads(
            SETTINGS_FILE.read_text(
                encoding="utf-8"
            )
        )

        mode = data.get(
            "appearance_mode",
            "light",
        ).lower()

        if mode not in {"light", "dark"}:
            return "light"

        return mode

    except Exception:
        return "light"


def save_appearance_mode(mode: str) -> None:
    mode = mode.lower()

    if mode not in {"light", "dark"}:
        mode = "light"

    SETTINGS_FILE.write_text(
        json.dumps(
            {
                "appearance_mode": mode
            },
            indent=2,
        ),
        encoding="utf-8",
    )
