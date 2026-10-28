"""Create local secrets without printing or committing them. Existing values are preserved."""
import base64
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
text = path.read_text() if path.exists() else (root / ".env.example").read_text()
values = {"SECRET_KEY": secrets.token_urlsafe(64), "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), "DB_PASSWORD": secrets.token_urlsafe(32)}
lines = []
for line in text.splitlines():
    key, _, value = line.partition("=")
    if key in values and not value:
        line = key + "=" + values[key]
    lines.append(line)
path.write_text("\n".join(lines) + "\n")
path.chmod(0o600)
print("Local .env configured. Secret values were not printed.")
