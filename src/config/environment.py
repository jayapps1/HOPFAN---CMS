"""The shared, explicit project .env loader used by desktop and API."""
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_environment() -> None:
    # Preserve the desktop application's existing .env precedence.
    load_dotenv(dotenv_path=ENV_FILE, override=True)
