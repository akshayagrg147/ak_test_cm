"""Create production secrets once on the EC2 host; never print secret values."""

import argparse
import base64
import ipaddress
import json
import os
import re
import secrets
from pathlib import Path


def configure(root: Path, host: str):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,251}[a-zA-Z0-9]", host):
            raise ValueError(
                "Provide a hostname or IP address without a scheme or path"
            )
    shared = root / "shared"
    shared.mkdir(parents=True, exist_ok=True, mode=0o700)
    app = shared / "app.env"
    database = shared / "database.env"
    if app.exists() != database.exists():
        raise RuntimeError(
            "Incomplete secrets: restore the matching environment files; do not regenerate them"
        )
    if app.exists():
        return
    password = secrets.token_urlsafe(40)
    values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": f"postgresql+psycopg://crm:{password}@db:5432/talkocrm",
        "SECRET_KEY": secrets.token_urlsafe(64),
        "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "PUBLIC_ORIGIN": f"https://{host}",
        "STORAGE_PATH": "/storage",
        "BRAND_NAME": "ViaCRM",
        "MAX_RECORDING_UPLOAD": str(64 * 1024 * 1024),
    }
    os.umask(0o077)
    # JSON strings are valid quoted values in Compose/dotenv env files.
    app.write_text(
        "".join(f"{key}={json.dumps(value)}\n" for key, value in values.items())
    )
    database.write_text(
        f"POSTGRES_DB=talkocrm\nPOSTGRES_USER=crm\nPOSTGRES_PASSWORD={password}\nTZ=UTC\n"
    )
    app.chmod(0o600)
    database.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/viacrm"))
    parser.add_argument("--host", required=True)
    args = parser.parse_args()
    configure(args.root, args.host)
