"""Write the private environment file used by the Ubuntu Docker Compose install."""
from __future__ import annotations

import os
from pathlib import Path


def compose_env_value(value: str) -> str:
    """Quote one value for Compose's .env parser without expanding its contents."""
    if "\n" in value or "\r" in value or "\0" in value:
        raise ValueError("Environment values must fit on one line.")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def compose_environment(values: dict[str, str]) -> str:
    return "".join(f"{key}={compose_env_value(value)}\n" for key, value in values.items())


def main() -> None:
    hostname = os.environ["NCET_INSTALL_PUBLIC_HOST"]
    values = {
        "APP_ENV": "production",
        "PUBLIC_HOST": hostname,
        "PUBLIC_ORIGIN": "https://" + hostname,
        "POSTGRES_PASSWORD": os.environ["NCET_INSTALL_POSTGRES_PASSWORD"],
        "SETTINGS_ENCRYPTION_KEY": os.environ["NCET_INSTALL_ENCRYPTION_KEY"],
        "NCET_BOOTSTRAP_ADMIN_USERNAME": os.environ["NCET_INSTALL_ADMIN_USERNAME"],
        "NCET_BOOTSTRAP_ADMIN_PASSWORD": os.environ["NCET_INSTALL_ADMIN_PASSWORD"],
        "SCAN_MODE": "clamav",
        "CLAMAV_HOST": "clamav",
        "CLAMAV_PORT": "3310",
    }
    Path(".env").write_text(compose_environment(values), encoding="utf-8")


if __name__ == "__main__":
    main()

